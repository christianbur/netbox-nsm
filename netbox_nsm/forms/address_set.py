from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
    NetBoxModelFilterSetForm,
)

from tenancy.forms import TenancyForm, TenancyFilterForm
from utilities.forms.rendering import FieldSet, ObjectAttribute
from utilities.forms.fields import (
    DynamicModelChoiceField,
    DynamicModelMultipleChoiceField,
    TagFilterField,
    CommentField,
    CSVModelMultipleChoiceField,
    CSVModelChoiceField,
)
from dcim.models import Device, VirtualDeviceContext
from tenancy.models import Tenant, TenantGroup

from netbox_nsm.models import (
    AddressSet,
    Address,
    SecurityZone,
)

__all__ = (
    "AddressSetForm",
    "AddressSetFilterForm",
    "AddressSetImportForm",
    "AddressSetBulkEditForm",
)


class AddressSetForm(TenancyForm, PrimaryModelForm):
    name = forms.CharField(max_length=64, required=True)
    identifier = forms.CharField(max_length=100, required=False)
    addresses = DynamicModelMultipleChoiceField(
        required=False,
        label=_("Addresses"),
        quick_add=True,
        queryset=Address.objects.all(),
    )
    address_sets = DynamicModelMultipleChoiceField(
        required=False,
        label=_("Address Sets"),
        quick_add=True,
        queryset=AddressSet.objects.all(),
    )
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet(
            "name",
            "identifier",
            "addresses",
            "address_sets",
            "description",
            name=_("Address Set Parameters"),
        ),
        FieldSet("tenant_group", "tenant", name=_("Tenancy")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = AddressSet
        fields = [
            "name",
            "owner",
            "identifier",
            "addresses",
            "address_sets",
            "tenant_group",
            "tenant",
            "description",
            "comments",
            "tags",
        ]


class AddressSetFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = AddressSet
    fieldsets = (
        FieldSet("q", "filter_id", "tag", "owner_id"),
        FieldSet(
            "name",
            "identifier",
            "addresses_id",
            "address_sets_id",
            name=_("AddressSet List"),
        ),
        FieldSet("tenant_group_id", "tenant_id", name=_("Tenancy")),
    )
    addresses_id = DynamicModelMultipleChoiceField(
        required=False,
        label=_("Addresses"),
        queryset=Address.objects.all(),
    )
    address_sets_id = DynamicModelMultipleChoiceField(
        required=False,
        label=_("Address Sets"),
        queryset=AddressSet.objects.all(),
    )
    tags = TagFilterField(model)


class AddressSetImportForm(PrimaryModelImportForm):
    name = forms.CharField(max_length=200, required=True)
    identifier = forms.CharField(max_length=100, required=False)
    description = forms.CharField(max_length=200, required=False)
    addresses = CSVModelMultipleChoiceField(
        queryset=Address.objects.all(),
        to_field_name="name",
        required=False,
    )
    address_sets = CSVModelMultipleChoiceField(
        queryset=AddressSet.objects.all(),
        to_field_name="name",
        required=False,
    )
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Tenant"),
    )

    class Meta:
        model = AddressSet
        fields = (
            "name",
            "owner",
            "identifier",
            "addresses",
            "address_sets",
            "description",
            "tenant",
            "tags",
        )


class AddressSetBulkEditForm(PrimaryModelBulkEditForm):
    model = AddressSet
    description = forms.CharField(max_length=200, required=False)
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
    tags = TagFilterField(model)
    nullable_fields = ["description", "tenant"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tenant_group", "tenant", name=_("Tenancy")),
        FieldSet("tags", name=_("Tags")),
    )


