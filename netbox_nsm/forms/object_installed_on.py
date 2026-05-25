from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectInstalledOn

__all__ = (
    "ObjectInstalledOnForm",
    "ObjectInstalledOnFilterForm",
    "ObjectInstalledOnBulkEditForm",
)


class ObjectInstalledOnForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet("name", "description", name=_("Installed On Object")),
        FieldSet("device", name=_("Device")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectInstalledOn
        fields = ("name", "device", "description", "comments", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from dcim.models import Device
        self.fields["device"] = DynamicModelChoiceField(
            queryset=Device.objects.all(), required=False, label=_("Device")
        )


class ObjectInstalledOnFilterForm(PrimaryModelFilterSetForm):
    model = ObjectInstalledOn
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
    )


class ObjectInstalledOnBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectInstalledOn
    nullable_fields = ("description",)
