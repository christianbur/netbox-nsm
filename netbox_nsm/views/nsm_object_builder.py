from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import NsmObjectTypeFilterSet, NsmObjectTypeFieldFilterSet, NsmObjectFilterSet
from netbox_nsm.forms import (
    NsmObjectTypeBulkEditForm,
    NsmObjectTypeFieldBulkEditForm,
    NsmObjectTypeFieldFilterForm,
    NsmObjectTypeFieldForm,
    NsmObjectTypeFieldImportForm,
    NsmObjectTypeFilterForm,
    NsmObjectTypeForm,
    NsmObjectTypeImportForm,
    NsmObjectBulkEditForm,
    NsmObjectFilterForm,
    NsmObjectForm,
    NsmObjectImportForm,
)
from netbox_nsm.models import NsmObjectType, NsmObjectTypeField, NsmObject
from netbox_nsm.tables import NsmObjectTypeFieldTable, NsmObjectTypeTable, NsmObjectTable


@register_model_view(NsmObjectType)
class NsmObjectTypeView(generic.ObjectView):
    queryset = NsmObjectType.objects.prefetch_related("fields", "nsm_objects")
    template_name = "netbox_nsm/nsmobjecttype.html"

    def get_extra_context(self, request, instance):
        fields_table = NsmObjectTypeFieldTable(instance.fields.all())
        fields_table.configure(request)
        objects_table = NsmObjectTable(instance.nsm_objects.all())
        objects_table.configure(request)
        return {
            "fields_table": fields_table,
            "objects_table": objects_table,
        }


@register_model_view(NsmObjectType, "list", path="", detail=False)
class NsmObjectTypeListView(generic.ObjectListView):
    queryset = NsmObjectType.objects.all()
    filterset = NsmObjectTypeFilterSet
    filterset_form = NsmObjectTypeFilterForm
    table = NsmObjectTypeTable


@register_model_view(NsmObjectType, "add", detail=False)
@register_model_view(NsmObjectType, "edit")
class NsmObjectTypeEditView(generic.ObjectEditView):
    queryset = NsmObjectType.objects.all()
    form = NsmObjectTypeForm


@register_model_view(NsmObjectType, "delete")
class NsmObjectTypeDeleteView(generic.ObjectDeleteView):
    queryset = NsmObjectType.objects.all()


@register_model_view(NsmObjectType, "bulk_edit", path="edit", detail=False)
class NsmObjectTypeBulkEditView(generic.BulkEditView):
    queryset = NsmObjectType.objects.all()
    filterset = NsmObjectTypeFilterSet
    table = NsmObjectTypeTable
    form = NsmObjectTypeBulkEditForm


@register_model_view(NsmObjectType, "bulk_delete", path="delete", detail=False)
class NsmObjectTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = NsmObjectType.objects.all()
    table = NsmObjectTypeTable


@register_model_view(NsmObjectType, "bulk_import", detail=False)
class NsmObjectTypeBulkImportView(generic.BulkImportView):
    queryset = NsmObjectType.objects.all()
    model_form = NsmObjectTypeImportForm


@register_model_view(NsmObjectTypeField)
class NsmObjectTypeFieldView(generic.ObjectView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")


@register_model_view(NsmObjectTypeField, "list", path="", detail=False)
class NsmObjectTypeFieldListView(generic.ObjectListView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")
    filterset = NsmObjectTypeFieldFilterSet
    filterset_form = NsmObjectTypeFieldFilterForm
    table = NsmObjectTypeFieldTable


@register_model_view(NsmObjectTypeField, "add", detail=False)
@register_model_view(NsmObjectTypeField, "edit")
class NsmObjectTypeFieldEditView(generic.ObjectEditView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")
    form = NsmObjectTypeFieldForm


@register_model_view(NsmObjectTypeField, "delete")
class NsmObjectTypeFieldDeleteView(generic.ObjectDeleteView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")


@register_model_view(NsmObjectTypeField, "bulk_edit", path="edit", detail=False)
class NsmObjectTypeFieldBulkEditView(generic.BulkEditView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")
    filterset = NsmObjectTypeFieldFilterSet
    table = NsmObjectTypeFieldTable
    form = NsmObjectTypeFieldBulkEditForm


@register_model_view(NsmObjectTypeField, "bulk_delete", path="delete", detail=False)
class NsmObjectTypeFieldBulkDeleteView(generic.BulkDeleteView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")
    table = NsmObjectTypeFieldTable


@register_model_view(NsmObjectTypeField, "bulk_import", detail=False)
class NsmObjectTypeFieldBulkImportView(generic.BulkImportView):
    queryset = NsmObjectTypeField.objects.select_related("nsm_object_type")
    model_form = NsmObjectTypeFieldImportForm


@register_model_view(NsmObject)
class NsmObjectView(generic.ObjectView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    template_name = "netbox_nsm/nsmobject.html"

    def get_extra_context(self, request, instance):
        return {
            "typed_data": instance.get_typed_object_data(),
        }


@register_model_view(NsmObject, "list", path="", detail=False)
class NsmObjectListView(generic.ObjectListView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    filterset = NsmObjectFilterSet
    filterset_form = NsmObjectFilterForm
    table = NsmObjectTable


@register_model_view(NsmObject, "add", detail=False)
@register_model_view(NsmObject, "edit")
class NsmObjectEditView(generic.ObjectEditView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    form = NsmObjectForm


@register_model_view(NsmObject, "delete")
class NsmObjectDeleteView(generic.ObjectDeleteView):
    queryset = NsmObject.objects.select_related("nsm_object_type")


@register_model_view(NsmObject, "bulk_edit", path="edit", detail=False)
class NsmObjectBulkEditView(generic.BulkEditView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    filterset = NsmObjectFilterSet
    table = NsmObjectTable
    form = NsmObjectBulkEditForm


@register_model_view(NsmObject, "bulk_delete", path="delete", detail=False)
class NsmObjectBulkDeleteView(generic.BulkDeleteView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    table = NsmObjectTable


@register_model_view(NsmObject, "bulk_import", detail=False)
class NsmObjectBulkImportView(generic.BulkImportView):
    queryset = NsmObject.objects.select_related("nsm_object_type")
    model_form = NsmObjectImportForm
