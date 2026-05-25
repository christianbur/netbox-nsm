import json

from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.choices import FamilyChoices
from netbox_nsm.models import ObjectFilter

__all__ = (
    "ObjectFilterForm",
    "ObjectFilterFilterForm",
    "ObjectFilterBulkEditForm",
)


class ObjectFilterForm(PrimaryModelForm):
    description = forms.CharField(max_length=200, required=False)
    rules = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 12, "style": "font-family: monospace;"}),
        label=_("Rules (JSON)"),
        help_text=_(
            'JSON list of rules. Example: [{"match": "destination-address", "value": "10.0.0.0/8", "action": "accept"}]'
        ),
    )

    fieldsets = (
        FieldSet("name", "family", "description", name=_("Filter Object")),
        FieldSet("rules", name=_("Rules")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectFilter
        fields = ("name", "family", "rules", "description", "comments", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.rules:
            self.initial["rules"] = json.dumps(self.instance.rules, indent=2)

    def clean_rules(self):
        raw = self.cleaned_data.get("rules", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")
        if not isinstance(parsed, list):
            raise forms.ValidationError("Rules must be a JSON list.")
        return parsed


class ObjectFilterFilterForm(PrimaryModelFilterSetForm):
    model = ObjectFilter
    family = forms.ChoiceField(
        choices=[("", "---------")] + list(FamilyChoices.CHOICES),
        required=False,
        label=_("Address Family"),
    )
    tag = TagFilterField(model)

    fieldsets = (
        FieldSet("q", "filter_id", "family", "tag"),
    )


class ObjectFilterBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectFilter
    nullable_fields = ("description",)
