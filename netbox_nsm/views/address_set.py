from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.tables import (
    AddressSetTable,
)
from netbox_nsm.filtersets import (
    AddressSetFilterSet,
)

from netbox_nsm.models import AddressSet
from netbox_nsm.forms import (
    AddressSetFilterForm,
    AddressSetForm,
    AddressSetBulkEditForm,
    AddressSetImportForm,
)

__all__ = (
    "AddressSetView",
    "AddressSetListView",
    "AddressSetEditView",
    "AddressSetDeleteView",
    "AddressSetBulkEditView",
    "AddressSetBulkDeleteView",
    "AddressSetBulkImportView",
)


@register_model_view(AddressSet)
class AddressSetView(generic.ObjectView):
    queryset = AddressSet.objects.all()
    template_name = "netbox_nsm/addressset.html"


@register_model_view(AddressSet, "list", path="", detail=False)
class AddressSetListView(generic.ObjectListView):
    queryset = AddressSet.objects.all()
    filterset = AddressSetFilterSet
    filterset_form = AddressSetFilterForm
    table = AddressSetTable


@register_model_view(AddressSet, "add", detail=False)
@register_model_view(AddressSet, "edit")
class AddressSetEditView(generic.ObjectEditView):
    queryset = AddressSet.objects.all()
    form = AddressSetForm


@register_model_view(AddressSet, "delete")
class AddressSetDeleteView(generic.ObjectDeleteView):
    queryset = AddressSet.objects.all()


@register_model_view(AddressSet, "bulk_edit", path="edit", detail=False)
class AddressSetBulkEditView(generic.BulkEditView):
    queryset = AddressSet.objects.all()
    filterset = AddressSetFilterSet
    table = AddressSetTable
    form = AddressSetBulkEditForm


@register_model_view(AddressSet, "bulk_delete", path="delete", detail=False)
class AddressSetBulkDeleteView(generic.BulkDeleteView):
    queryset = AddressSet.objects.all()
    table = AddressSetTable


@register_model_view(AddressSet, "bulk_import", detail=False)
class AddressSetBulkImportView(generic.BulkImportView):
    queryset = AddressSet.objects.all()
    model_form = AddressSetImportForm
