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
    CSVModelChoiceField,
)

from dcim.models import Device, VirtualDeviceContext, Interface
from tenancy.models import Tenant, TenantGroup
from virtualization.models import VirtualMachine

from netbox_nsm.models import (
    SecurityZone,
)

__all__ = (
    "SecurityZoneForm",
    "SecurityZoneFilterForm",
    "SecurityZoneImportForm",
    "SecurityZoneBulkEditForm",
)


class SecurityZoneForm(PrimaryModelForm):
    name = forms.CharField(max_length=64, required=True)
    color = forms.CharField(
        max_length=7,
        required=True,
        widget=forms.TextInput(attrs={"type": "color"}),
        label=_("Color"),
    )
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet("name", "color", "description", name=_("Security Zone")),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = SecurityZone
        fields = [
            "name",
            "owner",
            "color",
            "description",
            "comments",
            "tags",
        ]


class SecurityZoneFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = SecurityZone
    fieldsets = (
        FieldSet("q", "filter_id", "tag", "owner_id"),
        FieldSet(
            "name",
            "color",
        ),
        FieldSet("tenant_group_id", "tenant_id", name=_("Tenancy")),
    )
    tags = TagFilterField(model)


class SecurityZoneImportForm(PrimaryModelImportForm):
    color = forms.CharField(max_length=7, required=False)
    tenant = CSVModelChoiceField(
        queryset=Tenant.objects.all(),
        required=False,
        to_field_name="name",
        label=_("Tenant"),
    )

    class Meta:
        model = SecurityZone
        fields = (
            "name",
            "owner",
            "color",
            "description",
            "tenant",
            "tags",
        )


class SecurityZoneBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityZone
    color = forms.CharField(max_length=7, required=False, widget=forms.TextInput(attrs={"type": "color"}))
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
        FieldSet("color", "description"),
        FieldSet("tenant_group", "tenant", name=_("Tenancy")),
        FieldSet("tags", name=_("Tags")),
    )


