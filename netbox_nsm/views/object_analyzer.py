"""
Object Analyzer page view.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

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
            "ct_key": ("netbox_nsm", "rule"),
            "api_url": None,
            "label": _("Firewall Rule"),
        },
    ]


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
            try:
                app, model = t["ct_key"]
                ct = ContentType.objects.get(app_label=app, model=model)
                if ct.pk in seen_ct_ids:
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

        return render(
            request,
            self.template_name,
            {
                "api_types": api_types,
                "sel_ct": sel_ct,
                "sel_pk": sel_pk,
                "sel_name": sel_name,
            },
        )
