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
    TagFilterField,
    CommentField,
    CSVModelChoiceField,
    CSVModelMultipleChoiceField,
    DynamicModelMultipleChoiceField,
)

from dcim.models import Device, VirtualDeviceContext
from tenancy.models import Tenant, TenantGroup

from netbox_nsm.models import (
    Application,
    ApplicationItem,
)

__all__ = (
    "ApplicationForm",
    "ApplicationFilterForm",
    "ApplicationImportForm",
    "ApplicationBulkEditForm",
)


class ApplicationForm(PrimaryModelForm):
    name = forms.CharField(max_length=64, required=True, label=_("Application Name"))
    identifier = forms.CharField(max_length=100, required=True, label=_("App-ID Name"))
    category = forms.CharField(max_length=100, required=False, label=_("Category"))
    subcategory = forms.CharField(max_length=100, required=False, label=_("Subcategory"))
    application_items = DynamicModelMultipleChoiceField(
        queryset=ApplicationItem.objects.all(),
        required=False,
        quick_add=True,
        label=_("Standard Ports (Services)"),
        help_text=_("Link one or more services."),
    )
    standard_ports_text = forms.CharField(
        max_length=255,
        required=False,
        label=_("Standard Ports (Text)"),
        help_text=_("Optional free text, e.g. tcp/22."),
    )
    technology = forms.CharField(max_length=100, required=False, label=_("Technology"))
    reference = forms.CharField(max_length=255, required=False, label=_("Reference"))
    fieldsets = (
        FieldSet(
            "name",
            "identifier",
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "description",
            name=_("General"),
        ),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = Application
        fields = [
            "name",
            "identifier",
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "description",
            "comments",
            "tags",
        ]

    def clean(self):
        cleaned_data = super().clean()
        has_services = bool(cleaned_data.get("application_items"))
        has_text = bool(cleaned_data.get("standard_ports_text"))
        if not has_services and not has_text:
            raise forms.ValidationError(
                _("Define standard ports as linked services or as free text.")
            )
        return cleaned_data


class ApplicationFilterForm(TenancyFilterForm, PrimaryModelFilterSetForm):
    model = Application
    fieldsets = (
        FieldSet("q", "filter_id", "tag", "owner_id"),
        FieldSet(
            "name",
            "identifier",
            "category",
            "subcategory",
            "application_items_id",
            "standard_ports_text",
            "technology",
            "reference",
            name=_("Application"),
        ),
        FieldSet("tenant_group_id", "tenant_id", name=_("Tenancy")),
    )
    name = forms.CharField(
        required=False,
        label=_("Name"),
    )
    identifier = forms.CharField(
        required=False,
        label=_("App-ID Name"),
    )
    category = forms.CharField(required=False, label=_("Category"))
    subcategory = forms.CharField(required=False, label=_("Subcategory"))
    application_items_id = DynamicModelMultipleChoiceField(
        queryset=ApplicationItem.objects.all(),
        label=_("Standard Ports (Services)"),
        required=False,
    )
    standard_ports_text = forms.CharField(required=False, label=_("Standard Ports (Text)"))
    technology = forms.CharField(required=False, label=_("Technology"))
    reference = forms.CharField(required=False, label=_("Reference"))
    tags = TagFilterField(model)


class ApplicationImportForm(PrimaryModelImportForm):
    name = forms.CharField(max_length=200, required=True)
    identifier = forms.CharField(max_length=100, required=False)
    category = forms.CharField(max_length=100, required=False)
    subcategory = forms.CharField(max_length=100, required=False)
    standard_ports_text = forms.CharField(max_length=255, required=False)
    technology = forms.CharField(max_length=100, required=False)
    reference = forms.CharField(max_length=255, required=False)
    description = forms.CharField(max_length=200, required=False)
    application_items = CSVModelMultipleChoiceField(
        queryset=ApplicationItem.objects.all(),
        required=False,
        to_field_name="name",
        help_text=_("A list of linked services for standard ports."),
        label=_("Standard Ports (Services)"),
    )

    class Meta:
        model = Application
        fields = (
            "name",
            "owner",
            "identifier",
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "description",
            "tags",
        )


class ApplicationBulkEditForm(PrimaryModelBulkEditForm):
    model = Application
    description = forms.CharField(max_length=200, required=False)
    category = forms.CharField(max_length=100, required=False)
    subcategory = forms.CharField(max_length=100, required=False)
    standard_ports_text = forms.CharField(max_length=255, required=False)
    technology = forms.CharField(max_length=100, required=False)
    reference = forms.CharField(max_length=255, required=False)
    tags = TagFilterField(model)
    application_items = DynamicModelMultipleChoiceField(
        queryset=ApplicationItem.objects.all(),
        required=False,
        label=_("Standard Ports (Services)"),
    )
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet(
            "category",
            "subcategory",
            "application_items",
            "standard_ports_text",
            "technology",
            "reference",
            "description",
        ),
        FieldSet("tags", name=_("Tags")),
    )


