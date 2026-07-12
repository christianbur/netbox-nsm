"""Bundle setup views — list, detail, preview, apply, and run_bundle."""

from __future__ import annotations

import json
from copy import deepcopy

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.core.setup_flags import setup_allow_destructive_actions, setup_menu_enabled
from netbox_nsm.bundles import setup_context
from netbox_nsm.type_metadata.permissions import (
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


def _load_named_bundle(slug: str) -> dict:
    """Load and return the bundle dict for *slug* or raise Http404."""
    from netbox_nsm.bundles.dispatch import load_bundle
    from netbox_nsm.bundles.paths import bundle_json_path

    try:
        bundle = load_bundle(bundle_json_path(slug))
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError):
        raise Http404
    bundle["_slug"] = slug
    return bundle


def _resolve_bundle_from_request(request, slug: str) -> dict:
    """Return on-disk bundle, optionally replaced by edited ``bundle_json`` POST field."""
    bundle = _load_named_bundle(slug)
    override = (request.POST.get("bundle_json") or "").strip()
    if not override:
        return bundle
    from netbox_nsm.bundles.dispatch import parse_bundle_json_override

    bundle = parse_bundle_json_override(override)
    bundle["_slug"] = slug
    return bundle


def _selected_cot_slugs_from_request(request) -> set[str] | None:
    """Return selected COT slugs from POST, or ``None`` when selection UI inactive."""
    if request.POST.get("cot_selection_active") != "1":
        return None

    values = request.POST.getlist("selected_cot_slugs")
    if not values:
        raw = (request.POST.get("selected_cot_slugs") or "").strip()
        if raw:
            values = [raw]

    selected: set[str] = set()
    for raw in values:
        for item in str(raw).split(","):
            slug = item.strip()
            if slug:
                selected.add(slug)
    return selected


