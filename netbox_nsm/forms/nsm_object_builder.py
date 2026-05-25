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

from netbox_nsm.models import NsmObjectType, NsmObjectTypeField, NsmObject

__all__ = (
    "NsmObjectTypeForm",
    "NsmObjectTypeFilterForm",
    "NsmObjectTypeImportForm",
    "NsmObjectTypeBulkEditForm",
    "NsmObjectTypeFieldForm",
    "NsmObjectTypeFieldFilterForm",
    "NsmObjectTypeFieldImportForm",
    "NsmObjectTypeFieldBulkEditForm",
    "NsmObjectForm",
    "NsmObjectFilterForm",
    "NsmObjectImportForm",
    "NsmObjectBulkEditForm",
)


class NsmObjectTypeForm(PrimaryModelForm):
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
        model = NsmObjectType
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


class NsmObjectTypeFilterForm(PrimaryModelFilterSetForm):
    model = NsmObjectType
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "slug", "group_name", name=_("Type")),
    )
    tags = TagFilterField(model)


class NsmObjectTypeImportForm(PrimaryModelImportForm):
    class Meta:
        model = NsmObjectType
        fields = (
            "name",
            "verbose_name",
            "verbose_name_plural",
            "slug",
            "group_name",
            "description",
            "tags",
        )


class NsmObjectTypeBulkEditForm(PrimaryModelBulkEditForm):
    model = NsmObjectType
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )


class NsmObjectTypeFieldForm(PrimaryModelForm):
    nsm_object_type = DynamicModelChoiceField(queryset=NsmObjectType.objects.all(), required=True, label=_("Object type"))
    name = forms.CharField(max_length=50, required=True)
    label = forms.CharField(max_length=50, required=False)
    type = forms.ChoiceField(choices=NsmObjectTypeField._meta.get_field("type").choices, required=True)
    group_name = forms.CharField(max_length=50, required=False)
    required = forms.BooleanField(required=False)
    unique = forms.BooleanField(required=False)
    default = forms.JSONField(required=False)
    weight = forms.IntegerField(required=False, min_value=0)
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet(
            "nsm_object_type",
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
        model = NsmObjectTypeField
        fields = (
            "nsm_object_type",
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


class NsmObjectTypeFieldFilterForm(PrimaryModelFilterSetForm):
    model = NsmObjectTypeField
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("nsm_object_type", "name", "type", name=_("Field")),
    )
    tags = TagFilterField(model)


class NsmObjectTypeFieldImportForm(PrimaryModelImportForm):
    class Meta:
        model = NsmObjectTypeField
        fields = (
            "nsm_object_type",
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


class NsmObjectTypeFieldBulkEditForm(PrimaryModelBulkEditForm):
    model = NsmObjectTypeField
    type = forms.ChoiceField(choices=NsmObjectTypeField._meta.get_field("type").choices, required=False)
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("type", "description"),
        FieldSet("tags", name=_("Tags")),
    )


class NsmObjectForm(PrimaryModelForm):
    nsm_object_type = DynamicModelChoiceField(queryset=NsmObjectType.objects.all(), required=True, label=_("Object type"))
    name = forms.CharField(max_length=150, required=True)
    object_data = forms.JSONField(required=False)
    source_model = forms.CharField(max_length=64, required=False)
    source_pk = forms.IntegerField(required=False, min_value=1)
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet(
            "nsm_object_type",
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
        model = NsmObject
        fields = (
            "nsm_object_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            "comments",
            "tags",
        )


class NsmObjectFilterForm(PrimaryModelFilterSetForm):
    model = NsmObject
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("nsm_object_type", "name", "source_model", name=_("Object")),
    )
    tags = TagFilterField(model)


class NsmObjectImportForm(PrimaryModelImportForm):
    class Meta:
        model = NsmObject
        fields = (
            "nsm_object_type",
            "name",
            "object_data",
            "source_model",
            "source_pk",
            "description",
            "tags",
        )


class NsmObjectBulkEditForm(PrimaryModelBulkEditForm):
    model = NsmObject
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
