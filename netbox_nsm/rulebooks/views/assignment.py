"""CRUD views for COT rulebook host assignments."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import CotRulebookAssignmentFilterSet
from netbox_nsm.forms import CotRulebookAssignmentFilterForm, CotRulebookAssignmentForm
from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.tables import CotRulebookAssignmentTable

__all__ = (
    "CotRulebookAssignmentBulkDeleteView",
    "CotRulebookAssignmentDeleteView",
    "CotRulebookAssignmentEditView",
    "CotRulebookAssignmentListView",
)


@register_model_view(CotRulebookAssignment, "list", path="", detail=False)
class CotRulebookAssignmentListView(generic.ObjectListView):
    queryset = CotRulebookAssignment.objects.select_related("assigned_object_type")
    filterset = CotRulebookAssignmentFilterSet
    filterset_form = CotRulebookAssignmentFilterForm
    table = CotRulebookAssignmentTable
    actions = {"export": {"view"}}


@register_model_view(CotRulebookAssignment, "add", detail=False)
@register_model_view(CotRulebookAssignment, "edit")
class CotRulebookAssignmentEditView(generic.ObjectEditView):
    queryset = CotRulebookAssignment.objects.all()
    form = CotRulebookAssignmentForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            content_type = get_object_or_404(
                ContentType, pk=request.GET.get("assigned_object_type")
            )
            instance.assigned_object = get_object_or_404(
                content_type.model_class(), pk=request.GET.get("assigned_object_id")
            )
        return instance

    def get_extra_addanother_params(self, request):
        return {
            "assigned_object_type": request.GET.get("assigned_object_type"),
            "assigned_object_id": request.GET.get("assigned_object_id"),
        }


@register_model_view(CotRulebookAssignment, "delete")
class CotRulebookAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = CotRulebookAssignment.objects.all()


@register_model_view(CotRulebookAssignment, "bulk_delete", path="delete", detail=False)
class CotRulebookAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = CotRulebookAssignment.objects.all()
    table = CotRulebookAssignmentTable
