from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityPropertyType, SecurityPropertyField, SecurityProperty

__all__ = (
    "SecurityPropertyTypeForm",
    "SecurityPropertyTypeFilterForm",
    "SecurityPropertyTypeImportForm",
    "SecurityPropertyTypeBulkEditForm",
    "SecurityPropertyFieldForm",
    "SecurityPropertyFieldFilterForm",
    "SecurityPropertyFieldImportForm",
    "SecurityPropertyFieldBulkEditForm",
    "SecurityPropertyForm",
    "SecurityPropertyFilterForm",
    "SecurityPropertyImportForm",
    "SecurityPropertyBulkEditForm",
)


class SecurityPropertyTypeForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True, label=_("Internal name"))
    verbose_name = forms.CharField(max_length=100, required=False, label=_("Display name"))
    verbose_name_plural = forms.CharField(max_length=100, required=False, label=_("Display name (plural)"))
    slug = forms.SlugField(max_length=100, required=True)
    group_name = forms.CharField(max_length=100, required=False)
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet(
            "name",
            "verbose_name",
            "verbose_name_plural",
            "slug",
            "group_name",
            "description",
            name=_("Type"),
        ),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityPropertyType
        fields = (
            "name",
            "verbose_name",
            "verbose_name_plural",
            "slug",
            "group_name",
            "description",
            "comments",
            "tags",
        )


class SecurityPropertyTypeFilterForm(PrimaryModelFilterSetForm):
    model = SecurityPropertyType
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "slug", "group_name", name=_("Type")),
    )
    tags = TagFilterField(model)


class SecurityPropertyTypeImportForm(PrimaryModelImportForm):
    class Meta:
        model = SecurityPropertyType
        fields = (
            "name",
            "verbose_name",
            "verbose_name_plural",
            "slug",
            "group_name",
            "description",
            "tags",
        )


class SecurityPropertyTypeBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityPropertyType
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )


class SecurityPropertyFieldForm(PrimaryModelForm):
    security_property_type = DynamicModelChoiceField(queryset=SecurityPropertyType.objects.all(), required=True, label=_("Object type"))
    name = forms.CharField(max_length=50, required=True)
    label = forms.CharField(max_length=50, required=False)
    type = forms.ChoiceField(choices=SecurityPropertyField._meta.get_field("type").choices, required=True)
    group_name = forms.CharField(max_length=50, required=False)
    required = forms.BooleanField(required=False)
    unique = forms.BooleanField(required=False)
    default = forms.JSONField(required=False)
    weight = forms.IntegerField(required=False, min_value=0)
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet(
            "security_property_type",
            "name",
            "label",
            "type",
            "group_name",
            "required",
            "unique",
            "default",
            "weight",
            "description",
            name=_("Field"),
        ),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityPropertyField
        fields = (
            "security_property_type",
            "name",
            "label",
            "type",
            "group_name",
            "required",
            "unique",
            "default",
            "weight",
            "description",
            "comments",
            "tags",
        )


class SecurityPropertyFieldFilterForm(PrimaryModelFilterSetForm):
    model = SecurityPropertyField
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("security_property_type", "name", "type", name=_("Field")),
    )
    tags = TagFilterField(model)


class SecurityPropertyFieldImportForm(PrimaryModelImportForm):
    class Meta:
        model = SecurityPropertyField
        fields = (
            "security_property_type",
            "name",
            "label",
            "type",
            "group_name",
            "required",
            "unique",
            "default",
            "weight",
            "description",
            "tags",
        )


class SecurityPropertyFieldBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityPropertyField
    type = forms.ChoiceField(choices=SecurityPropertyField._meta.get_field("type").choices, required=False)
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class SecurityPropertyForm(PrimaryModelForm):
    security_property_type = DynamicModelChoiceField(queryset=SecurityPropertyType.objects.all(), required=True, label=_("Object type"))
    name = forms.CharField(max_length=150, required=True)
    object_data = forms.JSONField(required=False)
    source_model = forms.CharField(max_length=64, required=False)
    source_pk = forms.IntegerField(required=False, min_value=1)
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet(
            "security_property_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            name=_("Object"),
        ),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityProperty
        fields = (
            "security_property_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            "comments",
            "tags",
        )


class SecurityPropertyFilterForm(PrimaryModelFilterSetForm):
    model = SecurityProperty
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("security_property_type", "name", "source_model", name=_("Object")),
    )
    tags = TagFilterField(model)


class SecurityPropertyImportForm(PrimaryModelImportForm):
    class Meta:
        model = SecurityProperty
        fields = (
            "security_property_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            "tags",
        )


class SecurityPropertyBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityProperty
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
