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

    name = forms.CharField(
        max_length=100,
        label=_("Name"),
    )
    slug = forms.CharField(
        max_length=50,
        label=_("Slug"),
        help_text=_(
            "Internal identifier (e.g. 'source', 'services'). "
            "Unique within the Rulebook."
        ),
        widget=forms.TextInput(
            attrs={"list": "slug-presets", "style": "font-family: monospace;"}
        ),
    )
    placement = forms.ChoiceField(
        choices=_PLACEMENT_CHOICES,
        label=_("Placement"),
        help_text=_("Traffic direction for this field."),
    )
    type_configs = forms.ModelMultipleChoiceField(
        queryset=TypeConfig.objects.select_related("content_type").order_by(
            "content_type__app_label", "content_type__model"
        ),
        required=False,
        label=_("Allowed Types"),
        help_text=_("Object types that may be used in this field."),
        widget=forms.SelectMultiple(attrs={"size": "6", "class": "form-select"}),
    )
    max_items = forms.IntegerField(
        min_value=1,
        required=False,
        label=_("Max Items"),
        help_text=_("Maximum objects per rule for the selected types. Leave empty for unlimited."),
    )

    class Meta:
        model = RulebookField
        fields = (
            "name",
            "slug",
            "sort_order",
            "placement",
        )
        widgets = {
            "sort_order": forms.NumberInput(attrs={"min": 0}),
        }
        labels = {
            "sort_order": _("Sort Order"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["type_configs"].initial = TypeConfig.objects.filter(
                rulebook_field_types__field=self.instance
            )
            # Pre-fill max_items from existing type entries (common value if equal)
            vals = list(
                RulebookFieldType.objects.filter(field=self.instance)
                .values_list("max_items", flat=True)
            )
            if vals and len(set(vals)) == 1:
                self.fields["max_items"].initial = vals[0]


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
        fields = ("type_config", "sort_order", "max_items", "show_colored_pills")
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
