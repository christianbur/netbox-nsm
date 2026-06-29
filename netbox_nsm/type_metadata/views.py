from dataclasses import dataclass

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.type_metadata.forms import (
    NsmConfigForm,
    area_labels_for_values,
    config_form_class_for_slug,
)
from netbox_nsm.core.display_template import DEFAULT_DISPLAY_TEMPLATE, normalize_display_template
from netbox_nsm.type_metadata.config import (
    clear_nsm_config_from_cot_comments,
    config_dict_from_spec,
    has_nsm_config_in_comments,
    resolve_nsm_config_dict_for_cot,
    resolve_nsm_config_for_cot,
    save_nsm_config_document_for_cot,
)
from netbox_nsm.type_metadata.permissions import (
    nsm_config_add_permission,
    nsm_config_change_permission,
    nsm_config_delete_permission,
    nsm_config_view_permission,
)
from netbox_nsm.type_metadata.roles import resolve_role_for_cot
from netbox_nsm.type_metadata.specs import (
    TYPECONFIG_SPEC_BY_SLUG,
    TYPECONFIG_UI_SPECS,
)

__all__ = (
    "TypeMetadataListView",
    "TypeMetadataView",
    "TypeMetadataEditView",
    "TypeMetadataDeleteView",
    "TypeMetadataAddView",
)


@dataclass(frozen=True)
class TypeMetadataListEntry:
    config: object
    has_stored_metadata: bool


def _metadata_eligible_slugs() -> set[str]:
    slugs = set(TYPECONFIG_SPEC_BY_SLUG)
    from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks

    for cot in iter_deployed_cot_rulebooks():
        slugs.add(cot.slug)
    return slugs


def _plugin_name_template_rows() -> list[dict]:
    from netbox_nsm.addresses.address_name_templates import (
        ADDRESS_MATCH_ALIASES,
        get_address_name_templates,
        normalize_match_value,
    )

    rows = []
    for entry in get_address_name_templates():
        match = normalize_match_value(entry.get("match"), aliases=ADDRESS_MATCH_ALIASES)
        rows.append({"match": match, "template": entry.get("template") or ""})
    return rows


def _get_ui_cot(slug: str):
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        raise Http404
    if slug not in _metadata_eligible_slugs():
        raise Http404
    return get_object_or_404(CustomObjectType, slug=slug)


def _has_metadata(cot) -> bool:
    return has_nsm_config_in_comments(cot.comments or "")


def _resolved_configs() -> list[TypeMetadataListEntry]:
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return []

    entries: list[TypeMetadataListEntry] = []
    seen: set[str] = set()
    for spec in TYPECONFIG_UI_SPECS:
        cot = CustomObjectType.objects.filter(slug=spec["slug"]).first()
        if not cot:
            continue
        seen.add(cot.slug)
        resolved = resolve_nsm_config_for_cot(cot)
        if resolved:
            entries.append(
                TypeMetadataListEntry(
                    config=resolved,
                    has_stored_metadata=_has_metadata(cot),
                )
            )
    for cot in CustomObjectType.objects.order_by("name", "slug"):
        if cot.slug in seen:
            continue
        if resolve_role_for_cot(cot) != "rulebook":
            continue
        resolved = resolve_nsm_config_for_cot(cot)
        if resolved:
            entries.append(
                TypeMetadataListEntry(
                    config=resolved,
                    has_stored_metadata=_has_metadata(cot),
                )
            )
    return sorted(
        entries,
        key=lambda entry: (
            entry.config.role or "",
            entry.config.sort_order,
            entry.config.name,
        ),
    )


def _document_updates_from_config_dict(config: dict) -> dict:
    updates = {
        "role": config.get("role"),
        "rule_view": {
            "sort_order": config.get("sort_order", 0),
            "display_template": normalize_display_template(
                config.get("display_template") or DEFAULT_DISPLAY_TEMPLATE
            ),
            "areas": list(config.get("areas") or []),
        },
        "links": dict(config.get("links") or {}),
    }
    return updates


