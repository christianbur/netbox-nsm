"""
IP Analysis page view.
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render
from django.views import View

from netbox_nsm.analysis.addr_analysis_utils import _parse_ipa_column_selections
from netbox_nsm.core.api_urls import get_api_url_for_content_type as _get_api_url_for_content_type
from netbox_nsm.objects.nsm_config import build_nsm_config_lookup

__all__ = ("IPAnalysisView",)


class IPAnalysisView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/ip_analysis.html"

    def get(self, request):
        seen_ct_ids = set()
        ip_api_types = []
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
            ip_api_types.append(
                {
                    "ct_id": ct.pk,
                    "api_url": api_url,
                    "name": str(mc._meta.verbose_name_plural).title(),
                }
            )

        ip_selections, ip_addr_columns = _parse_ipa_column_selections(request, "")
        ip2_selections, ip2_addr_columns = _parse_ipa_column_selections(request, "2")

        return render(
            request,
            self.template_name,
            {
                "ip_api_types": ip_api_types,
                "ip_selections": ip_selections,
                "ip_addr_columns": ip_addr_columns,
                "ip2_selections": ip2_selections,
                "ip2_addr_columns": ip2_addr_columns,
            },
        )
