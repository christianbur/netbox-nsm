from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectNAT
from netbox_nsm.models.object_nat import NatObjectTypeChoices

__all__ = (
    "ObjectNATForm",
    "ObjectNATFilterForm",
    "ObjectNATBulkEditForm",
)


class ObjectNATForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)

    try:
        from utilities.forms.fields import DynamicModelChoiceField as _Dyn
        source_address = _Dyn(
            queryset=None,  # set in __init__
            required=False,
            label=_("Source Address"),
        )
        source_prefix = _Dyn(
            queryset=None,
            required=False,
            label=_("Source Prefix"),
        )
        destination_address = _Dyn(
            queryset=None,
            required=False,
            label=_("Destination Address"),
        )
        destination_prefix = _Dyn(
            queryset=None,
            required=False,
            label=_("Destination Prefix"),
        )
    except Exception:
        pass

    fieldsets = (
        FieldSet("name", "nat_type", "description", name=_("NAT Object")),
        FieldSet("source_address", "source_prefix", name=_("Source")),
        FieldSet("destination_address", "destination_prefix", name=_("Destination")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectNAT
        fields = ("name", "nat_type", "source_address", "source_prefix", "destination_address", "destination_prefix", "description", "comments", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ipam.models import IPAddress, Prefix
        self.fields["source_address"] = DynamicModelChoiceField(
            queryset=IPAddress.objects.all(), required=False, label=_("Source Address")
        )
        self.fields["source_prefix"] = DynamicModelChoiceField(
            queryset=Prefix.objects.all(), required=False, label=_("Source Prefix")
        )
        self.fields["destination_address"] = DynamicModelChoiceField(
            queryset=IPAddress.objects.all(), required=False, label=_("Destination Address")
        )
        self.fields["destination_prefix"] = DynamicModelChoiceField(
            queryset=Prefix.objects.all(), required=False, label=_("Destination Prefix")
        )


class ObjectNATFilterForm(PrimaryModelFilterSetForm):
    model = ObjectNAT
    nat_type = forms.ChoiceField(
        choices=[("", "---------")] + list(NatObjectTypeChoices.CHOICES),
        required=False,
        label=_("NAT Type"),
    )
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "nat_type", "tag"),
    )


class ObjectNATBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectNAT
    nullable_fields = ("description",)
