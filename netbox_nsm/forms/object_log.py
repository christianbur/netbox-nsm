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

from netbox_nsm.models import ObjectLog

__all__ = (
    "ObjectLogForm",
    "ObjectLogFilterForm",
    "ObjectLogImportForm",
    "ObjectLogBulkEditForm",
)


class ObjectLogForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True, label=_("Name"))
    enabled = forms.BooleanField(required=False, label=_("Enabled"))
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "enabled", "description", name=_("Log")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectLog
        fields = ("name", "enabled", "description", "comments", "tags")


class ObjectLogFilterForm(PrimaryModelFilterSetForm):
    model = ObjectLog
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "enabled", name=_("Log")),
    )
    tags = TagFilterField(model)


class ObjectLogImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectLog
        fields = ("name", "enabled", "description", "tags")


class ObjectLogBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectLog
    enabled = forms.NullBooleanField(required=False, label=_("Enabled"))
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("enabled", "description"),
        FieldSet("tags", name=_("Tags")),
    )
