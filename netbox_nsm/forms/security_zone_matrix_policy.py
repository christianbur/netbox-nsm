from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.fields import CSVChoiceField
from utilities.forms.rendering import FieldSet

from netbox_nsm.choices import ActionChoices
from netbox_nsm.models import SecurityZoneMatrixPolicy

__all__ = (
    "SecurityZoneMatrixPolicyForm",
    "SecurityZoneMatrixPolicyFilterForm",
    "SecurityZoneMatrixPolicyImportForm",
    "SecurityZoneMatrixPolicyBulkEditForm",
)

COLOR_CHOICES = (
    ("green", "Green"),
    ("red", "Red"),
    ("orange", "Orange"),
    ("blue", "Blue"),
    ("gray", "Gray"),
)


class SecurityZoneMatrixPolicyForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True)
    action = forms.ChoiceField(
        choices=((ActionChoices.PERMIT, "Permit"), (ActionChoices.DENY, "Deny")),
        required=True,
    )
    color = forms.ChoiceField(choices=COLOR_CHOICES, required=True)
    fieldsets = (
        FieldSet("name", "action", "color", name=_("Security Zone Matrix Policy")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityZoneMatrixPolicy
        fields = (
            "name",
            "action",
            "color",
            "description",
            "comments",
            "tags",
        )


class SecurityZoneMatrixPolicyFilterForm(PrimaryModelFilterSetForm):
    model = SecurityZoneMatrixPolicy
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", "action", "color", name=_("Security Zone Matrix Policy")),
    )
    action = forms.ChoiceField(
        required=False,
        choices=(
            ("", "------"),
            (ActionChoices.PERMIT, "Permit"),
            (ActionChoices.DENY, "Deny"),
        ),
    )
    color = forms.ChoiceField(required=False, choices=(("", "------"),) + COLOR_CHOICES)
    tags = TagFilterField(model)


class SecurityZoneMatrixPolicyImportForm(PrimaryModelImportForm):
    action = CSVChoiceField(
        choices=((ActionChoices.PERMIT, "Permit"), (ActionChoices.DENY, "Deny")),
        required=True,
    )
    color = CSVChoiceField(choices=COLOR_CHOICES, required=True)

    class Meta:
        model = SecurityZoneMatrixPolicy
        fields = (
            "name",
            "action",
            "color",
            "description",
            "tags",
        )


class SecurityZoneMatrixPolicyBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityZoneMatrixPolicy
    action = forms.ChoiceField(
        choices=((ActionChoices.PERMIT, "Permit"), (ActionChoices.DENY, "Deny")),
        required=False,
    )
    color = forms.ChoiceField(choices=COLOR_CHOICES, required=False)
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("action", "color", "description"),
        FieldSet("tags", name=_("Tags")),
    )
