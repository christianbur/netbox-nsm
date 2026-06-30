"""
JSON API for the IP Analyzer applet object picker.

GET /plugins/netbox-nsm/api/ip-analyzer/add-object-types/
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from netbox_nsm.analyzers.ip_analyzer.ipa_add_object_types import build_ipa_add_object_categories

__all__ = ("IpAnalyzerAddObjectTypesApiView",)


class IpAnalyzerAddObjectTypesApiView(LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"categories": build_ipa_add_object_categories()})
