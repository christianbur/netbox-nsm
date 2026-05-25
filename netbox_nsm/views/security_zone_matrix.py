from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import (
    SecurityZoneMatrixFilterSet,
    SecurityZoneMatrixPolicyFilterSet,
    SecurityZoneMatrixCellFilterSet,
)
from netbox_nsm.forms import (
    SecurityZoneMatrixForm,
    SecurityZoneMatrixFilterForm,
    SecurityZoneMatrixImportForm,
    SecurityZoneMatrixBulkEditForm,
    SecurityZoneMatrixPolicyForm,
    SecurityZoneMatrixPolicyFilterForm,
    SecurityZoneMatrixPolicyImportForm,
    SecurityZoneMatrixPolicyBulkEditForm,
    SecurityZoneMatrixCellForm,
    SecurityZoneMatrixCellFilterForm,
)
from netbox_nsm.models import (
    SecurityZone,
    SecurityZoneMatrix,
    SecurityZoneMatrixPolicy,
    SecurityZoneMatrixCell,
)
from netbox_nsm.tables import (
    SecurityZoneMatrixTable,
    SecurityZoneMatrixPolicyTable,
    SecurityZoneMatrixCellTable,
)

__all__ = (
    "SecurityZoneMatrixView",
    "SecurityZoneMatrixListView",
    "SecurityZoneMatrixEditView",
    "SecurityZoneMatrixDeleteView",
    "SecurityZoneMatrixBulkEditView",
    "SecurityZoneMatrixBulkDeleteView",
    "SecurityZoneMatrixBulkImportView",
    "SecurityZoneMatrixPolicyView",
    "SecurityZoneMatrixPolicyListView",
    "SecurityZoneMatrixPolicyEditView",
    "SecurityZoneMatrixPolicyDeleteView",
    "SecurityZoneMatrixPolicyBulkEditView",
    "SecurityZoneMatrixPolicyBulkDeleteView",
    "SecurityZoneMatrixPolicyBulkImportView",
    "SecurityZoneMatrixCellView",
    "SecurityZoneMatrixCellListView",
    "SecurityZoneMatrixCellEditView",
    "SecurityZoneMatrixCellDeleteView",
    "SecurityZoneMatrixCellBulkDeleteView",
)


