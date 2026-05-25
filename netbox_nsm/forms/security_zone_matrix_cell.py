from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    NetBoxModelFilterSetForm,
)
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import (
    SecurityZone,
    SecurityZoneMatrix,
    SecurityZoneMatrixCell,
    SecurityZoneMatrixPolicy,
)

__all__ = (
    "SecurityZoneMatrixCellForm",
    "SecurityZoneMatrixCellFilterForm",
)


class SecurityZoneMatrixCellForm(forms.ModelForm):
    matrix = DynamicModelChoiceField(
        queryset=SecurityZoneMatrix.objects.all(),
        required=True,
        label=_("Security Zone Matrix"),
    )
    source_zone = DynamicModelChoiceField(
        queryset=SecurityZone.objects.all(),
        required=True,
        label=_("Source Zone"),
    )
    destination_zone = DynamicModelChoiceField(
        queryset=SecurityZone.objects.all(),
        required=True,
        label=_("Destination Zone"),
    )
    policy = DynamicModelChoiceField(
        queryset=SecurityZoneMatrixPolicy.objects.all(),
        required=True,
        label=_("Security Zone Matrix Policy"),
    )
    fieldsets = (
        FieldSet("matrix", "source_zone", "destination_zone", "policy", name=_("Matrix Cell")),
    )

    class Meta:
        model = SecurityZoneMatrixCell
        fields = (
            "matrix",
            "source_zone",
            "destination_zone",
            "policy",
        )


class SecurityZoneMatrixCellFilterForm(NetBoxModelFilterSetForm):
    model = SecurityZoneMatrixCell
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("matrix_id", name=_("Matrix")),
        FieldSet("source_zone_id", "destination_zone_id", "policy_id", name=_("Cell")),
    )
    matrix_id = DynamicModelChoiceField(
        queryset=SecurityZoneMatrix.objects.all(),
        required=False,
        label=_("Security Zone Matrix"),
    )
    source_zone_id = DynamicModelChoiceField(
        queryset=SecurityZone.objects.all(),
        required=False,
        label=_("Source Zone"),
    )
    destination_zone_id = DynamicModelChoiceField(
        queryset=SecurityZone.objects.all(),
        required=False,
        label=_("Destination Zone"),
    )
    policy_id = DynamicModelChoiceField(
        queryset=SecurityZoneMatrixPolicy.objects.all(),
        required=False,
        label=_("Security Zone Matrix Policy"),
    )
