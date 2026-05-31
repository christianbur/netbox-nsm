"""
Object Analyzer page view.
"""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views import View

from netbox_nsm.models import NSMTypeConfig

__all__ = ("ObjectAnalyzerView",)

_EXTRA_TYPES = [
    {
        "ct_key": ("dcim", "device"),
        "api_url": "/api/dcim/devices/",
        "label": "Device",
    },
    {
        "ct_key": ("virtualization", "virtualmachine"),
        "api_url": "/api/virtualization/virtual-machines/",
        "label": "Virtual Machine",
    },
    {
        "ct_key": ("ipam", "ipaddress"),
        "api_url": "/api/ipam/ip-addresses/",
        "label": "IP Address",
    },
    {
        "ct_key": ("ipam", "prefix"),
        "api_url": "/api/ipam/prefixes/",
        "label": "Prefix",
    },
    {
        "ct_key": ("netbox_nsm", "securitypolicyrule"),
        "api_url": None,
        "label": "Firewall Rule",
    },
    {
        "ct_key": ("netbox_nsm", "securitypolicyrulebook"),
        "api_url": None,
        "label": "Rulebook",
    },
]


class ObjectAnalyzerView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/object_analyzer.html"

    def get(self, request):
        from django.contrib.contenttypes.models import ContentType
        from netbox_nsm.views.security_policy import _get_api_url_for_content_type

        sel_ct = request.GET.get("ct", "")
        sel_pk = request.GET.get("pk", "")
        sel_name = request.GET.get("name", "")

        # Build search types: NSMTypeConfig + extras
        seen_ct_ids: set[int] = set()
        api_types = []

        # NSMTypeConfig types first
        for tc in NSMTypeConfig.objects.select_related("content_type").order_by(
            "order_id", "content_type__app_label", "content_type__model"
        ):
            if tc.content_type_id in seen_ct_ids:
                continue
            mc = tc.content_type.model_class()
            if not mc:
                continue
            api_url = _get_api_url_for_content_type(tc.content_type)
            if not api_url:
                continue
            seen_ct_ids.add(tc.content_type_id)
            api_types.append(
                {
                    "ct_id": tc.content_type.pk,
                    "api_url": api_url,
                    "name": str(tc),  # e.g. "Custom Objects › Labels"
                }
            )

        # Extra types (Device, VM, IP, Prefix, Rule, Rulebook)
        for t in _EXTRA_TYPES:
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
                    {"ct_id": ct.pk, "api_url": api_url, "name": t["label"]}
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
