from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import ContentTypeChoiceField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import MatchingClassChoices, TypeConfig
from netbox_nsm.panel_sections import get_panel_section_choices

__all__ = ("TypeConfigForm", "TypeConfigAddForm")


class PlacementToggleWidget(forms.CheckboxSelectMultiple):
    """Render panel slug choices as Bootstrap checkboxes."""

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
    name = forms.CharField(max_length=100, required=True, label=_("Name"))
    matching_class = forms.ChoiceField(
        choices=[("", _("— none —"))] + list(MatchingClassChoices.choices),
        required=False,
        label=_("Matching Class"),
    )
    display_template = forms.CharField(
        max_length=255,
        required=False,
        initial="{name}",
        label=_("Display Template"),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    panel_slugs = forms.MultipleChoiceField(
        choices=get_panel_section_choices,
        required=False,
        label=_("Panel slugs"),
        widget=PlacementToggleWidget,
    )
    order_id = forms.IntegerField(
        required=False, min_value=0, initial=100, label=_("Sort order")
    )
    allow_virtual_groups = forms.BooleanField(
        required=False, label=_("Allow Virtual Groups")
    )
    inherit_links = forms.BooleanField(required=False, label=_("Inherit from parent"))
    inherit_stop_on_own = forms.BooleanField(
        required=False, label=_("Stop inheritance if own link present")
    )
    panel_linkable = forms.BooleanField(required=False, label=_("Linkable in panel"))

    fieldsets = (
        FieldSet("name", name=_("Identity")),
        FieldSet(
            "matching_class",
            "display_template",
            "panel_slugs",
            "order_id",
            "allow_virtual_groups",
            "panel_linkable",
            name=_("Configuration"),
        ),
        FieldSet("inherit_links", "inherit_stop_on_own", name=_("Inheritance")),
    )

    class Meta:
        model = TypeConfig
        fields = (
            "name",
            "matching_class",
            "display_template",
            "panel_slugs",
            "order_id",
            "allow_virtual_groups",
            "inherit_links",
            "inherit_stop_on_own",
            "panel_linkable",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance and instance.panel_slugs:
            self.initial["panel_slugs"] = instance.panel_slugs

    def clean_panel_slugs(self):
        return list(self.cleaned_data.get("panel_slugs", []))


class TypeConfigAddForm(TypeConfigForm):
    content_type = ContentTypeChoiceField(
        queryset=ContentType.objects.filter(app_label__in=_NETBOX_APPS).order_by(
            "app_label", "model"
        ),
        label=_("Object Type"),
    )

    fieldsets = (
        FieldSet("name", name=_("Identity")),
        FieldSet("content_type", name=_("Object Type")),
        FieldSet(
            "matching_class",
            "display_template",
            "panel_slugs",
            "order_id",
            "allow_virtual_groups",
            "panel_linkable",
            name=_("Configuration"),
        ),
        FieldSet("inherit_links", "inherit_stop_on_own", name=_("Inheritance")),
    )

    class Meta(TypeConfigForm.Meta):
        fields = TypeConfigForm.Meta.fields + ("content_type",)
