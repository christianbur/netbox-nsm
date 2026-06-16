from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.forms.type_config import NsmConfigForm, config_form_class_for_slug
from netbox_nsm.objects.nsm_config import (
    clear_nsm_config_from_cot_comments,
    config_dict_from_spec,
    has_nsm_config_in_comments,
    parse_nsm_config_from_comments,
    resolve_nsm_config_for_cot,
    resolve_object_builder_config_for_cot,
    save_nsm_config_document_for_cot,
)
from netbox_nsm.objects.nsm_config_permissions import (
    nsm_config_add_permission,
    nsm_config_change_permission,
    nsm_config_delete_permission,
    nsm_config_view_permission,
)
from netbox_nsm.objects.type_config_specs import (
    TYPECONFIG_LIST_EXCLUDED_SLUGS,
    TYPECONFIG_SPEC_BY_SLUG,
    TYPECONFIG_UI_SPECS,
)

__all__ = (
    "ObjectConfigListView",
    "ObjectConfigView",
    "ObjectConfigEditView",
    "ObjectConfigDeleteView",
    "ObjectConfigAddView",
)


def _object_builder_template_rows(builder_config: dict | None) -> list[dict]:
    if not builder_config:
        return []
    sources = builder_config.get("sources") or {}
    rows = []
    for source_key, label in (
        ("ipam.ipaddress", _("IP Address")),
        ("ipam.prefix", _("Prefix")),
        ("ipam.iprange", _("IP Range")),
    ):
        template = (sources.get(source_key) or {}).get("build_template") or ""
        rows.append({"label": label, "template": template})
    return rows


def _get_ui_cot(slug: str):
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        raise Http404
    if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
        raise Http404
    return get_object_or_404(CustomObjectType, slug=slug)


def _resolved_configs():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return []

    configs = []
    for spec in TYPECONFIG_UI_SPECS:
        cot = CustomObjectType.objects.filter(slug=spec["slug"]).first()
        if not cot:
            continue
        resolved = resolve_nsm_config_for_cot(cot)
        if resolved and has_nsm_config_in_comments(cot.comments or ""):
            configs.append(resolved)
    return sorted(configs, key=lambda c: (c.sort_order, c.name))


def _document_updates_from_config_dict(config: dict) -> dict:
    updates = {
        "rule_view": {
            "sort_order": config.get("sort_order", 0),
            "display_template": config.get("display_template") or "{name}",
        },
    }
    if config.get("areas"):
        updates["rule_view"]["areas"] = list(config["areas"])
    if "panel" in config:
        updates["panel"] = config["panel"]
    if "object_builder" in config:
        updates["object_builder"] = config["object_builder"]
    return updates


class ObjectConfigListView(PermissionRequiredMixin, View):
    permission_required = nsm_config_view_permission()
    template_name = "netbox_nsm/typeconfig_list.html"

    def get(self, request):
        configs = _resolved_configs()
        return render(
            request,
            self.template_name,
            {"configs": configs},
        )


class ObjectConfigView(PermissionRequiredMixin, View):
    permission_required = nsm_config_view_permission()
    template_name = "netbox_nsm/typeconfig.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        config = resolve_nsm_config_for_cot(cot)
        if not config:
            raise Http404
        return render(
            request,
            self.template_name,
            {
                "cot": cot,
                "config": config,
                "object_builder": resolve_object_builder_config_for_cot(cot),
                "object_builder_templates": _object_builder_template_rows(
                    resolve_object_builder_config_for_cot(cot)
                ),
            },
        )


class ObjectConfigEditView(PermissionRequiredMixin, View):
    permission_required = nsm_config_change_permission()
    template_name = "generic/object_edit.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        config = resolve_nsm_config_for_cot(cot)
        if not config:
            raise Http404
        form = NsmConfigForm.from_config_dict(
            parse_nsm_config_from_comments(cot.comments or "")
            or config_dict_from_spec(TYPECONFIG_SPEC_BY_SLUG[cot.slug]),
            slug=cot.slug,
        )
        return render(
            request,
            self.template_name,
            {
                "object": cot,
                "form": form,
                "return_url": reverse("plugins:netbox_nsm:objectconfig", args=[slug]),
            },
        )

    def post(self, request, slug):
        cot = _get_ui_cot(slug)
        form = config_form_class_for_slug(cot.slug)(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "object": cot,
                    "form": form,
                    "return_url": reverse("plugins:netbox_nsm:objectconfig", args=[slug]),
                },
            )
        config_dict = form.to_config_dict()
        updates = _document_updates_from_config_dict(config_dict)
        if cot.slug == "nsm_address" and "object_builder" not in config_dict:
            updates["object_builder"] = None
        save_nsm_config_document_for_cot(cot, updates)
        messages.success(request, _("Object Config updated."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig", args=[slug]))


class ObjectConfigDeleteView(PermissionRequiredMixin, View):
    permission_required = nsm_config_delete_permission()
    template_name = "generic/object_delete.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        return render(
            request,
            self.template_name,
            {
                "object": cot,
                "return_url": reverse("plugins:netbox_nsm:objectconfig_list"),
            },
        )

    def post(self, request, slug):
        cot = _get_ui_cot(slug)
        clear_nsm_config_from_cot_comments(cot)
        messages.success(request, _("Object Config removed from comments."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig_list"))


class ObjectConfigAddView(PermissionRequiredMixin, View):
    permission_required = nsm_config_add_permission()
    template_name = "netbox_nsm/objectconfig_add.html"

    def get(self, request):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            raise Http404
        missing = []
        for spec in TYPECONFIG_UI_SPECS:
            cot = CustomObjectType.objects.filter(slug=spec["slug"]).first()
            if cot and not has_nsm_config_in_comments(cot.comments or ""):
                missing.append({"spec": spec, "cot": cot})
        return render(request, self.template_name, {"missing": missing})

    def post(self, request):
        slug = request.POST.get("slug", "").strip()
        if not slug or slug not in TYPECONFIG_SPEC_BY_SLUG:
            messages.error(request, _("Invalid object type slug."))
            return redirect(reverse("plugins:netbox_nsm:objectconfig_add"))
        cot = _get_ui_cot(slug)
        spec = TYPECONFIG_SPEC_BY_SLUG[slug]
        save_nsm_config_document_for_cot(
            cot,
            _document_updates_from_config_dict(config_dict_from_spec(spec)),
        )
        messages.success(request, _("Object Config created."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig", args=[slug]))
