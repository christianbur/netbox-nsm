from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import SecurityZoneRole

__all__ = (
    "SecurityZoneRoleForm",
    "SecurityZoneRoleFilterForm",
    "SecurityZoneRoleImportForm",
    "SecurityZoneRoleBulkEditForm",
)


class SecurityZoneRoleForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "description", name=_("Security Zone Role")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityZoneRole
        fields = (
            "name",
            "description",
            "comments",
            "tags",
        )


class SecurityZoneRoleFilterForm(PrimaryModelFilterSetForm):
    model = SecurityZoneRole
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", name=_("Security Zone Role")),
    )
    tags = TagFilterField(model)


class SecurityZoneRoleImportForm(PrimaryModelImportForm):
    class Meta:
        model = SecurityZoneRole
        fields = (
            "name",
            "description",
            "tags",
        )


class SecurityZoneRoleBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityZoneRole
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