class TypeMetadataListView(PermissionRequiredMixin, View):
    permission_required = nsm_config_view_permission()
    template_name = "netbox_nsm/typeconfig_list.html"

    def get(self, request):
        return render(
            request,
            self.template_name,
            {
                "configs": _resolved_configs(),
            },
        )


class TypeMetadataView(PermissionRequiredMixin, View):
    permission_required = nsm_config_view_permission()
    template_name = "netbox_nsm/typeconfig.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        config = resolve_nsm_config_for_cot(cot)
        if not config:
            raise Http404
        config_dict = resolve_nsm_config_dict_for_cot(cot) or {}
        links = dict(config_dict.get("links") or {})
        from netbox_nsm.addresses.address_cot_schema import cot_ipam_address_flag

        return render(
            request,
            self.template_name,
            {
                "cot": cot,
                "config": config,
                "config_dict": config_dict,
                "role_label": config.role_label,
                "areas": list(config_dict.get("areas") or []),
                "area_labels": area_labels_for_values(config_dict.get("areas")),
                "links": links,
                "has_stored_metadata": _has_metadata(cot),
                "show_plugin_name_templates": cot_ipam_address_flag(cot),
                "plugin_name_templates": _plugin_name_template_rows(),
            },
        )


class TypeMetadataEditView(PermissionRequiredMixin, View):
    permission_required = nsm_config_change_permission()
    template_name = "generic/object_edit.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        config_dict = resolve_nsm_config_dict_for_cot(cot)
        if not config_dict:
            raise Http404
        form = NsmConfigForm.from_config_dict(config_dict, slug=cot.slug)
        return render(
            request,
            self.template_name,
            {
                "object": cot,
                "form": form,
                "return_url": reverse("plugins:netbox_nsm:typemetadata", args=[slug]),
            },
        )

    def post(self, request, slug):
        cot = _get_ui_cot(slug)
        form = config_form_class_for_slug(cot.slug, cot=cot)(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "object": cot,
                    "form": form,
                    "return_url": reverse("plugins:netbox_nsm:typemetadata", args=[slug]),
                },
            )
        save_nsm_config_document_for_cot(
            cot,
            _document_updates_from_config_dict(form.to_config_dict()),
        )
        messages.success(request, _("Type Metadata updated."))
        return redirect(reverse("plugins:netbox_nsm:typemetadata", args=[slug]))


class TypeMetadataDeleteView(PermissionRequiredMixin, View):
    permission_required = nsm_config_delete_permission()
    template_name = "generic/object_delete.html"

    def get(self, request, slug):
        cot = _get_ui_cot(slug)
        return render(
            request,
            self.template_name,
            {
                "object": cot,
                "return_url": reverse("plugins:netbox_nsm:typemetadata_list"),
            },
        )

    def post(self, request, slug):
        cot = _get_ui_cot(slug)
        clear_nsm_config_from_cot_comments(cot)
        messages.success(request, _("Type Metadata removed from comments."))
        return redirect(reverse("plugins:netbox_nsm:typemetadata_list"))


class TypeMetadataAddView(PermissionRequiredMixin, View):
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
            if cot and not _has_metadata(cot):
                missing.append({"spec": spec, "cot": cot})
        return render(request, self.template_name, {"missing": missing})

    def post(self, request):
        slug = request.POST.get("slug", "").strip()
        if not slug or slug not in TYPECONFIG_SPEC_BY_SLUG:
            messages.error(request, _("Invalid object type slug."))
            return redirect(reverse("plugins:netbox_nsm:typemetadata_add"))
        cot = _get_ui_cot(slug)
        spec = TYPECONFIG_SPEC_BY_SLUG[slug]
        save_nsm_config_document_for_cot(
            cot,
            _document_updates_from_config_dict(config_dict_from_spec(spec)),
        )
        messages.success(request, _("Type Metadata created."))
        return redirect(reverse("plugins:netbox_nsm:typemetadata", args=[slug]))
