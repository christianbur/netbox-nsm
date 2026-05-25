from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import (
    DynamicModelMultipleChoiceField,
    CSVModelMultipleChoiceField,
    TagFilterField,
    CommentField,
)
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityZoneMatrix, SecurityZoneRole

__all__ = (
    "SecurityZoneMatrixForm",
    "SecurityZoneMatrixFilterForm",
    "SecurityZoneMatrixImportForm",
    "SecurityZoneMatrixBulkEditForm",
)


class SecurityZoneMatrixForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    roles = DynamicModelMultipleChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        label=_("Security Zone Roles"),
    )
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "roles", "description", name=_("Security Zone Matrix")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityZoneMatrix
        fields = (
            "name",
            "roles",
            "description",
            "comments",
            "tags",
        )


class SecurityZoneMatrixFilterForm(PrimaryModelFilterSetForm):
    model = SecurityZoneMatrix
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "role_id", name=_("Security Zone Matrix")),
    )
    role_id = DynamicModelMultipleChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        label=_("Security Zone Role"),
    )
    tags = TagFilterField(model)


class SecurityZoneMatrixImportForm(PrimaryModelImportForm):
    roles = CSVModelMultipleChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Security Zone Roles"),
    )

    class Meta:
        model = SecurityZoneMatrix
        fields = (
            "name",
            "roles",
            "description",
            "tags",
        )


class SecurityZoneMatrixBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityZoneMatrix
    roles = DynamicModelMultipleChoiceField(
        queryset=SecurityZoneRole.objects.all(),
        required=False,
        label=_("Security Zone Roles"),
    )
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("roles", "description"),
        FieldSet("tags", name=_("Tags")),
    )
