"""Bundle setup views — list, detail, preview, apply, and run_bundle."""

from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.core.setup_flags import setup_allow_destructive_actions, setup_menu_enabled
from netbox_nsm.import_ import custom_objects
from netbox_nsm.objects.nsm_config_permissions import (
    ADD_CUSTOM_OBJECT_TYPE,
    CHANGE_CUSTOM_OBJECT_TYPE,
    VIEW_CUSTOM_OBJECT_TYPE,
)

__all__ = (
    "SetupView",
    "SetupSchemaApplyView",
    "SetupSchemaDetailView",
    "SetupSchemaPreviewView",
)


def _get_bundle_dir(slug: str):
    """Return the bundle directory for *slug* or raise Http404."""
    from netbox_nsm.bundles.paths import find_bundle_dirs

    dirs = find_bundle_dirs()
    if slug not in dirs:
        raise Http404
    return dirs[slug]


def _load_named_bundle(slug: str) -> dict:
    """Load and return the bundle dict for *slug* or raise Http404."""
    from netbox_nsm.bundles.dispatch import load_bundle

    bundle_dir = _get_bundle_dir(slug)
    try:
        bundle = load_bundle(bundle_dir / "bundle.json")
    except Exception:
        raise Http404
    bundle["_slug"] = slug
    return bundle


class _SetupBase(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if not setup_menu_enabled():
            raise Http404
        if not request.user.has_perm(VIEW_CUSTOM_OBJECT_TYPE):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)


