"""REST API for ``nsm_config`` stored in ``CustomObjectType.comments``."""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from netbox_nsm.api.serializers_.nsm_config import (
    NsmConfigApiSerializer,
    NsmConfigDocumentSerializer,
)
from netbox_nsm.objects.nsm_config import (
    clear_nsm_config_from_cot_comments,
    parse_nsm_config_document_from_comments,
    save_nsm_config_document_for_cot,
)
from netbox_nsm.objects.nsm_config_permissions import (
    nsm_config_change_permission,
    nsm_config_view_permission,
)
from netbox_nsm.rulebooks.permissions import can_change_rulebook, can_view_rulebook

__all__ = ("NsmConfigApiView",)


def _get_cot_or_404(slug: str):
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError as exc:
        raise NotFound() from exc
    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is None:
        raise NotFound()
    return cot


def _is_rulebook_slug(slug: str) -> bool:
    return slug.startswith("nsm_rb_")


def _check_permission(user, cot, slug: str, *, write: bool = False) -> None:
    if _is_rulebook_slug(slug):
        allowed = can_change_rulebook(user, cot) if write else can_view_rulebook(user, cot)
        if not allowed:
            raise PermissionDenied("Missing rulebook permission for this COT.")
        return
    perm = nsm_config_change_permission() if write else nsm_config_view_permission()
    if not user.has_perm(perm):
        raise PermissionDenied(f"Missing permission: {perm}")


def _save_nsm_config(cot, document: dict) -> None:
    """Persist *document* and surface model-level validation as HTTP 400."""
    try:
        save_nsm_config_document_for_cot(cot, document)
    except DjangoValidationError as exc:
        raise DRFValidationError(_validation_error_detail(exc)) from exc


def _validation_error_detail(exc: DjangoValidationError):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    messages = getattr(exc, "messages", None)
    if messages:
        return messages if len(messages) > 1 else messages[0]
    return str(exc)


def _serialize_cot(cot) -> dict:
    return {
        "slug": cot.slug,
        "custom_object_type_id": cot.pk,
        "nsm_config": parse_nsm_config_document_from_comments(cot.comments or ""),
        "comments": cot.comments or "",
    }


class NsmConfigApiView(APIView):
    """Read and update ``nsm_config`` on a ``CustomObjectType`` (by slug)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="netbox_nsm_nsm_config_retrieve",
        responses={200: NsmConfigApiSerializer},
    )
    def get(self, request, slug: str):
        cot = _get_cot_or_404(slug)
        _check_permission(request.user, cot, slug)
        return Response(_serialize_cot(cot))

    @extend_schema(
        operation_id="netbox_nsm_nsm_config_partial_update",
        request=NsmConfigDocumentSerializer,
        responses={200: NsmConfigApiSerializer},
    )
    def patch(self, request, slug: str):
        cot = _get_cot_or_404(slug)
        _check_permission(request.user, cot, slug, write=True)
        serializer = NsmConfigDocumentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        _save_nsm_config(cot, serializer.validated_data)
        cot.refresh_from_db()
        return Response(_serialize_cot(cot))

    @extend_schema(
        operation_id="netbox_nsm_nsm_config_update",
        request=NsmConfigDocumentSerializer,
        responses={200: NsmConfigApiSerializer},
    )
    def put(self, request, slug: str):
        cot = _get_cot_or_404(slug)
        _check_permission(request.user, cot, slug, write=True)
        serializer = NsmConfigDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _save_nsm_config(
            cot,
            {
                "rule_view": None,
                "object_builder": None,
                "rulebook": None,
                **serializer.validated_data,
            },
        )
        cot.refresh_from_db()
        return Response(_serialize_cot(cot))

    @extend_schema(
        operation_id="netbox_nsm_nsm_config_destroy",
        responses={204: None},
    )
    def delete(self, request, slug: str):
        cot = _get_cot_or_404(slug)
        _check_permission(request.user, cot, slug, write=True)
        clear_nsm_config_from_cot_comments(cot)
        return Response(status=status.HTTP_204_NO_CONTENT)