@register_model_view(SecurityZoneMatrix)
class SecurityZoneMatrixView(generic.ObjectView):
    queryset = SecurityZoneMatrix.annotated_queryset().prefetch_related("roles")
    template_name = "netbox_nsm/securityzonematrix.html"

    def get_extra_context(self, request, instance):
        def _clean_id_list(values):
            cleaned = []
            for raw in values:
                for piece in str(raw).replace(",", "&").split("&"):
                    candidate = piece.split("?", 1)[0].strip()
                    if candidate.isdigit() and candidate not in cleaned:
                        cleaned.append(candidate)
            return cleaned

        zones_qs = SecurityZone.objects.filter(
            roles__in=instance.roles.all()
        ).prefetch_related("roles").distinct().order_by("name")
        all_policies = list(
            SecurityZoneMatrixPolicy.objects.filter(cells__matrix=instance)
            .distinct()
            .order_by("name")
        )

        source_zone_ids = _clean_id_list(request.GET.getlist("source_zone_id"))
        destination_zone_ids = _clean_id_list(request.GET.getlist("destination_zone_id"))
        policy_ids = _clean_id_list(request.GET.getlist("policy_id"))

        cells = (
            SecurityZoneMatrixCell.objects.filter(matrix=instance)
            .select_related("source_zone", "destination_zone", "policy")
            .order_by("source_zone__name", "destination_zone__name")
        )

        if source_zone_ids:
            cells = cells.filter(source_zone_id__in=source_zone_ids)
        if destination_zone_ids:
            cells = cells.filter(destination_zone_id__in=destination_zone_ids)
        if policy_ids:
            cells = cells.filter(policy_id__in=policy_ids)

        source_zones = list(zones_qs)
        destination_zones = list(zones_qs)

        if not source_zone_ids and policy_ids:
            source_ids = cells.values_list("source_zone_id", flat=True).distinct()
            source_zones = list(zones_qs.filter(pk__in=source_ids))
        if not destination_zone_ids and policy_ids:
            destination_ids = cells.values_list("destination_zone_id", flat=True).distinct()
            destination_zones = list(zones_qs.filter(pk__in=destination_ids))

        if source_zone_ids:
            source_zones = list(zones_qs.filter(pk__in=source_zone_ids))
        if destination_zone_ids:
            destination_zones = list(zones_qs.filter(pk__in=destination_zone_ids))

        cell_map = {
            (cell.source_zone_id, cell.destination_zone_id): cell for cell in cells
        }

        matrix_rows = []
        for source_zone in source_zones:
            row_cells = []
            for destination_zone in destination_zones:
                row_cells.append(
                    {
                        "destination_zone": destination_zone,
                        "cell": cell_map.get((source_zone.pk, destination_zone.pk)),
                    }
                )
            matrix_rows.append(
                {
                    "source_zone": source_zone,
                    "cells": row_cells,
                }
            )

        policy_ids_used = {
            cell.policy_id for cell in cell_map.values() if cell is not None
        }
        policy_legend = list(
            SecurityZoneMatrixPolicy.objects.filter(pk__in=policy_ids_used).order_by("name")
        )

        return {
            "source_zones": source_zones,
            "destination_zones": destination_zones,
            "filter_zone_options": list(zones_qs),
            "filter_policy_options": all_policies,
            "matrix_rows": matrix_rows,
            "cell_map": cell_map,
            "source_zone_ids": source_zone_ids,
            "destination_zone_ids": destination_zone_ids,
            "policy_ids": policy_ids,
            "policy_legend": policy_legend,
            "cell_filter_form": SecurityZoneMatrixCellFilterForm(
                data=request.GET or None
            ),
        }


@register_model_view(SecurityZoneMatrix, "list", path="", detail=False)
class SecurityZoneMatrixListView(generic.ObjectListView):
    queryset = SecurityZoneMatrix.annotated_queryset().prefetch_related("roles")
    filterset = SecurityZoneMatrixFilterSet
    filterset_form = SecurityZoneMatrixFilterForm
    table = SecurityZoneMatrixTable


@register_model_view(SecurityZoneMatrix, "add", detail=False)
@register_model_view(SecurityZoneMatrix, "edit")
class SecurityZoneMatrixEditView(generic.ObjectEditView):
    queryset = SecurityZoneMatrix.objects.all()
    form = SecurityZoneMatrixForm


@register_model_view(SecurityZoneMatrix, "delete")
class SecurityZoneMatrixDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZoneMatrix.objects.all()


@register_model_view(SecurityZoneMatrix, "bulk_edit", path="edit", detail=False)
class SecurityZoneMatrixBulkEditView(generic.BulkEditView):
    queryset = SecurityZoneMatrix.objects.all()
    filterset = SecurityZoneMatrixFilterSet
    table = SecurityZoneMatrixTable
    form = SecurityZoneMatrixBulkEditForm


@register_model_view(SecurityZoneMatrix, "bulk_delete", path="delete", detail=False)
class SecurityZoneMatrixBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZoneMatrix.objects.all()
    table = SecurityZoneMatrixTable


@register_model_view(SecurityZoneMatrix, "bulk_import", detail=False)
class SecurityZoneMatrixBulkImportView(generic.BulkImportView):
    queryset = SecurityZoneMatrix.objects.all()
    model_form = SecurityZoneMatrixImportForm


@register_model_view(SecurityZoneMatrixPolicy)
class SecurityZoneMatrixPolicyView(generic.ObjectView):
    queryset = SecurityZoneMatrixPolicy.objects.all()


