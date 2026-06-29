"""
Object Analyzer page view.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from .modes import (
    AnalyzerMode,
    SECURITY_NSM_COT_SLUGS,
    get_security_allowed_ct_ids,
    parse_analyzer_mode,
)
from netbox_nsm.objects.nsm_config import build_nsm_config_lookup
from netbox_nsm.rulebooks.permissions import user_can_access_rulebooks

__all__ = ("ObjectAnalyzerView",)


def _extra_analyzer_types():
    return [
        {
            "ct_key": ("dcim", "device"),
            "api_url": "/api/dcim/devices/",
            "label": _("Device"),
        },
        {
            "ct_key": ("virtualization", "virtualmachine"),
            "api_url": "/api/virtualization/virtual-machines/",
            "label": _("Virtual Machine"),
        },
        {
            "ct_key": ("dcim", "interface"),
            "api_url": "/api/dcim/interfaces/",
            "label": _("Interface"),
        },
        {
            "ct_key": ("virtualization", "vminterface"),
            "api_url": "/api/virtualization/interfaces/",
            "label": _("VM Interface"),
        },
        {
            "ct_key": ("ipam", "ipaddress"),
            "api_url": "/api/ipam/ip-addresses/",
            "label": _("IP Address"),
        },
        {
            "ct_key": ("ipam", "prefix"),
            "api_url": "/api/ipam/prefixes/",
            "label": _("Prefix"),
        },
        {
            "ct_key": ("ipam", "iprange"),
            "api_url": "/api/ipam/ip-ranges/",
            "label": _("IP Range"),
        },
        {
            "ct_key": ("netbox_nsm", "rule"),
            "api_url": None,
            "label": _("Firewall Rule"),
            "security": False,
        },
    ]


def _nsm_config_slug(config) -> str | None:
    slug = getattr(config, "slug", None)
    if slug:
        return slug
    name = (getattr(config, "name", None) or "").strip().lower().replace(" ", "_")
    return name or None


def _mode_ui_context(mode: AnalyzerMode) -> dict[str, str | None]:
    if mode is AnalyzerMode.SECURITY:
        return {
            "search_placeholder": _(
                "Search: Device, VM, Interface, IP, Prefix, NSM Address …"
            ),
            "empty_title": _("Select a security-related object"),
            "empty_subtitle": _(
                "Search for hosts, interfaces, IPAM objects, or NSM addresses "
                "and groups — then click Analyze."
            ),
            "mode_hint": _(
                "Security view shows hosts, interfaces, IPAM, and NSM objects "
                "only. Labels, zones, rules, cables, and other infrastructure "
                "links are hidden."
            ),
        }
    return {
        "search_placeholder": _(
            "Search: Device, VM, IP, Prefix, Label, Zone, Rule …"
        ),
        "empty_title": _("Select an object to analyze"),
        "empty_subtitle": _(
            "Search above and click Analyze — the graph starts with the "
            "selected object. Use + on nodes to explore links; edge ▾ collapses "
            "a branch."
        ),
        "mode_hint": None,
    }


def _build_analyzer_legend(mode: AnalyzerMode) -> list[dict[str, str]]:
    items = [
        {"label": str(_("Device")), "color": "#0d6efd"},
        {"label": str(_("VM")), "color": "#0891b2"},
        {"label": str(_("Interface")), "color": "#6c757d"},
        {"label": str(_("IP")), "color": "#16a34a"},
        {"label": str(_("Prefix")), "color": "#0d9488"},
    ]
    if mode is AnalyzerMode.ALL:
        items.extend(
            [
                {"label": str(_("IP Range")), "color": "#d97706"},
                {"label": str(_("Label")), "color": "#c026d3"},
                {"label": str(_("Zone / Rule")), "color": "#dc3545"},
            ]
        )
        return items

    items.extend(
        [
            {"label": str(_("IP Range")), "color": "#d97706"},
            {"label": str(_("NSM Address")), "color": "#64748b"},
            {"label": str(_("NSM Address Group")), "color": "#78716c"},
            {"label": str(_("NSM Object Link")), "color": "#475569"},
        ]
    )
    return items


class ObjectAnalyzerView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/object_analyzer.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_can_access_rulebooks(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from django.contrib.contenttypes.models import ContentType

        from netbox_nsm.core.api_urls import (
            get_api_url_for_content_type as _get_api_url_for_content_type,
        )

        sel_ct = request.GET.get("ct", "")
        sel_pk = request.GET.get("pk", "")
        sel_name = request.GET.get("name", "")
        mode = parse_analyzer_mode(request.GET.get("mode", "all"))
        security_allowed_ct_ids = (
            get_security_allowed_ct_ids() if mode is AnalyzerMode.SECURITY else None
        )

        # Build search types: NSM configs + extras
        seen_ct_ids: set[int] = set()
        api_types = []

        configs = sorted(
            build_nsm_config_lookup().values(),
            key=lambda c: (
                (c.name or "").lower(),
                c.content_type_id,
            ),
        )
        for config in configs:
            if config.content_type_id in seen_ct_ids:
                continue
            if mode is AnalyzerMode.SECURITY:
                slug = _nsm_config_slug(config)
                if slug not in SECURITY_NSM_COT_SLUGS:
                    continue
                if (
                    security_allowed_ct_ids is not None
                    and config.content_type_id not in security_allowed_ct_ids
                ):
                    continue
            try:
                ct = ContentType.objects.get(pk=config.content_type_id)
            except ContentType.DoesNotExist:
                continue
            mc = ct.model_class()
            if not mc:
                continue
            api_url = _get_api_url_for_content_type(ct)
            if not api_url:
                continue
            seen_ct_ids.add(config.content_type_id)
            api_types.append(
                {
                    "ct_id": ct.pk,
                    "api_url": api_url,
                    "name": config.name or str(mc._meta.verbose_name_plural).title(),
                }
            )

        # Extra types (Device, VM, IP, Prefix, Rule, Rulebook)
        for t in _extra_analyzer_types():
            if mode is AnalyzerMode.SECURITY and t.get("security") is False:
                continue
            try:
                app, model = t["ct_key"]
                ct = ContentType.objects.get(app_label=app, model=model)
                if ct.pk in seen_ct_ids:
                    continue
                if (
                    mode is AnalyzerMode.SECURITY
                    and security_allowed_ct_ids is not None
                    and ct.pk not in security_allowed_ct_ids
                ):
                    continue
                # Resolve API URL
                api_url = t["api_url"]
                if api_url is None:
                    api_url = _get_api_url_for_content_type(ct)
                if not api_url:
                    continue
                seen_ct_ids.add(ct.pk)
                api_types.append(
                    {"ct_id": ct.pk, "api_url": api_url, "name": str(t["label"])}
                )
            except ContentType.DoesNotExist:
                pass

        mode_ui = _mode_ui_context(mode)
        return render(
            request,
            self.template_name,
            {
                "api_types": api_types,
                "sel_ct": sel_ct,
                "sel_pk": sel_pk,
                "sel_name": sel_name,
                "sel_mode": mode.value,
                "legend": _build_analyzer_legend(mode),
                **mode_ui,
            },
        )
