from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectPolicer

__all__ = (
    "ObjectPolicerForm",
    "ObjectPolicerFilterForm",
    "ObjectPolicerBulkEditForm",
)


class ObjectPolicerForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet("name", "description", name=_("Policer Object")),
        FieldSet("bandwidth_limit", "bandwidth_percent", name=_("Bandwidth")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectPolicer
        fields = ("name", "bandwidth_limit", "bandwidth_percent", "description", "comments", "tags")


class ObjectPolicerFilterForm(PrimaryModelFilterSetForm):
    model = ObjectPolicer
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
    )


class ObjectPolicerBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectPolicer
    nullable_fields = ("description",)
