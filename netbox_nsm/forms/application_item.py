from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)

from utilities.forms.rendering import FieldSet
from utilities.forms.fields import (
    TagFilterField,
    CommentField,
)

from netbox_nsm.models import (
    ApplicationItem,
)
from netbox_nsm.choices import ProtocolChoices
from netbox_nsm.mixins import PortsForm

__all__ = (
    "ApplicationItemForm",
    "ApplicationItemFilterForm",
    "ApplicationItemImportForm",
    "ApplicationItemBulkEditForm",
)


class ApplicationItemForm(PortsForm, PrimaryModelForm):
    name = forms.CharField(max_length=255, required=True)
    protocol = forms.ChoiceField(
        choices=ProtocolChoices,
        required=True,
    )
    destination_ports = PortsForm.base_fields["destination_ports"]
    destination_ports.required = True
    description = forms.CharField(max_length=200, required=False)
    fieldsets = (
        FieldSet(
            "name",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
            name=_("Application Items"),
        ),
        FieldSet("tags", name=_("Tags")),
    )
    comments = CommentField()

    class Meta:
        model = ApplicationItem
        fields = [
            "name",
            "owner",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
            "comments",
            "tags",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Model stores protocol as array; edit form shows a single selected value.
        if self.instance and self.instance.pk and self.instance.protocol:
            self.initial["protocol"] = self.instance.protocol[0]

    def clean_protocol(self):
        protocol = self.cleaned_data.get("protocol")
        return [protocol] if protocol else []

    def save(self, commit=True):
        if self.instance.pk is None and self.instance.index is None:
            self.instance.index = ApplicationItem.get_next_index()
        return super().save(commit=commit)


class ApplicationItemFilterForm(PortsForm, PrimaryModelFilterSetForm):
    model = ApplicationItem
    fieldsets = (
        FieldSet("q", "filter_id", "tag", "owner_id"),
        FieldSet(
            "name",
            "index",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
            name=_("Application Items"),
        ),
    )
    index = forms.IntegerField(required=False)
    protocol = forms.MultipleChoiceField(
        choices=ProtocolChoices,
        required=False,
    )
    tags = TagFilterField(model)


class ApplicationItemImportForm(PortsForm, PrimaryModelImportForm):
    name = forms.CharField(max_length=255, required=True)
    index = forms.IntegerField(
        required=True,
        label=_("Index"),
    )
    description = forms.CharField(max_length=200, required=False)
    protocol = forms.ChoiceField(
        choices=ProtocolChoices,
        required=True,
    )

    def clean_protocol(self):
        protocol = self.cleaned_data.get("protocol")
        return [protocol] if protocol else []

    class Meta:
        model = ApplicationItem
        fields = (
            "name",
            "owner",
            "index",
            "protocol",
            "destination_ports",
            "source_ports",
            "description",
            "tags",
        )


class ApplicationItemBulkEditForm(PrimaryModelBulkEditForm):
    model = ApplicationItem
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    protocol = forms.MultipleChoiceField(
        choices=ProtocolChoices,
        required=False,
    )
    nullable_fields = [
        "description",
    ]
    fieldsets = (
        FieldSet("protocol", "description"),
        FieldSet("tags", name=_("Tags")),
    )
