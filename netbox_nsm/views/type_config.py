from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.forms.type_config import NsmConfigForm, config_form_class_for_slug
from netbox_nsm.objects.nsm_config import (
    config_dict_from_spec,
    format_nsm_config_comment_yaml,
    has_nsm_config_in_comments,
    parse_nsm_config_from_comments,
    resolve_nsm_config_for_cot,
    resolve_object_builder_config_for_cot,
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


class ObjectConfigListView(PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.view_typeconfig"
    template_name = "netbox_nsm/typeconfig_list.html"

    def get(self, request):
        configs = _resolved_configs()
        return render(
            request,
            self.template_name,
            {"configs": configs},
        )


class ObjectConfigView(PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.view_typeconfig"
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
    permission_required = "netbox_nsm.change_typeconfig"
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
        cot.comments = format_nsm_config_comment_yaml(form.to_config_dict()).rstrip()
        cot.save(update_fields=["comments"])
        from netbox_nsm.core.display_utils import get_display_template_map

        get_display_template_map.cache_clear()
        messages.success(request, _("Object Config updated."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig", args=[slug]))


class ObjectConfigDeleteView(PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.delete_typeconfig"
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
        cot.comments = ""
        cot.save(update_fields=["comments"])
        messages.success(request, _("Object Config removed from comments."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig_list"))


class ObjectConfigAddView(PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.add_typeconfig"
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
        cot.comments = format_nsm_config_comment_yaml(config_dict_from_spec(spec)).rstrip()
        cot.save(update_fields=["comments"])
        messages.success(request, _("Object Config created."))
        return redirect(reverse("plugins:netbox_nsm:objectconfig", args=[slug]))
