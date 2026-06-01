from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import NetBoxModelForm
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import RulebookField, RulebookFieldType, TypeConfig

__all__ = ("RulebookFieldForm", "RulebookFieldTypeForm")

_SLUG_PRESETS = [
    ("source", "source"),
    ("destination", "destination"),
    ("services", "services"),
    ("action", "action"),
    ("info", "info"),
]

_PLACEMENT_CHOICES = [
    ("source", _("Source")),
    ("destination", _("Destination")),
    ("fixed", _("Fixed")),
]


class RulebookFieldForm(forms.ModelForm):
    """Add / Edit form for a RulebookField."""

    slug = forms.CharField(
        max_length=50,
        label=_("Slug"),
        help_text=_(
            "Interner Bezeichner (z.\u202fB. <code>source</code>, <code>services</code>). "
            "Eindeutig innerhalb des Rulebooks."
        ),
        widget=forms.TextInput(
            attrs={"list": "slug-presets", "style": "font-family: monospace;"}
        ),
    )
    placement = forms.ChoiceField(
        choices=_PLACEMENT_CHOICES,
        label=_("Placement"),
        help_text=_("Traffic-Richtung für dieses Feld."),
    )

    class Meta:
        model = RulebookField
        fields = (
            "slug",
            "name",
            "sort_order",
            "placement",
            "searchable",
            "filterable",
            "facetable",
            "facet_mode",
            "facet_weight",
        )
        widgets = {
            "name": forms.TextInput(),
            "sort_order": forms.NumberInput(attrs={"min": 0}),
            "facet_weight": forms.NumberInput(attrs={"min": 0}),
        }
        labels = {
            "name": _("Name"),
            "sort_order": _("Sort Order"),
            "searchable": _("Searchable"),
            "filterable": _("Filterable"),
            "facetable": _("Facetable"),
            "facet_mode": _("Facet Mode"),
            "facet_weight": _("Facet Weight"),
        }


class RulebookFieldTypeForm(forms.ModelForm):
    """Add / Edit form for a RulebookFieldType (type within a field)."""

    type_config = forms.ModelChoiceField(
        queryset=TypeConfig.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model"
        ),
        label=_("Type Config"),
        help_text=_("Objekt-Typ, der in diesem Feld verwendet werden darf."),
    )

    class Meta:
        model = RulebookFieldType
        fields = ("type_config", "sort_order", "max_items")
        widgets = {
            "sort_order": forms.NumberInput(attrs={"min": 0}),
            "max_items": forms.NumberInput(attrs={"min": 1}),
        }
        labels = {
            "sort_order": _("Sort Order"),
            "max_items": _("Max Items"),
        }
        help_texts = {
            "max_items": _(
                "Maximum number of objects of this type per rule. Leave empty for unlimited."
            ),
        }
