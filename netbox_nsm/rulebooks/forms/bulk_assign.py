from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from utilities.forms.fields import DynamicModelMultipleChoiceField
from virtualization.models import VirtualMachine

__all__ = ("CotRulebookBulkAssignForm",)


class CotRulebookBulkAssignForm(forms.Form):
    """Assign a COT rulebook to multiple devices/VMs/VDCs in one form submission."""

    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label=_("Devices"),
    )
    virtual_machines = DynamicModelMultipleChoiceField(
        queryset=VirtualMachine.objects.all(),
        required=False,
        label=_("Virtual Machines"),
    )
    virtual_device_contexts = DynamicModelMultipleChoiceField(
        queryset=VirtualDeviceContext.objects.all(),
        required=False,
        label=_("Virtual Device Contexts"),
    )

    def clean(self):
        data = super().clean()
        if (
            not data.get("devices")
            and not data.get("virtual_machines")
            and not data.get("virtual_device_contexts")
        ):
            raise forms.ValidationError(_("Select at least one device, VM, or VDC."))
        return data