class SetupView(_SetupBase):
    template_name = "netbox_nsm/setup.html"

    def _build_context(self):
        co_loaded = custom_objects.custom_objects_plugin_loaded()
        co_ready = custom_objects.custom_objects_db_ready()
        cot_status = custom_objects.get_cot_status() if co_loaded else {}
        cots_ok = custom_objects.all_cots_ok(cot_status) if co_loaded else False
        return {
            "custom_objects_plugin_loaded": co_loaded,
            "custom_objects_db_ready": co_ready,
            "cot_status": cot_status,
            "schema_bundles": custom_objects.get_schema_bundles() if co_loaded else [],
            "all_cots_ok": cots_ok,
            "can_run_demo": cots_ok and setup_allow_destructive_actions(),
            "setup_allow_destructive_actions": setup_allow_destructive_actions(),
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context())

    def post(self, request):
        if not custom_objects.custom_objects_db_ready():
            messages.error(
                request,
                _(
                    "netbox-custom-objects database tables are missing. "
                    "Run: python manage.py migrate netbox_custom_objects"
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        action = request.POST.get("action", "")

        if action == "run_bundle":
            return self._handle_run_bundle(request)

        if action:
            messages.warning(
                request, _("Unknown action: %(action)s") % {"action": action}
            )
        return redirect(reverse("plugins:netbox_nsm:bundles"))

    # ------------------------------------------------------------------
    # run_bundle — generic Python bundle runner
    # ------------------------------------------------------------------

    def _handle_run_bundle(self, request) -> HttpResponse:
        slug = request.POST.get("slug", "").strip()
        if not slug:
            messages.error(request, _("run_bundle: no slug provided."))
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        if not setup_allow_destructive_actions():
            messages.error(
                request,
                _("Bundle actions are disabled (setup_allow_destructive_actions)."),
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        # Load manifest to check needs_confirm
        from netbox_nsm.bundles.dispatch import load_bundle
        from netbox_nsm.bundles.paths import find_bundle_dirs
        from netbox_nsm.bundles.runner import run_bundle

        bundle_dirs = find_bundle_dirs()
        if slug not in bundle_dirs:
            messages.error(
                request, _("Bundle not found: %(slug)s") % {"slug": slug}
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        try:
            bundle = load_bundle(bundle_dirs[slug] / "bundle.json")
        except Exception as exc:
            messages.error(
                request, _("Could not load bundle: %(error)s") % {"error": exc}
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        if bundle.get("needs_confirm") and not request.POST.get("confirm"):
            messages.error(
                request,
                _(
                    "Please confirm before running bundle '%(slug)s'."
                ) % {"slug": slug},
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        try:
            result = run_bundle(slug, request)
            if isinstance(result, HttpResponse):
                return result
        except Exception as exc:
            messages.error(request, _("Error: %(error)s") % {"error": exc})

        return redirect(reverse("plugins:netbox_nsm:bundles"))


# ---------------------------------------------------------------------------
# Bundle detail, preview, and apply
# ---------------------------------------------------------------------------


class SetupSchemaDetailView(_SetupBase):
    template_name = "netbox_nsm/setup_schema_detail.html"

    def get(self, request, slug: str):
        bundle = _load_named_bundle(slug)
        if bundle.get("bundle_kind") == "python":
            raise Http404
        from netbox_nsm.bundles.dispatch import bundle_summary

        types = bundle.get("types") or []
        summary = bundle_summary(bundle)
        preview_open = request.GET.get("preview") == "1"
        return render(
            request,
            self.template_name,
            {
                "bundle_slug": slug,
                "bundle": bundle,
                "types": types,
                "bundle_status": summary.get("status"),
                "preview_open": preview_open,
                "can_apply": request.user.has_perm(ADD_CUSTOM_OBJECT_TYPE)
                and request.user.has_perm(CHANGE_CUSTOM_OBJECT_TYPE),
                "allow_destructive": setup_allow_destructive_actions(),
                "bundle_json": json.dumps(bundle, indent=2, ensure_ascii=False),
            },
        )


class SetupSchemaPreviewView(_SetupBase):
    def post(self, request, slug: str):
        if not request.user.has_perm(VIEW_CUSTOM_OBJECT_TYPE):
            return JsonResponse({"error": "Permission denied."}, status=403)
        bundle = _load_named_bundle(slug)
        if bundle.get("bundle_kind") == "python":
            return JsonResponse({"error": "Python bundles have no schema preview."}, status=400)
        allow_destructive = (
            setup_allow_destructive_actions()
            and request.POST.get("allow_destructive") == "1"
        )
        from netbox_nsm.bundles.dispatch import preview_bundle

        try:
            result = preview_bundle(bundle, allow_destructive=allow_destructive)
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse(result)


class SetupSchemaApplyView(_SetupBase):
    def post(self, request, slug: str):
        if not (
            request.user.has_perm(ADD_CUSTOM_OBJECT_TYPE)
            and request.user.has_perm(CHANGE_CUSTOM_OBJECT_TYPE)
        ):
            messages.error(
                request,
                _("Permission denied: custom object type add/change required."),
            )
            return redirect(reverse("plugins:netbox_nsm:bundle_detail", args=[slug]))

        bundle = _load_named_bundle(slug)
        if bundle.get("bundle_kind") == "python":
            messages.error(
                request, _("Python bundles cannot be applied via this endpoint.")
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        allow_destructive = (
            setup_allow_destructive_actions()
            and request.POST.get("allow_destructive") == "1"
        )
        from netbox_nsm.bundles.dispatch import apply_bundle

        try:
            summary = apply_bundle(bundle, allow_destructive=allow_destructive)
        except Exception as exc:
            messages.error(request, _("Apply failed: %(error)s") % {"error": exc})
            return redirect(reverse("plugins:netbox_nsm:bundle_detail", args=[slug]))

        messages.success(
            request,
            _(
                "Bundle '%(slug)s' applied (%(types)s types, "
                "%(meta_types)s type metadata, %(meta_rb)s rulebook metadata)."
            )
            % {
                "slug": slug,
                "types": summary.get("types_applied", 0),
                "meta_types": summary.get("metadata_types_synced", 0),
                "meta_rb": summary.get("metadata_rulebooks_synced", 0),
            },
        )
        return redirect(reverse("plugins:netbox_nsm:bundles"))
