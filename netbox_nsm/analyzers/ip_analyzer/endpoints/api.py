"""
JSON API for the floating IP Analyzer applet.

GET /plugins/netbox-nsm/api/ip-analyzer/?ct=<id>&pk=<id>&ct=...&pk=...
"""

from __future__ import annotations

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from django.views import View

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service import (
    execute_ip_analyzer_diff,
    execute_ip_analyzer_merge,
    ip_analyzer_json_response,
    parse_diff_sides_from_request,
    parse_selections_from_request,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_perf import (
    build_ipa_cache_key,
    cached_ipa_payload,
    get_ipa_analyzer_cache_timeout,
    ipa_lazy_context,
    parse_lazy_flag,
    parse_refresh_flag,
    should_bypass_ipa_cache,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_yaml_export import (
    build_ipa_export_child_objects,
    build_ipa_export_document,
    ipa_export_filename,
    parse_export_context_from_request,
    serialize_ipa_export_yaml,
)

__all__ = ("IpAnalyzerApiView",)

logger = logging.getLogger(__name__)


class IpAnalyzerApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        try:
            return self._get(request)
        except Exception as exc:
            logger.exception("IP analyzer UI API failed")
            detail = str(exc).strip() or exc.__class__.__name__
            return JsonResponse(
                {
                    "error": _("Analyzer failed: %(detail)s") % {"detail": detail},
                    "detail": detail,
                },
                status=500,
            )

    def _get(self, request):
        mode = (request.GET.get("mode") or "merge").strip().lower()
        export_yaml = (request.GET.get("format") or "").strip().lower() == "yaml"
        lazy = parse_lazy_flag(request)
        refresh = parse_refresh_flag(request)

        if mode == "diff":
            return self._get_diff(
                request, export_yaml=export_yaml, lazy=lazy, refresh=refresh
            )

        ct_list = request.GET.getlist("ct")
        pk_list = request.GET.getlist("pk")

        if not ct_list or not pk_list:
            return JsonResponse({"error": "ct and pk required"}, status=400)

        selections, objs, unsupported, raw_selections, obj_by_key, _unauthorized = (
            parse_selections_from_request(request)
        )
        payload = self._cached_merge_payload(
            request=request,
            lazy=lazy,
            refresh=refresh,
            export_yaml=export_yaml,
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
        )
        if export_yaml:
            return self._yaml_response(request, payload)
        return ip_analyzer_json_response(payload)

    def _cached_merge_payload(
        self,
        *,
        request,
        lazy,
        refresh,
        export_yaml,
        selections,
        objs,
        unsupported,
        raw_selections,
        obj_by_key,
    ):
        cache_timeout = get_ipa_analyzer_cache_timeout()
        bypass_cache = should_bypass_ipa_cache(
            lazy=lazy, refresh=refresh, cache_timeout=cache_timeout
        )

        def builder():
            with ipa_lazy_context(lazy):
                return execute_ip_analyzer_merge(
                    selections=selections,
                    objs=objs,
                    unsupported=unsupported,
                    raw_selections=raw_selections,
                    obj_by_key=obj_by_key,
                    request=request,
                    include_html=not export_yaml,
                    include_structured_data=export_yaml,
                    lazy=lazy,
                )

        if bypass_cache:
            payload = builder()
            payload["cached"] = False
            return payload

        cache_key = build_ipa_cache_key(
            user_id=getattr(request.user, "pk", None),
            mode="merge",
            lazy=lazy,
            variant="yaml" if export_yaml else "html",
            selections=selections,
        )
        payload, from_cache = cached_ipa_payload(cache_key, cache_timeout, builder)
        payload["cached"] = from_cache
        return payload

    def _get_diff(self, request, *, export_yaml=False, lazy=False, refresh=False):
        sides = parse_diff_sides_from_request(request)
        if len(sides) < 2:
            return JsonResponse(
                {"error": "At least two diff sides required"}, status=400
            )

        payload = self._cached_diff_payload(
            request=request,
            sides=sides,
            lazy=lazy,
            refresh=refresh,
            export_yaml=export_yaml,
        )
        if export_yaml:
            return self._yaml_response(request, payload)
        return ip_analyzer_json_response(payload)

    def _cached_diff_payload(
        self,
        *,
        request,
        sides,
        lazy,
        refresh,
        export_yaml,
    ):
        cache_timeout = get_ipa_analyzer_cache_timeout()
        bypass_cache = should_bypass_ipa_cache(
            lazy=lazy, refresh=refresh, cache_timeout=cache_timeout
        )

        def builder():
            with ipa_lazy_context(lazy):
                return execute_ip_analyzer_diff(
                    sides=sides,
                    request=request,
                    include_html=not export_yaml,
                    include_structured_data=export_yaml,
                    lazy=lazy,
                )

        if bypass_cache:
            payload = builder()
            payload["cached"] = False
            return payload

        cache_key = build_ipa_cache_key(
            user_id=getattr(request.user, "pk", None),
            mode="diff",
            lazy=lazy,
            variant="yaml" if export_yaml else "html",
            sides=sides,
        )
        payload, from_cache = cached_ipa_payload(cache_key, cache_timeout, builder)
        payload["cached"] = from_cache
        return payload

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
