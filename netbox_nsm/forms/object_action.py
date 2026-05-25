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

from netbox_nsm.models import ObjectAction

__all__ = (
    "ObjectActionForm",
    "ObjectActionFilterForm",
    "ObjectActionImportForm",
    "ObjectActionBulkEditForm",
)


class ObjectActionForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True, label=_("Name"))
    action = forms.CharField(max_length=100, required=True, label=_("Action"))
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "action", "description", name=_("Objekt (action)")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectAction
        fields = ("name", "action", "description", "comments", "tags")


class ObjectActionFilterForm(PrimaryModelFilterSetForm):
    model = ObjectAction
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "action", name=_("Objekt (action)")),
    )
    tags = TagFilterField(model)


class ObjectActionImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectAction
        fields = ("name", "action", "description", "tags")


class ObjectActionBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectAction
    action = forms.CharField(max_length=100, required=False, label=_("Action"))
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("action", "description"),
        FieldSet("tags", name=_("Tags")),
    )
