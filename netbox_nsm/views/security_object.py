from django.shortcuts import get_object_or_404

from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from netbox_nsm.filtersets import SecurityObjectFilterSet, SecurityObjectAssignmentFilterSet
from netbox_nsm.forms import (
    SecurityObjectBulkEditForm,
    SecurityObjectFilterForm,
    SecurityObjectForm,
    SecurityObjectAssignmentForm,
    SecurityObjectAssignmentFilterForm,
)
from django.db.models import Q

from netbox_nsm.models import SecurityObject, SecurityObjectAssignment, SecurityPolicyRule
from netbox_nsm.tables import SecurityObjectTable, SecurityObjectAssignmentTable


@register_model_view(SecurityObject)
class ObjectCustomView(generic.ObjectView):
    queryset = SecurityObject.objects.prefetch_related("custom_type", "tags")
    template_name = "netbox_nsm/securityobject_area.html"

    def get_extra_context(self, request, instance):
        # Filter out meta entries (e.g. {'__meta__': True, 'hide_table_data': True})
        # that don't have a 'name' key, so the template never crashes on them.
        raw_defs = (instance.custom_type.field_definitions or []) if instance.custom_type else []
        field_defs = [fd for fd in raw_defs if fd.get("name")]
        normalized = {fd["name"]: instance.field_data.get(fd["name"], "") for fd in field_defs}
        rendered_comments = instance.render_comments() if hasattr(instance, "render_comments") else (instance.comments or "")
        return {
            "field_defs": field_defs,
            "normalized_field_data": normalized,
            "rendered_comments": rendered_comments,
        }


@register_model_view(SecurityObject, "list", path="", detail=False)
class ObjectCustomListView(generic.ObjectListView):
    queryset = SecurityObject.objects.prefetch_related("custom_type", "tags")
    filterset = SecurityObjectFilterSet
    filterset_form = SecurityObjectFilterForm
    table = SecurityObjectTable


@register_model_view(SecurityObject, "add", detail=False)
@register_model_view(SecurityObject, "edit")
class ObjectCustomEditView(generic.ObjectEditView):
    queryset = SecurityObject.objects.all()
    form = SecurityObjectForm


@register_model_view(SecurityObject, "delete")
class ObjectCustomDeleteView(generic.ObjectDeleteView):
    queryset = SecurityObject.objects.all()


@register_model_view(SecurityObject, "bulk_edit", path="edit", detail=False)
class ObjectCustomBulkEditView(generic.BulkEditView):
    queryset = SecurityObject.objects.all()
    filterset = SecurityObjectFilterSet
    table = SecurityObjectTable
    form = SecurityObjectBulkEditForm


@register_model_view(SecurityObject, "bulk_delete", path="delete", detail=False)
class ObjectCustomBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityObject.objects.all()
    table = SecurityObjectTable


# ── SecurityObjectAssignment ──────────────────────────────────────────────

def _rules_for_object(obj):
    return SecurityPolicyRule.objects.filter(
        Q(custom_srcdst_objects=obj)
        | Q(destination_custom_objects=obj)
        | Q(custom_service_objects=obj)
        | Q(custom_action_objects=obj)
    ).distinct()


@register_model_view(SecurityObject, "assignments")
class ObjectCustomAssignmentsView(generic.ObjectChildrenView):
    queryset = SecurityObject.objects.all()
    child_model = SecurityObjectAssignment
    table = SecurityObjectAssignmentTable
    filterset = SecurityObjectAssignmentFilterSet
    template_name = "netbox_nsm/securityobject_assignments.html"
    tab = ViewTab(
        label=_("Assignments"),
        badge=lambda obj: _rules_for_object(obj).count(),
        weight=200,
        hide_if_empty=False,
    )

    def get_children(self, request, parent):
        return SecurityObjectAssignment.objects.filter(custom_object=parent).select_related(
            "assigned_object_type"
        )

    def get_extra_context(self, request, instance):
        rules = (
            _rules_for_object(instance)
            .select_related("rulebook")
            .order_by("rulebook__name", "index", "name")
        )
        return {"firewall_rules": rules}


@register_model_view(SecurityObjectAssignment, "list", path="", detail=False)
class SecurityObjectAssignmentListView(generic.ObjectListView):
    queryset = SecurityObjectAssignment.objects.select_related(
        "custom_object__custom_type", "assigned_object_type"
    )
    filterset = SecurityObjectAssignmentFilterSet
    filterset_form = SecurityObjectAssignmentFilterForm
    table = SecurityObjectAssignmentTable


@register_model_view(SecurityObjectAssignment, "add", detail=False)
@register_model_view(SecurityObjectAssignment, "edit")
class SecurityObjectAssignmentEditView(generic.ObjectEditView):
    queryset = SecurityObjectAssignment.objects.all()
    form = SecurityObjectAssignmentForm

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


@register_model_view(SecurityObjectAssignment, "delete")
class SecurityObjectAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = SecurityObjectAssignment.objects.all()


@register_model_view(SecurityObjectAssignment, "bulk_delete", path="delete", detail=False)
class SecurityObjectAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityObjectAssignment.objects.all()
    table = SecurityObjectAssignmentTable



