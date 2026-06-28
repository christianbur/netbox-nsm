"""
JSON API for the floating IP Analyzer applet.

GET /plugins/netbox-nsm/api/ip-analysis/?ct=<id>&pk=<id>&ct=...&pk=...
"""

from __future__ import annotations

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.views import View

from netbox_nsm.analysis.ip_analysis_service import (
    execute_ip_analysis_diff,
    execute_ip_analysis_merge,
    ip_analysis_json_response,
    parse_diff_sides_from_request,
    parse_object_refs,
    parse_selections_from_request,
)
from netbox_nsm.analysis.ipa_yaml_export import (
    build_ipa_export_child_objects,
    build_ipa_export_document,
    ipa_export_filename,
    parse_export_context_from_request,
    serialize_ipa_export_yaml,
)

__all__ = ("IpAnalysisApiView",)

logger = logging.getLogger(__name__)


class IpAnalysisApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        try:
            return self._get(request)
        except Exception as exc:
            logger.exception("IP analysis UI API failed")
            detail = str(exc).strip() or exc.__class__.__name__
            return JsonResponse(
                {
                    "error": _("Analysis failed: %(detail)s") % {"detail": detail},
                    "detail": detail,
                },
                status=500,
            )

    def _get(self, request):
        mode = (request.GET.get("mode") or "merge").strip().lower()
        export_yaml = (request.GET.get("format") or "").strip().lower() == "yaml"

        if mode == "diff":
            return self._get_diff(request, export_yaml=export_yaml)

        ct_list = request.GET.getlist("ct")
        pk_list = request.GET.getlist("pk")

        if not ct_list or not pk_list:
            return JsonResponse({"error": "ct and pk required"}, status=400)

        selections, objs, unsupported, raw_selections, obj_by_key, _unauthorized = (
            parse_selections_from_request(request)
        )
        payload = execute_ip_analysis_merge(
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
            request=request,
            include_html=not export_yaml,
            include_structured_data=export_yaml,
        )
        if export_yaml:
            return self._yaml_response(request, payload)
        return ip_analysis_json_response(payload)

    def _get_diff(self, request, *, export_yaml=False):
        sides = parse_diff_sides_from_request(request)
        if len(sides) < 2:
            return JsonResponse(
                {"error": "At least two diff sides required"}, status=400
            )

        payload = execute_ip_analysis_diff(
            sides=sides,
            request=request,
            include_html=not export_yaml,
            include_structured_data=export_yaml,
        )
        if export_yaml:
            return self._yaml_response(request, payload)
        return ip_analysis_json_response(payload)

    def _yaml_response(self, request, payload):
        export_context = parse_export_context_from_request(request)
        child_objects = build_ipa_export_child_objects(payload)
        document = build_ipa_export_document(
            payload,
            export_context=export_context,
            child_objects=child_objects,
        )
        yaml_text = serialize_ipa_export_yaml(document)
        filename = ipa_export_filename(payload, export_context=export_context)
        response = HttpResponse(yaml_text, content_type="text/yaml; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
