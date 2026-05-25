from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
    NetBoxModelFilterSetForm,
)

from tenancy.forms import TenancyForm, TenancyFilterForm
from utilities.forms.rendering import (
    FieldSet,
    ObjectAttribute,
    TabbedGroups,
)
from utilities.forms.fields import (
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
    CommentField,
    CSVModelChoiceField,
)

from ipam.models import IPRange, Prefix, IPAddress
from dcim.models import Device, VirtualDeviceContext
from tenancy.models import Tenant, TenantGroup

from netbox_nsm.models import (
    Address,
    CustomPrefix,
    SecurityZone,
)

__all__ = (
    "AddressForm",
    "AddressFilterForm",
    "AddressImportForm",
    "AddressBulkEditForm",
)


class AddressForm(PrimaryModelForm):
    name = forms.CharField(max_length=64, required=True)
    ipam_prefix = DynamicModelChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        selector=True,
        label=_("Prefix"),
    )
    ipam_ipaddress = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        required=False,
        selector=True,
        label=_("IP Address"),
    )
    ipam_iprange = DynamicModelChoiceField(
        queryset=IPRange.objects.all(),
        required=False,
        selector=True,
        label=_("IP Range"),
    )
    custom_prefix = DynamicModelChoiceField(
        queryset=CustomPrefix.objects.all(),
        required=False,
        selector=True,
        quick_add=True,
        label=_("Custom Prefix"),
    )
    dns_name = forms.CharField(
        max_length=255,
        required=False,
        help_text=_("Fully qualified hostname (wildcard allowed)"),
    )
    ip_range = DynamicModelChoiceField(
        queryset=IPRange.objects.all(),
        required=False,
        quick_add=True,
        help_text=_("An IP Address Range"),
    )
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet(
            "name",
            "description",
        ),
        FieldSet(
            TabbedGroups(
                FieldSet("ipam_prefix", name=_("Prefix")),
                FieldSet("ipam_ipaddress", name=_("IP Address")),
                FieldSet("ipam_iprange", name=_("IP Range")),
                FieldSet("custom_prefix", name=_("Custom Prefix")),
                FieldSet("dns_name", name=_("DNS Name")),
            ),
            name=_("Address Parameters"),
        ),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = Address
        fields = [
            "name",
            "owner",
            "ipam_prefix",
            "ipam_ipaddress",
            "ipam_iprange",
            "custom_prefix",
            "dns_name",
            "description",
            "comments",
            "tags",
        ]

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        initial = kwargs.get("initial", {}).copy()
        if instance:
            if type(instance.assigned_object) is Prefix:
                initial["ipam_prefix"] = instance.assigned_object
            elif type(instance.assigned_object) is IPAddress:
                initial["ipam_ipaddress"] = instance.assigned_object
            elif type(instance.assigned_object) is IPRange:
                initial["ipam_iprange"] = instance.assigned_object
            elif type(instance.assigned_object) is CustomPrefix:
                initial["custom_prefix"] = instance.assigned_object
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        # Handle object assignment
        selected_objects = [
            field
            for field in (
                "ipam_prefix",
                "ipam_ipaddress",
                "ipam_iprange",
                "custom_prefix",
                "dns_name",
            )
            if self.cleaned_data[field]
        ]
        if len(selected_objects) > 1:
            raise forms.ValidationError(
                {
                    selected_objects[1]: _(
                        "You can only assign a Prefix, IP Address, an IP Range, a Custom Prefix or a DNS Name."
                    )
                }
            )
        elif selected_objects:
            if selected_objects[0] != "dns_name":
                self.instance.assigned_object = self.cleaned_data[selected_objects[0]]
        else:
            raise ValidationError(
                _(
                    "A DNS Name, Prefix, IP Address, IP Range or Custom Prefix must be specified"
                )
            )


class AddressFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = Address
    fieldsets = (
        FieldSet("q", "filter_id", "tag", "owner_id"),
        FieldSet(
            "name",
            "dns_name",
            name=_("Address"),
        ),
        FieldSet(
            "prefix_id",
            "ipaddress_id",
            "iprange_id",
            "customprefix_id",
            name="Assignments",
        ),
    )
    tags = TagFilterField(model)

    name = forms.CharField(
        required=False,
        label=_("Name"),
    )
    dns_name = forms.CharField(
        required=False,
        label=_("DNS Name"),
    )
    prefix_id = DynamicModelChoiceField(
        queryset=Prefix.objects.all(),
        required=False,
        label=_("Prefix"),
    )
    ipaddress_id = DynamicModelChoiceField(
        queryset=IPAddress.objects.all(),
        required=False,
        label=_("IP Address"),
    )
    iprange_id = DynamicModelChoiceField(
        queryset=IPRange.objects.all(),
        required=False,
        label=_("IP Range"),
    )
    customprefix_id = DynamicModelChoiceField(
        queryset=CustomPrefix.objects.all(),
        required=False,
        label=_("Custom Prefix"),
    )


class AddressImportForm(PrimaryModelImportForm):
    name = forms.CharField(max_length=200, required=True)
    identifier = forms.CharField(max_length=100, required=False)
    description = forms.CharField(max_length=200, required=False)
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Tenant"),
    )
    dns_name = forms.CharField(
        max_length=255,
        required=False,
        help_text=_("Fully qualified hostname (wildcard allowed)"),
    )

    class Meta:
        model = Address
        fields = (
            "name",
            "owner",
            "identifier",
            "dns_name",
            "description",
            "tenant",
            "tags",
        )


class AddressBulkEditForm(PrimaryModelBulkEditForm):
    model = Address
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    tenant_group = DynamicModelChoiceField(
        queryset=TenantGroup.objects.all(),
        required=False,
        label=_("Tenant Group"),
    )
    tenant = DynamicModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        label=_("Tenant"),
    )
    nullable_fields = ["description", "tenant"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tenant_group", "tenant", name=_("Tenancy")),
        FieldSet("tags", name=_("Tags")),
    )


