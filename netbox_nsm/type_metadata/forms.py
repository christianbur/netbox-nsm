from django import forms
from django.utils.translation import gettext_lazy as _

from utilities.forms.rendering import FieldSet

from netbox_nsm.core.display_template import (
    DEFAULT_DISPLAY_TEMPLATE,
    normalize_display_template,
    validate_display_template,
)
from netbox_nsm.forms.widgets import BtnCheckMultipleWidget
from netbox_nsm.type_metadata.roles import COT_ROLE_CHOICES, normalize_cot_role

__all__ = ("NsmAddressConfigForm", "NsmConfigForm", "config_form_class_for_slug")

AREA_CHOICES = (
    ("srcdst", _("Source / Destination")),
    ("services", _("Services")),
    ("action", _("Action")),
)

AREA_LABEL_BY_VALUE = dict(AREA_CHOICES)


def area_labels_for_values(values) -> list[str]:
    return [str(AREA_LABEL_BY_VALUE.get(value, value)) for value in (values or [])]


def config_form_class_for_cot(cot) -> type:
    from netbox_nsm.addresses.address_cot_schema import cot_ipam_address_flag

    if cot is not None and cot_ipam_address_flag(cot):
        return NsmAddressConfigForm
    return NsmConfigForm


def config_form_class_for_slug(slug: str | None, *, cot=None):
    if cot is not None:
        return config_form_class_for_cot(cot)
    if slug:
        try:
            from netbox_custom_objects.models import CustomObjectType

            resolved = CustomObjectType.objects.filter(slug=slug).first()
            if resolved is not None:
                return config_form_class_for_cot(resolved)
        except ImportError:
            pass
    return NsmConfigForm


class NsmConfigForm(forms.Form):
    role = forms.ChoiceField(
        choices=COT_ROLE_CHOICES,
        required=True,
        label=_("Role"),
        help_text=_("Semantic role of this Custom Object Type in NSM."),
    )
    sort_order = forms.IntegerField(
        min_value=0,
        required=True,
        label=_("Sort order"),
        help_text=_("Lower values appear first in the Rule Viewer and Object Config list."),
    )
    display_template = forms.CharField(
        max_length=500,
        required=False,
        initial=DEFAULT_DISPLAY_TEMPLATE,
        label=_("Display Template"),
        help_text=_(
            "Jinja2 template for object labels in the Rule Viewer and pickers. "
            "Reference fields by name, e.g. {{ name }} or {{ name | upper }}."
        ),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    areas = forms.MultipleChoiceField(
        choices=AREA_CHOICES,
        required=False,
        label=_("Rule areas"),
        help_text=_("Rulebook columns where objects of this type can be assigned."),
        widget=BtnCheckMultipleWidget,
    )
    linkable = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Linkable"),
    )
    inherit_links = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Inherit links"),
    )
    inherit_stop_on_own = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Inherit stop on own"),
    )
    allow_virtual_groups = forms.BooleanField(
        required=False,
        initial=False,
        label=_("Allow virtual groups"),
    )

    fieldsets = (
        FieldSet("role", name=_("Metadata")),
        FieldSet("sort_order", "display_template", "areas", name=_("Rule View")),
        FieldSet(
            "linkable",
            "inherit_links",
            "inherit_stop_on_own",
            "allow_virtual_groups",
            name=_("Security Links"),
        ),
    )

    @classmethod
    def from_config_dict(cls, config: dict, *, slug: str | None = None) -> "NsmConfigForm":
        form_class = config_form_class_for_slug(slug)
        return form_class(
            initial=form_class.initial_from_config_dict(config),
        )

    @classmethod
    def initial_from_config_dict(cls, config: dict) -> dict:
        links = dict(config.get("links") or {})
        return {
            "role": config.get("role") or "",
            "sort_order": config.get("sort_order", 0),
            "display_template": normalize_display_template(
                config.get("display_template") or DEFAULT_DISPLAY_TEMPLATE
            ),
            "areas": list(config.get("areas") or []),
            "linkable": bool(links.get("linkable", True)),
            "inherit_links": bool(links.get("inherit_links", False)),
            "inherit_stop_on_own": bool(links.get("inherit_stop_on_own", False)),
            "allow_virtual_groups": bool(links.get("allow_virtual_groups", False)),
        }

    def to_config_dict(self) -> dict:
        return {
            "role": self.cleaned_data["role"],
            "sort_order": self.cleaned_data["sort_order"],
            "display_template": self.cleaned_data.get("display_template") or DEFAULT_DISPLAY_TEMPLATE,
            "areas": list(self.cleaned_data.get("areas") or []),
            "links": {
                "linkable": bool(self.cleaned_data.get("linkable")),
                "inherit_links": bool(self.cleaned_data.get("inherit_links")),
                "inherit_stop_on_own": bool(self.cleaned_data.get("inherit_stop_on_own")),
                "allow_virtual_groups": bool(self.cleaned_data.get("allow_virtual_groups")),
            },
        }

    def clean_role(self):
        role = normalize_cot_role(self.cleaned_data.get("role"))
        if not role:
            raise forms.ValidationError(_("Select a valid role."))
        return role

    def clean_display_template(self):
        value = (self.cleaned_data.get("display_template") or "").strip()
        if not value:
            value = DEFAULT_DISPLAY_TEMPLATE
        validate_display_template(value)
        return normalize_display_template(value)


class NsmAddressConfigForm(NsmConfigForm):
    """Same fields as ``NsmConfigForm`` — kept for slug-specific form class routing."""

    pass
