from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view, ViewTab

from dcim.models import Device, VirtualDeviceContext
from virtualization.models import VirtualMachine

from dcim.tables import DeviceTable, VirtualDeviceContextTable
from dcim.models import Interface

from dcim.tables import InterfaceTable
from virtualization.tables import VirtualMachineTable

from netbox_nsm.tables import (
    SecurityZoneTable,
    SecurityZoneAssignmentTable,
    SecurityZoneRoleTable,
)
from netbox_nsm.filtersets import (
    SecurityZoneRoleFilterSet,
    SecurityZoneFilterSet,
    SecurityZoneAssignmentFilterSet,
)

from netbox_nsm.models import SecurityZoneRole, SecurityZone, SecurityZoneAssignment
from netbox_nsm.forms import (
    SecurityZoneRoleFilterForm,
    SecurityZoneRoleForm,
    SecurityZoneRoleBulkEditForm,
    SecurityZoneRoleImportForm,
    SecurityZoneFilterForm,
    SecurityZoneForm,
    SecurityZoneBulkEditForm,
    SecurityZoneAssignmentForm,
    SecurityZoneImportForm,
    SecurityZoneAssignmentFilterForm,
)

__all__ = (
    "SecurityZoneRoleView",
    "SecurityZoneRoleListView",
    "SecurityZoneRoleEditView",
    "SecurityZoneRoleDeleteView",
    "SecurityZoneRoleBulkEditView",
    "SecurityZoneRoleBulkDeleteView",
    "SecurityZoneRoleBulkImportView",
    "SecurityZoneView",
    "SecurityZoneListView",
    "SecurityZoneEditView",
    "SecurityZoneDeleteView",
    "SecurityZoneBulkEditView",
    "SecurityZoneBulkDeleteView",
    "SecurityZoneBulkImportView",
    "SecurityZoneAssignmentEditView",
    "SecurityZoneAssignmentDeleteView",
    "SecurityZoneAssignmentListView",
    "SecurityZoneAssignmentBulkDeleteView",
)


@register_model_view(SecurityZoneRole)
class SecurityZoneRoleView(generic.ObjectView):
    queryset = SecurityZoneRole.annotated_queryset()
    template_name = "netbox_nsm/security_zone_role.html"


@register_model_view(SecurityZoneRole, "list", path="", detail=False)
class SecurityZoneRoleListView(generic.ObjectListView):
    queryset = SecurityZoneRole.annotated_queryset()
    filterset = SecurityZoneRoleFilterSet
    filterset_form = SecurityZoneRoleFilterForm
    table = SecurityZoneRoleTable


@register_model_view(SecurityZoneRole, "add", detail=False)
@register_model_view(SecurityZoneRole, "edit")
class SecurityZoneRoleEditView(generic.ObjectEditView):
    queryset = SecurityZoneRole.objects.all()
    form = SecurityZoneRoleForm


@register_model_view(SecurityZoneRole, "delete")
class SecurityZoneRoleDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZoneRole.objects.all()


@register_model_view(SecurityZoneRole, "bulk_edit", path="edit", detail=False)
class SecurityZoneRoleBulkEditView(generic.BulkEditView):
    queryset = SecurityZoneRole.objects.all()
    filterset = SecurityZoneRoleFilterSet
    table = SecurityZoneRoleTable
    form = SecurityZoneRoleBulkEditForm


@register_model_view(SecurityZoneRole, "bulk_delete", path="delete", detail=False)
class SecurityZoneRoleBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZoneRole.objects.all()
    table = SecurityZoneRoleTable


@register_model_view(SecurityZoneRole, "bulk_import", detail=False)
class SecurityZoneRoleBulkImportView(generic.BulkImportView):
    queryset = SecurityZoneRole.objects.all()
    model_form = SecurityZoneRoleImportForm


