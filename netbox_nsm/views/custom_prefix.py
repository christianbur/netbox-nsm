from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import CustomPrefixFilterSet
from netbox_nsm.models import CustomPrefix
from netbox_nsm.forms import (
    CustomPrefixFilterForm,
    CustomPrefixForm,
    CustomPrefixBulkEditForm,
    CustomPrefixImportForm,
)
from netbox_nsm.tables import CustomPrefixTable

__all__ = (
    "CustomPrefixView",
    "CustomPrefixListView",
    "CustomPrefixEditView",
    "CustomPrefixDeleteView",
    "CustomPrefixBulkEditView",
    "CustomPrefixBulkDeleteView",
    "CustomPrefixBulkImportView",
)


@register_model_view(CustomPrefix)
class CustomPrefixView(generic.ObjectView):
    queryset = CustomPrefix.objects.all()
    template_name = "netbox_nsm/customprefix.html"

    def get_extra_context(self, request, instance):
        return {}


@register_model_view(CustomPrefix, "list", path="", detail=False)
class CustomPrefixListView(generic.ObjectListView):
    queryset = CustomPrefix.objects.all()
    filterset = CustomPrefixFilterSet
    filterset_form = CustomPrefixFilterForm
    table = CustomPrefixTable


@register_model_view(CustomPrefix, "add", detail=False)
@register_model_view(CustomPrefix, "edit")
class CustomPrefixEditView(generic.ObjectEditView):
    queryset = CustomPrefix.objects.all()
    form = CustomPrefixForm


@register_model_view(CustomPrefix, "delete")
class CustomPrefixDeleteView(generic.ObjectDeleteView):
    queryset = CustomPrefix.objects.all()


@register_model_view(CustomPrefix, "bulk_edit", path="edit", detail=False)
class CustomPrefixBulkEditView(generic.BulkEditView):
    queryset = CustomPrefix.objects.all()
    filterset = CustomPrefixFilterSet
    table = CustomPrefixTable
    form = CustomPrefixBulkEditForm


@register_model_view(CustomPrefix, "bulk_delete", path="delete", detail=False)
class CustomPrefixBulkDeleteView(generic.BulkDeleteView):
    queryset = CustomPrefix.objects.all()
    table = CustomPrefixTable


@register_model_view(CustomPrefix, "bulk_import", detail=False)
class CustomPrefixBulkImportView(generic.BulkImportView):
    queryset = CustomPrefix.objects.all()
    model_form = CustomPrefixImportForm
