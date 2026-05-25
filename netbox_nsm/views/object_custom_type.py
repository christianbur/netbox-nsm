from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import ObjectCustomTypeFilterSet
from netbox_nsm.forms import (
    ObjectCustomTypeBulkEditForm,
    ObjectCustomTypeFilterForm,
    ObjectCustomTypeForm,
    ObjectCustomTypeImportForm,
)
from netbox_nsm.models import ObjectCustomType
from netbox_nsm.tables import ObjectCustomTypeTable


@register_model_view(ObjectCustomType)
class ObjectCustomTypeView(generic.ObjectView):
    queryset = ObjectCustomType.objects.all()
    template_name = "netbox_nsm/objectcustomtype.html"


@register_model_view(ObjectCustomType, "list", path="", detail=False)
class ObjectCustomTypeListView(generic.ObjectListView):
    queryset = ObjectCustomType.objects.all()
    filterset = ObjectCustomTypeFilterSet
    filterset_form = ObjectCustomTypeFilterForm
    table = ObjectCustomTypeTable


@register_model_view(ObjectCustomType, "add", detail=False)
@register_model_view(ObjectCustomType, "edit")
class ObjectCustomTypeEditView(generic.ObjectEditView):
    queryset = ObjectCustomType.objects.all()
    form = ObjectCustomTypeForm


@register_model_view(ObjectCustomType, "delete")
class ObjectCustomTypeDeleteView(generic.ObjectDeleteView):
    queryset = ObjectCustomType.objects.all()


@register_model_view(ObjectCustomType, "bulk_edit", path="edit", detail=False)
class ObjectCustomTypeBulkEditView(generic.BulkEditView):
    queryset = ObjectCustomType.objects.all()
    filterset = ObjectCustomTypeFilterSet
    table = ObjectCustomTypeTable
    form = ObjectCustomTypeBulkEditForm


@register_model_view(ObjectCustomType, "bulk_delete", path="delete", detail=False)
class ObjectCustomTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = ObjectCustomType.objects.all()
    table = ObjectCustomTypeTable


@register_model_view(ObjectCustomType, "bulk_import", detail=False)
class ObjectCustomTypeBulkImportView(generic.BulkImportView):
    queryset = ObjectCustomType.objects.all()
    model_form = ObjectCustomTypeImportForm
