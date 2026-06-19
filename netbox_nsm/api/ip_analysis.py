"""
REST API for IP address analysis (NetBox DRF, token-authenticated).

GET/POST /api/plugins/netbox-nsm/ip-analysis/

Scope: resolve **address-analyzable** objects to IP trees or multi-side diffs.
Supported targets are NetBox IPAM objects (prefix, IP address, IP range) and COT
address types such as ``nsm_address`` / address groups — identified generically via
``content_type`` + ``id``. This endpoint does **not** expose COT rulebook or rule CRUD;
use ``netbox-custom-objects`` for policy object data.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from netbox_nsm.analysis.ip_analysis_service import (
    execute_ip_analysis_diff,
    execute_ip_analysis_merge,
    parse_diff_sides_from_body,
    parse_diff_sides_from_request,
    parse_object_refs,
    parse_selections_from_request,
)

__all__ = ("IpAnalysisRestApiView",)


class IpAnalysisRestApiView(APIView):
    """Resolve address objects to IP trees or multi-side diffs (JSON only)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="netbox_nsm_ip_analysis_retrieve",
        description=(
            "Analyze one or more address-analyzable objects: NetBox IPAM (prefix, "
            "IP address, IP range) or COT address types (e.g. ``nsm_address``, address "
            "groups). Objects are referenced by ``content_type`` id and object ``pk`` "
            "(query params ``ct``/``pk``). Use repeated ``ct``/``pk`` for merge mode, "
            "or ``mode=diff`` with ``a_ct``/``a_pk`` and ``b_ct``/``b_pk`` (or indexed "
            "``s0_ct``/``s0_pk``, …). Returns structured JSON (``addr_analysis``, counts); "
            "no HTML. For the UI applet use "
            "``GET /plugins/netbox-nsm/api/ip-analysis/`` instead."
        ),
        responses={200: dict},
        examples=[
            OpenApiExample(
                "Merge two objects",
                value=None,
                parameter_only=[
                    ("ct", "10"),
                    ("pk", "42"),
                    ("ct", "10"),
                    ("pk", "43"),
                ],
            ),
            OpenApiExample(
                "Diff two sides",
                value=None,
                parameter_only=[
                    ("mode", "diff"),
                    ("a_ct", "10"),
                    ("a_pk", "1"),
                    ("b_ct", "10"),
                    ("b_pk", "2"),
                ],
            ),
        ],
    )
    def get(self, request):
        mode = (request.query_params.get("mode") or "merge").strip().lower()
        if mode == "diff":
            return self._respond_diff(
                parse_diff_sides_from_request(request, user=request.user)
            )

        ct_list = request.query_params.getlist("ct")
        pk_list = request.query_params.getlist("pk")
        if not ct_list or not pk_list:
            return Response(
                {"detail": "ct and pk query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selections, objs, unsupported, raw_selections, obj_by_key, unauthorized = (
            parse_selections_from_request(request, user=request.user)
        )
        return self._respond_merge(
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
            unauthorized=unauthorized,
        )

    @extend_schema(
        operation_id="netbox_nsm_ip_analysis_create",
        description=(
            "Analyze objects from a JSON body. Merge mode accepts ``objects``; "
            "diff mode accepts ``sides`` (or legacy ``side_a``/``side_b``)."
        ),
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["merge", "diff"]},
                    "objects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "content_type": {"type": "integer"},
                                "id": {"type": "integer"},
                            },
                        },
                    },
                    "sides": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "objects": {"type": "array"},
                            },
                        },
                    },
                },
            }
        },
        responses={200: dict},
        examples=[
            OpenApiExample(
                "Merge via POST",
                value={
                    "mode": "merge",
                    "objects": [
                        {"content_type": 10, "id": 42},
                        {"content_type": 10, "id": 43},
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Diff via POST",
                value={
                    "mode": "diff",
                    "sides": [
                        {
                            "label": "Rule 2",
                            "objects": [{"content_type": 10, "id": 1}],
                        },
                        {
                            "label": "Rule 3",
                            "objects": [{"content_type": 10, "id": 2}],
                        },
                    ],
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        mode = (body.get("mode") or "merge").strip().lower()

        if mode == "diff":
            sides = parse_diff_sides_from_body(body, user=request.user)
            if len(sides) < 2:
                return Response(
                    {"detail": "At least two diff sides are required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return self._respond_diff(sides)

        refs = body.get("objects") or body.get("object_refs") or []
        if not refs:
            return Response(
                {"detail": "objects is required for merge mode."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        selections, objs, unsupported, raw_selections, obj_by_key, unauthorized = (
            parse_object_refs(refs, user=request.user)
        )
        return self._respond_merge(
            selections=selections,
            objs=objs,
            unsupported=unsupported,
            raw_selections=raw_selections,
            obj_by_key=obj_by_key,
            unauthorized=unauthorized,
        )

    def _respond_merge(self, **kwargs):
        payload = execute_ip_analysis_merge(**kwargs, include_html=False)
        return Response(self._clean_payload(payload))

    def _respond_diff(self, sides):
        payload = execute_ip_analysis_diff(sides=sides, include_html=False)
        return Response(self._clean_payload(payload))

    @staticmethod
    def _clean_payload(payload):
        return {key: value for key, value in payload.items() if value is not None}
