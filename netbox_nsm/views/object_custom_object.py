from django.shortcuts import get_object_or_404

from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from netbox_nsm.filtersets import ObjectCustomObjectFilterSet, ObjectCustomObjectAssignmentFilterSet
from netbox_nsm.forms import (
    ObjectCustomObjectBulkEditForm,
    ObjectCustomObjectFilterForm,
    ObjectCustomObjectForm,
    ObjectCustomObjectAssignmentForm,
    ObjectCustomObjectAssignmentFilterForm,
)
from netbox_nsm.models import ObjectCustomObject, ObjectCustomObjectAssignment
from netbox_nsm.tables import ObjectCustomObjectTable, ObjectCustomObjectAssignmentTable


@register_model_view(ObjectCustomObject)
class ObjectCustomView(generic.ObjectView):
    queryset = ObjectCustomObject.objects.prefetch_related("custom_type", "tags")
    template_name = "netbox_nsm/objectcustom.html"

    def get_extra_context(self, request, instance):
        # Build a normalized dict that always contains every key from field_definitions
        # so the template's get_item filter never raises a KeyError for missing fields.
        field_defs = (instance.custom_type.field_definitions or []) if instance.custom_type else []
        normalized = {fd["name"]: instance.field_data.get(fd["name"], "") for fd in field_defs}
        return {"normalized_field_data": normalized}


@register_model_view(ObjectCustomObject, "list", path="", detail=False)
class ObjectCustomListView(generic.ObjectListView):
    queryset = ObjectCustomObject.objects.prefetch_related("custom_type", "tags")
    filterset = ObjectCustomObjectFilterSet
    filterset_form = ObjectCustomObjectFilterForm
    table = ObjectCustomObjectTable


@register_model_view(ObjectCustomObject, "add", detail=False)
@register_model_view(ObjectCustomObject, "edit")
class ObjectCustomEditView(generic.ObjectEditView):
    queryset = ObjectCustomObject.objects.all()
    form = ObjectCustomObjectForm


@register_model_view(ObjectCustomObject, "delete")
class ObjectCustomDeleteView(generic.ObjectDeleteView):
    queryset = ObjectCustomObject.objects.all()


@register_model_view(ObjectCustomObject, "bulk_edit", path="edit", detail=False)
class ObjectCustomBulkEditView(generic.BulkEditView):
    queryset = ObjectCustomObject.objects.all()
    filterset = ObjectCustomObjectFilterSet
    table = ObjectCustomObjectTable
    form = ObjectCustomObjectBulkEditForm


@register_model_view(ObjectCustomObject, "bulk_delete", path="delete", detail=False)
class ObjectCustomBulkDeleteView(generic.BulkDeleteView):
    queryset = ObjectCustomObject.objects.all()
    table = ObjectCustomObjectTable


# ── ObjectCustomObjectAssignment ──────────────────────────────────────────────

@register_model_view(ObjectCustomObject, "assignments")
class ObjectCustomAssignmentsView(generic.ObjectChildrenView):
    queryset = ObjectCustomObject.objects.all()
    child_model = ObjectCustomObjectAssignment
    table = ObjectCustomObjectAssignmentTable
    filterset = ObjectCustomObjectAssignmentFilterSet
    tab = ViewTab(
        label=_("Assignments"),
        badge=lambda obj: obj.assignments.count(),
        weight=200,
        hide_if_empty=False,
    )

    def get_children(self, request, parent):
        return ObjectCustomObjectAssignment.objects.filter(custom_object=parent).select_related(
            "assigned_object_type"
        )


@register_model_view(ObjectCustomObjectAssignment, "list", path="", detail=False)
class ObjectCustomObjectAssignmentListView(generic.ObjectListView):
    queryset = ObjectCustomObjectAssignment.objects.select_related(
        "custom_object__custom_type", "assigned_object_type"
    )
    filterset = ObjectCustomObjectAssignmentFilterSet
    filterset_form = ObjectCustomObjectAssignmentFilterForm
    table = ObjectCustomObjectAssignmentTable


@register_model_view(ObjectCustomObjectAssignment, "add", detail=False)
@register_model_view(ObjectCustomObjectAssignment, "edit")
class ObjectCustomObjectAssignmentEditView(generic.ObjectEditView):
    queryset = ObjectCustomObjectAssignment.objects.all()
    form = ObjectCustomObjectAssignmentForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            from django.contrib.contenttypes.models import ContentType
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


@register_model_view(ObjectCustomObjectAssignment, "delete")
class ObjectCustomObjectAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = ObjectCustomObjectAssignment.objects.all()


@register_model_view(ObjectCustomObjectAssignment, "bulk_delete", path="delete", detail=False)
class ObjectCustomObjectAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = ObjectCustomObjectAssignment.objects.all()
    table = ObjectCustomObjectAssignmentTable
