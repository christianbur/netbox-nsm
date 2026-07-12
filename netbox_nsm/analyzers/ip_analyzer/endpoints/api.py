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
    get_ipa_analyzer_timeout_ms,
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
    parse_export_expanded_refs_from_request,
    serialize_ipa_export_yaml,
)

__all__ = ("IpAnalyzerApiView",)

logger = logging.getLogger(__name__)


class IpAnalyzerApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        mode = (request.GET.get("mode") or "merge").strip().lower()
        export_yaml = (request.GET.get("format") or "").strip().lower() == "yaml"
        lazy = parse_lazy_flag(request)
        refresh = parse_refresh_flag(request)
        try:
            return self._get(
                request,
                mode=mode,
                export_yaml=export_yaml,
                lazy=lazy,
                refresh=refresh,
            )
        except Exception as exc:
            logger.exception("IP analyzer UI API failed")
            detail = str(exc).strip() or exc.__class__.__name__
            status_code = self._error_status_code(exc)
            return JsonResponse(
                {
                    "error": _("Analyzer failed: %(detail)s") % {"detail": detail},
                    "detail": detail,
                    "debug_info": self._build_debug_info(
                        request,
                        mode=mode,
                        export_yaml=export_yaml,
                        lazy=lazy,
                        refresh=refresh,
                        exc=exc,
                        detail=detail,
                        status_code=status_code,
                    ),
                },
                status=status_code,
            )

    def _get(self, request, *, mode, export_yaml, lazy, refresh):
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

    @staticmethod
    def _error_status_code(exc):
        if isinstance(exc, TimeoutError):
            return 504
        return 500

    def _build_debug_info(
        self,
        request,
        *,
        mode,
        export_yaml,
        lazy,
        refresh,
        exc,
        detail,
        status_code,
    ):
        query = request.GET
        ct_list = query.getlist("ct")
        pk_list = query.getlist("pk")
        side_keys = {
            key.split("_", 1)[0]
            for key in query.keys()
            if key.startswith("s") and "_" in key
        }
        return {
            "mode": mode,
            "export_yaml": bool(export_yaml),
            "lazy": bool(lazy),
            "refresh": bool(refresh),
            "status_code": int(status_code),
            "exception_class": exc.__class__.__name__,
            "detail": detail,
            "selection_counts": {
                "ct": len(ct_list),
                "pk": len(pk_list),
                "diff_sides": len(side_keys),
            },
            "timeouts": {
                "analyzer_timeout_ms": get_ipa_analyzer_timeout_ms(),
                "cache_timeout": get_ipa_analyzer_cache_timeout(),
            },
            "query_keys": sorted(query.keys()),
        }

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
        bypass_cache = export_yaml or should_bypass_ipa_cache(
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
        bypass_cache = export_yaml or should_bypass_ipa_cache(
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
        view_only = (request.GET.get("view_only") or "").strip() in {
            "1",
            "true",
            "yes",
            "on",
        }
        expanded_refs = (
            parse_export_expanded_refs_from_request(request) if view_only else None
        )
        child_objects = build_ipa_export_child_objects(
            payload,
            expanded_refs=expanded_refs,
        )
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
