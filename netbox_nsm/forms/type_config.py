from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import ContentTypeChoiceField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import MatchingClassChoices, TypeConfig


class PlacementToggleWidget(forms.CheckboxSelectMultiple):
    """Rendert Placement-Optionen als Bootstrap form-check Checkboxen."""

    def render(self, name, value, attrs=None, renderer=None):
        value = value or []
        html_parts = ['<div class="d-flex gap-4 flex-wrap mt-1">']
        for i, (option_value, option_label) in enumerate(self.choices):
            input_id = f"id_{name}_{i}"
            checked = "checked" if str(option_value) in [str(v) for v in value] else ""
            html_parts.append(
                f'<div class="form-check">'
                f'<input class="form-check-input" type="checkbox" id="{input_id}" '
                f'name="{name}" value="{option_value}" {checked}>'
                f'<label class="form-check-label" for="{input_id}">{option_label}</label>'
                f"</div>"
            )
        html_parts.append("</div>")
        return mark_safe("".join(html_parts))


__all__ = ("TypeConfigForm", "TypeConfigAddForm")

# NetBox-relevante App-Labels (Django-Interna ausgeblendet)
_NETBOX_APPS = [
    "circuits",
    "dcim",
    "extras",
    "ipam",
    "netbox_custom_objects",
    "tenancy",
    "virtualization",
    "vpn",
    "wireless",
]


class TypeConfigForm(NetBoxModelForm):
    """Edit form — content_type ist bereits gesetzt, wird nur angezeigt."""

    matching_class = forms.ChoiceField(
        choices=[("", _("— none —"))] + list(MatchingClassChoices.choices),
        required=False,
        label=_("Matching Class"),
        help_text=_(
            "Semantic category of this type. "
            "Used to automatically derive the matching strategy of a rulebook."
        ),
    )
    display_template = forms.CharField(
        max_length=255,
        required=False,
        initial="{name}",
        label=_("Display Template"),
        help_text=_(
            "Format string for the display name. "
            "Use <code>{field}</code> for a full field value, "
            "<code>{field[0]}</code> for the first character, "
            "<code>{field!u}</code> for uppercase. "
            "Example: <code>{label_type[0]!u}:{name}</code>"
        ),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    allowed_placements = forms.MultipleChoiceField(
        choices=[
            ("source", _("Source")),
            ("destination", _("Destination")),
            ("fixed", _("Fixed")),
        ],
        required=False,
        label=_("Allowed Placements"),
        help_text=_(
            "UI hint: which placements this type may appear in. "
            "Leave empty for no restriction."
        ),
        widget=PlacementToggleWidget,
    )
    inherit_links = forms.BooleanField(
        required=False,
        label=_("Inherit from parent"),
        help_text=_(
            "When enabled, Security Panel shows NSM links of the containing Prefix "
            "on child objects (IP Address, IP Range, sub-Prefix)."
        ),
    )
    inherit_stop_on_own = forms.BooleanField(
        required=False,
        label=_("Stop inheritance if own link present"),
        help_text=_(
            "If the child object already has its own direct NSM link of the same "
            "type, inherited links of that type are suppressed."
        ),
    )

    fieldsets = (
        FieldSet(
            "matching_class",
            "display_template",
            "allowed_placements",
            name=_("Configuration"),
        ),
        FieldSet("inherit_links", "inherit_stop_on_own", name=_("Inheritance")),
    )

    class Meta:
        model = TypeConfig
        fields = (
            "matching_class",
            "display_template",
            "allowed_placements",
            "inherit_links",
            "inherit_stop_on_own",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # allowed_placements: JSON list from DB → convert to list
        instance = kwargs.get("instance")
        if instance and instance.allowed_placements:
            self.initial["allowed_placements"] = instance.allowed_placements

    def clean_allowed_placements(self):
        return list(self.cleaned_data.get("allowed_placements", []))


class TypeConfigAddForm(NetBoxModelForm):
    """Add form — object type selection from all NetBox ContentTypes."""

    content_type = ContentTypeChoiceField(
        queryset=ContentType.objects.filter(app_label__in=_NETBOX_APPS).order_by(
            "app_label", "model"
        ),
        label=_("Object Type"),
        help_text=_("NetBox object type, e.g. IPAM › IP Range or DCIM › Device."),
    )
    matching_class = forms.ChoiceField(
        choices=[("", _("— none —"))] + list(MatchingClassChoices.choices),
        required=False,
        label=_("Matching Class"),
        help_text=_(
            "Semantic category of this type. "
            "Used to automatically derive the matching strategy of a rulebook."
        ),
    )
    display_template = forms.CharField(
        max_length=255,
        required=False,
        initial="{name}",
        label=_("Display Template"),
        help_text=_(
            "Format string for the display name. "
            "Use <code>{field}</code> for a full field value, "
            "<code>{field[0]}</code> for the first character, "
            "<code>{field!u}</code> for uppercase. "
            "Example: <code>{label_type[0]!u}:{name}</code>"
        ),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    allowed_placements = forms.MultipleChoiceField(
        choices=[
            ("source", _("Source")),
            ("destination", _("Destination")),
            ("fixed", _("Fixed")),
        ],
        required=False,
        label=_("Allowed Placements"),
        help_text=_(
            "UI hint: which placements this type may appear in. "
            "Leave empty for no restriction."
        ),
        widget=PlacementToggleWidget,
    )
    inherit_links = forms.BooleanField(
        required=False,
        label=_("Inherit from parent"),
        help_text=_(
            "When enabled, Security Panel shows NSM links of the containing Prefix "
            "on child objects (IP Address, IP Range, sub-Prefix)."
        ),
    )
    inherit_stop_on_own = forms.BooleanField(
        required=False,
        label=_("Stop inheritance if own link present"),
        help_text=_(
            "If the child object already has its own direct NSM link of the same "
            "type, inherited links of that type are suppressed."
        ),
    )

    fieldsets = (
        FieldSet("content_type", name=_("Object Type")),
        FieldSet(
            "matching_class",
            "display_template",
            "allowed_placements",
            name=_("Configuration"),
        ),
        FieldSet("inherit_links", "inherit_stop_on_own", name=_("Inheritance")),
    )

    class Meta:
        model = TypeConfig
        fields = (
            "content_type",
            "matching_class",
            "display_template",
            "allowed_placements",
            "inherit_links",
            "inherit_stop_on_own",
        )

    def clean_allowed_placements(self):
        return list(self.cleaned_data.get("allowed_placements", []))
