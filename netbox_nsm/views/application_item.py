from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.models import ApplicationItem
from netbox_nsm.tables import ApplicationItemTable
from netbox_nsm.filtersets import ApplicationItemFilterSet
from netbox_nsm.forms import (
    ApplicationItemForm,
    ApplicationItemFilterForm,
    ApplicationItemBulkEditForm,
    ApplicationItemImportForm,
)

__all__ = (
    "ApplicationItemView",
    "ApplicationItemListView",
    "ApplicationItemEditView",
    "ApplicationItemDeleteView",
    "ApplicationItemBulkEditView",
    "ApplicationItemBulkDeleteView",
    "ApplicationItemBulkImportView",
)


@register_model_view(ApplicationItem)
class ApplicationItemView(generic.ObjectView):
    queryset = ApplicationItem.objects.prefetch_related("tags")


@register_model_view(ApplicationItem, "list", path="", detail=False)
class ApplicationItemListView(generic.ObjectListView):
    queryset = ApplicationItem.objects.prefetch_related("tags")
    filterset = ApplicationItemFilterSet
    filterset_form = ApplicationItemFilterForm
    table = ApplicationItemTable


@register_model_view(ApplicationItem, "add", detail=False)
@register_model_view(ApplicationItem, "edit")
class ApplicationItemEditView(generic.ObjectEditView):
    queryset = ApplicationItem.objects.all()
    form = ApplicationItemForm


@register_model_view(ApplicationItem, "delete")
class ApplicationItemDeleteView(generic.ObjectDeleteView):
    queryset = ApplicationItem.objects.all()


@register_model_view(ApplicationItem, "bulk_edit", path="edit", detail=False)
class ApplicationItemBulkEditView(generic.BulkEditView):
    queryset = ApplicationItem.objects.prefetch_related("tags")
    filterset = ApplicationItemFilterSet
    table = ApplicationItemTable
    form = ApplicationItemBulkEditForm


@register_model_view(ApplicationItem, "bulk_delete", path="delete", detail=False)
class ApplicationItemBulkDeleteView(generic.BulkDeleteView):
    queryset = ApplicationItem.objects.all()
    filterset = ApplicationItemFilterSet
    table = ApplicationItemTable


@register_model_view(ApplicationItem, "bulk_import", path="import", detail=False)
class ApplicationItemBulkImportView(generic.BulkImportView):
    queryset = ApplicationItem.objects.all()
    model_form = ApplicationItemImportForm