@register_model_view(SecurityZoneMatrixPolicy, "list", path="", detail=False)
class SecurityZoneMatrixPolicyListView(generic.ObjectListView):
    queryset = SecurityZoneMatrixPolicy.objects.all()
    filterset = SecurityZoneMatrixPolicyFilterSet
    filterset_form = SecurityZoneMatrixPolicyFilterForm
    table = SecurityZoneMatrixPolicyTable


@register_model_view(SecurityZoneMatrixPolicy, "add", detail=False)
@register_model_view(SecurityZoneMatrixPolicy, "edit")
class SecurityZoneMatrixPolicyEditView(generic.ObjectEditView):
    queryset = SecurityZoneMatrixPolicy.objects.all()
    form = SecurityZoneMatrixPolicyForm


@register_model_view(SecurityZoneMatrixPolicy, "delete")
class SecurityZoneMatrixPolicyDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZoneMatrixPolicy.objects.all()


@register_model_view(SecurityZoneMatrixPolicy, "bulk_edit", path="edit", detail=False)
class SecurityZoneMatrixPolicyBulkEditView(generic.BulkEditView):
    queryset = SecurityZoneMatrixPolicy.objects.all()
    filterset = SecurityZoneMatrixPolicyFilterSet
    table = SecurityZoneMatrixPolicyTable
    form = SecurityZoneMatrixPolicyBulkEditForm


@register_model_view(SecurityZoneMatrixPolicy, "bulk_delete", path="delete", detail=False)
class SecurityZoneMatrixPolicyBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZoneMatrixPolicy.objects.all()
    table = SecurityZoneMatrixPolicyTable


@register_model_view(SecurityZoneMatrixPolicy, "bulk_import", detail=False)
class SecurityZoneMatrixPolicyBulkImportView(generic.BulkImportView):
    queryset = SecurityZoneMatrixPolicy.objects.all()
    model_form = SecurityZoneMatrixPolicyImportForm


@register_model_view(SecurityZoneMatrixCell)
class SecurityZoneMatrixCellView(generic.ObjectView):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )


@register_model_view(SecurityZoneMatrixCell, "list", path="", detail=False)
class SecurityZoneMatrixCellListView(generic.ObjectListView):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )
    filterset = SecurityZoneMatrixCellFilterSet
    filterset_form = SecurityZoneMatrixCellFilterForm
    table = SecurityZoneMatrixCellTable
    actions = {"export": {"view"}}


@register_model_view(SecurityZoneMatrixCell, "add", detail=False)
@register_model_view(SecurityZoneMatrixCell, "edit")
class SecurityZoneMatrixCellEditView(generic.ObjectEditView):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )
    form = SecurityZoneMatrixCellForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            instance.matrix = get_object_or_404(
                SecurityZoneMatrix, pk=request.GET.get("matrix_id")
            )
            instance.source_zone = get_object_or_404(
                SecurityZone, pk=request.GET.get("source_zone_id")
            )
            instance.destination_zone = get_object_or_404(
                SecurityZone, pk=request.GET.get("destination_zone_id")
            )
            policy_id = request.GET.get("policy_id")
            if policy_id:
                instance.policy = get_object_or_404(SecurityZoneMatrixPolicy, pk=policy_id)
        return instance

    def get_extra_addanother_params(self, request):
        return {
            "matrix_id": request.GET.get("matrix_id"),
            "source_zone_id": request.GET.get("source_zone_id"),
            "destination_zone_id": request.GET.get("destination_zone_id"),
            "policy_id": request.GET.get("policy_id"),
        }


@register_model_view(SecurityZoneMatrixCell, "delete")
class SecurityZoneMatrixCellDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )


@register_model_view(SecurityZoneMatrixCell, "bulk_delete", path="delete", detail=False)
class SecurityZoneMatrixCellBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZoneMatrixCell.objects.select_related(
        "matrix", "source_zone", "destination_zone", "policy"
    )
    table = SecurityZoneMatrixCellTable