def _filter_bundle_to_selected_cots(bundle: dict, selected_slugs: set[str] | None) -> dict:
    """Return a filtered bundle with only the selected COT definitions and side effects."""
    if selected_slugs is None:
        return bundle
    if not selected_slugs:
        raise ValueError("No COT selected. Select at least one COT to apply.")

    filtered = deepcopy(bundle)

    selected_types = [
        entry
        for entry in (filtered.get("types") or [])
        if isinstance(entry, dict) and str(entry.get("slug", "")).strip() in selected_slugs
    ]
    if not selected_types:
        raise ValueError("Selected COTs are not present in this bundle.")

    selected_type_slugs = {
        str(entry.get("slug", "")).strip()
        for entry in selected_types
        if isinstance(entry, dict)
    }

    filtered["types"] = selected_types

    object_entries = [
        entry
        for entry in (filtered.get("objects") or [])
        if isinstance(entry, dict)
    ]
    object_by_type: dict[str, dict] = {}
    for entry in object_entries:
        obj_type = str(entry.get("type", "")).strip()
        if obj_type and obj_type not in object_by_type:
            object_by_type[obj_type] = entry

    def _collect_local_refs(value, local_types: set[str], refs: set[str]) -> None:
        if isinstance(value, str):
            if "/" in value:
                type_name = value.split("/", 1)[0].strip()
                if type_name in local_types:
                    refs.add(type_name)
            return
        if isinstance(value, list):
            for item in value:
                _collect_local_refs(item, local_types, refs)
            return
        if isinstance(value, dict):
            for item in value.values():
                _collect_local_refs(item, local_types, refs)

    local_types = set(object_by_type.keys())
    included_object_types = {t for t in selected_type_slugs if t in local_types}
    queue = list(included_object_types)
    while queue:
        current = queue.pop(0)
        current_entry = object_by_type.get(current)
        if not current_entry:
            continue
        refs: set[str] = set()
        _collect_local_refs(current_entry.get("records") or [], local_types, refs)
        for ref_type in sorted(refs):
            if ref_type not in included_object_types:
                included_object_types.add(ref_type)
                queue.append(ref_type)

    filtered["objects"] = [
        entry
        for entry in object_entries
        if str(entry.get("type", "")).strip() in included_object_types
    ]

    used_choice_sets: set[str] = set()
    for type_def in selected_types:
        for field in (type_def.get("fields") or []):
            if not isinstance(field, dict):
                continue
            choice_set = str(field.get("choice_set", "")).strip()
            if choice_set:
                used_choice_sets.add(choice_set)
    filtered["choice_sets"] = [
        entry
        for entry in (filtered.get("choice_sets") or [])
        if isinstance(entry, dict) and str(entry.get("name", "")).strip() in used_choice_sets
    ]

    metadata = filtered.get("metadata")
    if isinstance(metadata, dict):
        type_meta = metadata.get("types")
        if isinstance(type_meta, dict):
            metadata["types"] = {
                slug: block
                for slug, block in type_meta.items()
                if slug in selected_type_slugs
            }
        rulebook_meta = metadata.get("rulebooks")
        if isinstance(rulebook_meta, dict):
            metadata["rulebooks"] = {
                slug: block
                for slug, block in rulebook_meta.items()
                if slug in selected_type_slugs
            }

    return filtered


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
        co_loaded = setup_context.custom_objects_plugin_loaded()
        co_ready = setup_context.custom_objects_db_ready()
        cot_status = setup_context.get_cot_status() if co_loaded else {}
        cots_ok = setup_context.all_cots_ok(cot_status) if co_loaded else False
        return {
            "custom_objects_plugin_loaded": co_loaded,
            "custom_objects_db_ready": co_ready,
            "cot_status": cot_status,
            "schema_bundles": setup_context.get_schema_bundles() if co_loaded else [],
            "all_cots_ok": cots_ok,
            "can_run_demo": cots_ok and setup_allow_destructive_actions(),
            "setup_allow_destructive_actions": setup_allow_destructive_actions(),
        }

    def get(self, request):
        return render(request, self.template_name, self._build_context())

    def post(self, request):
        if not setup_context.custom_objects_db_ready():
            messages.error(
                request,
                _(
                    "netbox-custom-objects database tables are missing. "
                    "Run: python manage.py migrate netbox_custom_objects"
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        action = request.POST.get("action", "")

        if action:
            messages.warning(
                request, _("Unknown action: %(action)s") % {"action": action}
            )
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
        try:
            bundle = _resolve_bundle_from_request(request, slug)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
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

        try:
            bundle = _resolve_bundle_from_request(request, slug)
        except ValueError as exc:
            messages.error(request, _("Invalid bundle JSON: %(error)s") % {"error": exc})
            return redirect(reverse("plugins:netbox_nsm:bundle_detail", args=[slug]))
        if bundle.get("bundle_kind") == "python":
            messages.error(
                request, _("Python bundles cannot be applied via this endpoint.")
            )
            return redirect(reverse("plugins:netbox_nsm:bundles"))

        selected_slugs = _selected_cot_slugs_from_request(request)
        try:
            bundle = _filter_bundle_to_selected_cots(bundle, selected_slugs)
        except ValueError as exc:
            messages.error(request, _("Apply failed: %(error)s") % {"error": exc})
            return redirect(reverse("plugins:netbox_nsm:bundle_detail", args=[slug]))

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
                "%(meta_types)s type metadata, %(meta_rb)s rulebook metadata"
                "%(ipam)s)."
            )
            % {
                "slug": slug,
                "types": summary.get("types_applied", 0),
                "meta_types": summary.get("metadata_types_synced", 0),
                "meta_rb": summary.get("metadata_rulebooks_synced", 0),
                "ipam": (
                    _(", %(count)s demo addresses linked to IPAM")
                    % {"count": summary.get("ipam_addresses_linked", 0)}
                    if summary.get("ipam_addresses_linked")
                    else ""
                ),
            },
        )
        return redirect(reverse("plugins:netbox_nsm:bundles"))
