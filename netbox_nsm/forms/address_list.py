from django import forms
from django.utils.translation import gettext_lazy as _

from utilities.forms.rendering import FieldSet, ObjectAttribute
from utilities.forms.fields import (
    DynamicModelChoiceField,
)
from dcim.models import Device, VirtualDeviceContext

from netbox.forms import (
    NetBoxModelFilterSetForm,
)

from netbox_nsm.models import (
    AddressList,
    SecurityZone,
    Address,
    AddressSet,
)

__all__ = (
    "AddressListForm",
    "AddressListFilterForm",
)


class AddressListForm(forms.ModelForm):
    name = forms.CharField(max_length=64, required=True)
    fieldsets = (FieldSet(ObjectAttribute("assigned_object"), "name"),)

    class Meta:
        model = AddressList
        fields = ("name",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class AddressListFilterForm(NetBoxModelFilterSetForm):
    model = AddressList
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet(
            "device_id",
            "virtualdevicecontext_id",
            "securityzone_id",
            name="Assignments",
        ),
    )
    device_id = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_("Device"),
    )
    virtualdevicecontext_id = DynamicModelChoiceField(
        queryset=VirtualDeviceContext.objects.all(),
        required=False,
        label=_("Virtual Device Context"),
        query_params={"device_id": "$device_id"},
    )
    securityzone_id = DynamicModelChoiceField(
        queryset=SecurityZone.objects.all(),
        required=False,
        label=_("Security Zone"),
    )


