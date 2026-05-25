from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.tables import ApplicationSetTable
from netbox_nsm.filtersets import (
    ApplicationSetFilterSet,
)

from netbox_nsm.models import ApplicationSet
from netbox_nsm.forms import (
    ApplicationSetFilterForm,
    ApplicationSetForm,
    ApplicationSetBulkEditForm,
    ApplicationSetImportForm,
)

__all__ = (
    "ApplicationSetView",
    "ApplicationSetListView",
    "ApplicationSetEditView",
    "ApplicationSetDeleteView",
    "ApplicationSetBulkEditView",
    "ApplicationSetBulkDeleteView",
    "ApplicationSetBulkImportView",
)


@register_model_view(ApplicationSet)
class ApplicationSetView(generic.ObjectView):
    queryset = ApplicationSet.objects.all()
    template_name = "netbox_nsm/applicationset.html"


@register_model_view(ApplicationSet, "list", path="", detail=False)
class ApplicationSetListView(generic.ObjectListView):
    queryset = ApplicationSet.objects.all()
    filterset = ApplicationSetFilterSet
    filterset_form = ApplicationSetFilterForm
    table = ApplicationSetTable


@register_model_view(ApplicationSet, "add", detail=False)
@register_model_view(ApplicationSet, "edit")
class ApplicationSetEditView(generic.ObjectEditView):
    queryset = ApplicationSet.objects.all()
    form = ApplicationSetForm


@register_model_view(ApplicationSet, "delete")
class ApplicationSetDeleteView(generic.ObjectDeleteView):
    queryset = ApplicationSet.objects.all()


@register_model_view(ApplicationSet, "bulk_edit", path="edit", detail=False)
class ApplicationSetBulkEditView(generic.BulkEditView):
    queryset = ApplicationSet.objects.all()
    filterset = ApplicationSetFilterSet
    table = ApplicationSetTable
    form = ApplicationSetBulkEditForm


@register_model_view(ApplicationSet, "bulk_delete", path="delete", detail=False)
class ApplicationSetBulkDeleteView(generic.BulkDeleteView):
    queryset = ApplicationSet.objects.all()
    table = ApplicationSetTable


@register_model_view(ApplicationSet, "bulk_import", detail=False)
class ApplicationSetBulkImportView(generic.BulkImportView):
    queryset = ApplicationSet.objects.all()
    model_form = ApplicationSetImportForm
