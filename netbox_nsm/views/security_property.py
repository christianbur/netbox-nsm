from netbox.views import generic
from utilities.views import register_model_view

from netbox_nsm.filtersets import SecurityPropertyTypeFilterSet, SecurityPropertyFieldFilterSet, SecurityPropertyFilterSet
from netbox_nsm.forms import (
    SecurityPropertyTypeBulkEditForm,
    SecurityPropertyFieldBulkEditForm,
    SecurityPropertyFieldFilterForm,
    SecurityPropertyFieldForm,
    SecurityPropertyFieldImportForm,
    SecurityPropertyTypeFilterForm,
    SecurityPropertyTypeForm,
    SecurityPropertyTypeImportForm,
    SecurityPropertyBulkEditForm,
    SecurityPropertyFilterForm,
    SecurityPropertyForm,
    SecurityPropertyImportForm,
)
from netbox_nsm.models import SecurityPropertyType, SecurityPropertyField, SecurityProperty
from netbox_nsm.tables import SecurityPropertyFieldTable, SecurityPropertyTypeTable, SecurityPropertyTable


@register_model_view(SecurityPropertyType)
class SecurityPropertyTypeView(generic.ObjectView):
    queryset = SecurityPropertyType.objects.prefetch_related("fields", "security_propertys")
    template_name = "netbox_nsm/securitypropertytype.html"

    def get_extra_context(self, request, instance):
        fields_table = SecurityPropertyFieldTable(instance.fields.all())
        fields_table.configure(request)
        objects_table = SecurityPropertyTable(instance.security_propertys.all())
        objects_table.configure(request)
        return {
            "fields_table": fields_table,
            "objects_table": objects_table,
        }


@register_model_view(SecurityPropertyType, "list", path="", detail=False)
class SecurityPropertyTypeListView(generic.ObjectListView):
    queryset = SecurityPropertyType.objects.all()
    filterset = SecurityPropertyTypeFilterSet
    filterset_form = SecurityPropertyTypeFilterForm
    table = SecurityPropertyTypeTable


@register_model_view(SecurityPropertyType, "add", detail=False)
@register_model_view(SecurityPropertyType, "edit")
class SecurityPropertyTypeEditView(generic.ObjectEditView):
    queryset = SecurityPropertyType.objects.all()
    form = SecurityPropertyTypeForm


@register_model_view(SecurityPropertyType, "delete")
class SecurityPropertyTypeDeleteView(generic.ObjectDeleteView):
    queryset = SecurityPropertyType.objects.all()


@register_model_view(SecurityPropertyType, "bulk_edit", path="edit", detail=False)
class SecurityPropertyTypeBulkEditView(generic.BulkEditView):
    queryset = SecurityPropertyType.objects.all()
    filterset = SecurityPropertyTypeFilterSet
    table = SecurityPropertyTypeTable
    form = SecurityPropertyTypeBulkEditForm


@register_model_view(SecurityPropertyType, "bulk_delete", path="delete", detail=False)
class SecurityPropertyTypeBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityPropertyType.objects.all()
    table = SecurityPropertyTypeTable


@register_model_view(SecurityPropertyType, "bulk_import", detail=False)
class SecurityPropertyTypeBulkImportView(generic.BulkImportView):
    queryset = SecurityPropertyType.objects.all()
    model_form = SecurityPropertyTypeImportForm


@register_model_view(SecurityPropertyField)
class SecurityPropertyFieldView(generic.ObjectView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")


@register_model_view(SecurityPropertyField, "list", path="", detail=False)
class SecurityPropertyFieldListView(generic.ObjectListView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")
    filterset = SecurityPropertyFieldFilterSet
    filterset_form = SecurityPropertyFieldFilterForm
    table = SecurityPropertyFieldTable


@register_model_view(SecurityPropertyField, "add", detail=False)
@register_model_view(SecurityPropertyField, "edit")
class SecurityPropertyFieldEditView(generic.ObjectEditView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")
    form = SecurityPropertyFieldForm


@register_model_view(SecurityPropertyField, "delete")
class SecurityPropertyFieldDeleteView(generic.ObjectDeleteView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")


@register_model_view(SecurityPropertyField, "bulk_edit", path="edit", detail=False)
class SecurityPropertyFieldBulkEditView(generic.BulkEditView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")
    filterset = SecurityPropertyFieldFilterSet
    table = SecurityPropertyFieldTable
    form = SecurityPropertyFieldBulkEditForm


@register_model_view(SecurityPropertyField, "bulk_delete", path="delete", detail=False)
class SecurityPropertyFieldBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")
    table = SecurityPropertyFieldTable


@register_model_view(SecurityPropertyField, "bulk_import", detail=False)
class SecurityPropertyFieldBulkImportView(generic.BulkImportView):
    queryset = SecurityPropertyField.objects.select_related("security_property_type")
    model_form = SecurityPropertyFieldImportForm


@register_model_view(SecurityProperty)
class SecurityPropertyView(generic.ObjectView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    template_name = "netbox_nsm/securityproperty.html"

    def get_extra_context(self, request, instance):
        return {
            "typed_data": instance.get_typed_object_data(),
        }


@register_model_view(SecurityProperty, "list", path="", detail=False)
class SecurityPropertyListView(generic.ObjectListView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    filterset = SecurityPropertyFilterSet
    filterset_form = SecurityPropertyFilterForm
    table = SecurityPropertyTable


@register_model_view(SecurityProperty, "add", detail=False)
@register_model_view(SecurityProperty, "edit")
class SecurityPropertyEditView(generic.ObjectEditView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    form = SecurityPropertyForm


@register_model_view(SecurityProperty, "delete")
class SecurityPropertyDeleteView(generic.ObjectDeleteView):
    queryset = SecurityProperty.objects.select_related("security_property_type")


@register_model_view(SecurityProperty, "bulk_edit", path="edit", detail=False)
class SecurityPropertyBulkEditView(generic.BulkEditView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    filterset = SecurityPropertyFilterSet
    table = SecurityPropertyTable
    form = SecurityPropertyBulkEditForm


@register_model_view(SecurityProperty, "bulk_delete", path="delete", detail=False)
class SecurityPropertyBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    table = SecurityPropertyTable


@register_model_view(SecurityProperty, "bulk_import", detail=False)
class SecurityPropertyBulkImportView(generic.BulkImportView):
    queryset = SecurityProperty.objects.select_related("security_property_type")
    model_form = SecurityPropertyImportForm
