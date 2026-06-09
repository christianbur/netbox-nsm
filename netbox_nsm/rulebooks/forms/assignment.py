from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from dcim.models import Device, VirtualDeviceContext
from netbox.forms import NetBoxModelForm
from utilities.forms.fields import (
    ContentTypeChoiceField,
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
)
from virtualization.models import VirtualMachine

from netbox_nsm.constants import RULESET_ASSIGNMENT_MODELS
from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks
from netbox_nsm.models import CotRulebookAssignment

__all__ = (
    "CotRulebookAssignmentForm",
    "CotRulebookAssignmentFilterForm",
    "CotRulebookBulkAssignForm",
)


class CotRulebookAssignmentForm(NetBoxModelForm):
    assigned_object_type = ContentTypeChoiceField(
        queryset=ContentType.objects.filter(RULESET_ASSIGNMENT_MODELS),
        widget=forms.HiddenInput,
    )
    assigned_object_id = forms.IntegerField(widget=forms.HiddenInput)
    cot_slug = forms.ChoiceField(
        label=_("Rulebook"),
        choices=(),
        required=True,
    )

    field_order = ("cot_slug", "description", "tags")

    class Meta:
        model = CotRulebookAssignment
        fields = ("cot_slug", "description", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        for cot in iter_deployed_cot_rulebooks():
            label = cot.verbose_name or cot.name
            choices.append((cot.slug, label))
        self.fields["cot_slug"].choices = choices


class CotRulebookAssignmentFilterForm(forms.Form):
    cot_slug = forms.CharField(required=False, label=_("Rulebook slug"))


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
