from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectInterface
from netbox_nsm.models.object_interface import InterfaceDirectionChoices

__all__ = (
    "ObjectInterfaceForm",
    "ObjectInterfaceFilterForm",
    "ObjectInterfaceBulkEditForm",
)


class ObjectInterfaceForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)

    fieldsets = (
        FieldSet("name", "direction", "description", name=_("Interface Object")),
        FieldSet("device", "interface", name=_("Device / Interface")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectInterface
        fields = ("name", "direction", "device", "interface", "description", "comments", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from dcim.models import Device, Interface
        self.fields["device"] = DynamicModelChoiceField(
            queryset=Device.objects.all(), required=False, label=_("Device")
        )
        self.fields["interface"] = DynamicModelChoiceField(
            queryset=Interface.objects.all(),
            required=False,
            label=_("Interface"),
            query_params={"device_id": "$device"},
        )


class ObjectInterfaceFilterForm(PrimaryModelFilterSetForm):
    model = ObjectInterface
    direction = forms.ChoiceField(
        choices=[("", "---------")] + list(InterfaceDirectionChoices.CHOICES),
        required=False,
        label=_("Direction"),
    )
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "direction", "tag"),
    )


class ObjectInterfaceBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectInterface
    nullable_fields = ("description",)
