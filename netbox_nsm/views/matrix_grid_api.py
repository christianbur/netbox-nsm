"""Lazy JSON API for the zone matrix AG Grid."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from netbox_nsm.matrix_grid_service import (
    MATRIX_GRID_BLOCK_SIZE,
    fetch_matrix_grid_page,
)
from netbox_nsm.models import Rulebook, RulebookTypeChoices

__all__ = ("RulebookMatrixGridApiView",)


class RulebookMatrixGridApiView(LoginRequiredMixin, View):
    """
    GET /plugins/netbox-nsm/api/rulebooks/<pk>/matrix-grid/

    Forwards obj_type, mode, and axis filter query params from the matrix tab.
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rulebook"):
            return HttpResponseForbidden()

        instance = get_object_or_404(Rulebook, pk=pk)
        if instance.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
            return JsonResponse({"error": "not a security rules rulebook"}, status=404)

        import netbox_nsm.views.rulebook as rulebook_views

        try:
            start_row = int(request.GET.get("startRow", 0))
        except (TypeError, ValueError):
            start_row = 0
        try:
            end_row = int(request.GET.get("endRow", start_row + MATRIX_GRID_BLOCK_SIZE))
        except (TypeError, ValueError):
            end_row = start_row + MATRIX_GRID_BLOCK_SIZE

        payload = fetch_matrix_grid_page(
            request,
            instance,
            start_row=start_row,
            end_row=end_row,
            view_helpers=rulebook_views,
        )
        response = JsonResponse(payload)
        response["Cache-Control"] = "private, max-age=0, no-cache"
        return response
