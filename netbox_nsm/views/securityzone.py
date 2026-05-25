from django.utils.translation import gettext_lazy as _

from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.tables import (
    SecurityZoneTable,
)
from netbox_nsm.filtersets import (
    SecurityZoneFilterSet,
)

from netbox_nsm.models import SecurityZone
from netbox_nsm.forms import (
    SecurityZoneFilterForm,
    SecurityZoneForm,
    SecurityZoneBulkEditForm,
    SecurityZoneImportForm,
)

__all__ = (
    "SecurityZoneView",
    "SecurityZoneListView",
    "SecurityZoneEditView",
    "SecurityZoneDeleteView",
    "SecurityZoneBulkEditView",
    "SecurityZoneBulkDeleteView",
    "SecurityZoneBulkImportView",
)


@register_model_view(SecurityZone)
class SecurityZoneView(generic.ObjectView):
    queryset = SecurityZone.annotated_queryset()
    template_name = "netbox_nsm/securityzone.html"


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