@register_model_view(SecurityZone)
class SecurityZoneView(generic.ObjectView):
    queryset = SecurityZone.annotated_queryset()
    template_name = "netbox_nsm/securityzone.html"

    def get_extra_context(self, request, instance):
        device_assignments_table = DeviceTable(
            Device.objects.filter(security_zones__zone=instance),
            orderable=False,
        )
        device_assignments_table.configure(request)
        virtual_device_assignments_table = VirtualDeviceContextTable(
            VirtualDeviceContext.objects.filter(security_zones__zone=instance),
            orderable=False,
        )
        virtual_device_assignments_table.configure(request)
        virtual_machine_assignments_table = VirtualMachineTable(
            VirtualMachine.objects.filter(security_zones__zone=instance),
            orderable=False,
        )
        virtual_machine_assignments_table.configure(request)
        interface_assignments_table = InterfaceTable(
            Interface.objects.filter(security_zones__zone=instance),
            orderable=False,
        )
        interface_assignments_table.configure(request)
        return {
            "device_assignments_table": device_assignments_table,
            "virtual_device_assignments_table": virtual_device_assignments_table,
            "virtual_machine_assignments_table": virtual_machine_assignments_table,
            "interface_assignments_table": interface_assignments_table,
        }


@register_model_view(SecurityZone, "assigned_objects")
class SecurityZoneAssignedObjectsView(generic.ObjectView):
    queryset = SecurityZone.objects.all()
    template_name = "netbox_nsm/assigned_objects.html"
    tab = ViewTab(
        label=_("Assigned Objects"),
        badge=lambda obj: SecurityZoneAssignment.objects.filter(zone=obj).count(),
        hide_if_empty=True,
    )

    def get_extra_context(self, request, instance):
        return {
            "assigned_objects_list_url": (
                reverse("plugins:netbox_nsm:securityzoneassignment_list")
                + f"?embedded=True&zone_id={instance.pk}"
            )
        }


@register_model_view(SecurityZone, "list", path="", detail=False)
class SecurityZoneListView(generic.ObjectListView):
    queryset = SecurityZone.annotated_queryset()
    filterset = SecurityZoneFilterSet
    filterset_form = SecurityZoneFilterForm
    table = SecurityZoneTable


@register_model_view(SecurityZone, "add", detail=False)
@register_model_view(SecurityZone, "edit")
class SecurityZoneEditView(generic.ObjectEditView):
    queryset = SecurityZone.objects.all()
    form = SecurityZoneForm


@register_model_view(SecurityZone, "delete")
class SecurityZoneDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZone.objects.all()


@register_model_view(SecurityZone, "bulk_edit", path="edit", detail=False)
class SecurityZoneBulkEditView(generic.BulkEditView):
    queryset = SecurityZone.objects.all()
    filterset = SecurityZoneFilterSet
    table = SecurityZoneTable
    form = SecurityZoneBulkEditForm


@register_model_view(SecurityZone, "bulk_delete", path="delete", detail=False)
class SecurityZoneBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZone.objects.all()
    table = SecurityZoneTable


@register_model_view(SecurityZone, "bulk_import", detail=False)
class SecurityZoneBulkImportView(generic.BulkImportView):
    queryset = SecurityZone.objects.all()
    model_form = SecurityZoneImportForm


@register_model_view(SecurityZoneAssignment, "list", path="", detail=False)
class SecurityZoneAssignmentListView(generic.ObjectListView):
    queryset = SecurityZoneAssignment.objects.all()
    filterset = SecurityZoneAssignmentFilterSet
    filterset_form = SecurityZoneAssignmentFilterForm
    table = SecurityZoneAssignmentTable
    actions = {
        "export": {"view"},
    }

    def get_table(self, data, request, bulk_actions=True):
        table = super().get_table(data, request, bulk_actions)
        if request.GET.get("zone_id"):
            table.columns.hide("zone")
            table.columns.hide("zone_color")
        return table


@register_model_view(SecurityZoneAssignment, "add", detail=False)
@register_model_view(SecurityZoneAssignment, "edit")
class SecurityZoneAssignmentEditView(generic.ObjectEditView):
    queryset = SecurityZoneAssignment.objects.all()
    form = SecurityZoneAssignmentForm

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


@register_model_view(SecurityZoneAssignment, "delete")
class SecurityZoneAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZoneAssignment.objects.all()


@register_model_view(SecurityZoneAssignment, "bulk_delete", path="delete", detail=False)
class SecurityZoneAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZoneAssignment.objects.all()
    table = SecurityZoneAssignmentTable
