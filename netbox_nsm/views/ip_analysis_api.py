"""
JSON API for the floating IP Analyzer applet.

GET /plugins/netbox-nsm/api/ip-analysis/?ct=<id>&pk=<id>&ct=...&pk=...
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from netbox_nsm.analysis.ip_analysis_service import (
    execute_ip_analysis_diff,
    execute_ip_analysis_merge,
    ip_analysis_json_response,
    parse_diff_sides_from_request,
    parse_object_refs,
    parse_selections_from_request,
)

__all__ = ("IpAnalysisApiView",)


class IpAnalysisApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        mode = (request.GET.get("mode") or "merge").strip().lower()

        if mode == "diff":
            return self._get_diff(request)

        ct_list = request.GET.getlist("ct")
        pk_list = request.GET.getlist("pk")

        if not ct_list or not pk_list:
            return JsonResponse({"error": "ct and pk required"}, status=400)

        selections, objs, unsupported, raw_selections, obj_by_key = (
            parse_selections_from_request(request)
        )
        payload = execute_ip_analysis_merge(
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
            request=request,
            include_html=True,
            include_structured_data=False,
        )
        return ip_analysis_json_response(payload)

    def _get_diff(self, request):
        sides = parse_diff_sides_from_request(request)
        if len(sides) < 2:
            return JsonResponse(
                {"error": "At least two diff sides required"}, status=400
            )

        payload = execute_ip_analysis_diff(
            sides=sides,
            request=request,
            include_html=True,
            include_structured_data=False,
        )
        return ip_analysis_json_response(payload)
