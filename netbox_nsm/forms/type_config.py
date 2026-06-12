from django import forms
from django.utils.translation import gettext_lazy as _

from utilities.forms.rendering import FieldSet

from netbox_nsm.objects.object_builder_config import (
    DEFAULT_OBJECT_BUILDER_CONFIG,
    IPAM_SOURCE_KEYS,
    normalize_object_builder_config,
)

__all__ = ("NsmAddressConfigForm", "NsmConfigForm", "config_form_class_for_slug")


def config_form_class_for_slug(slug: str | None):
    if slug == "nsm_address":
        return NsmAddressConfigForm
    return NsmConfigForm


class NsmConfigForm(forms.Form):
    sort_order = forms.IntegerField(
        min_value=0,
        required=True,
        label=_("Sort order"),
        help_text=_("Lower values appear first in the Rule Viewer and Object Config list."),
    )
    display_template = forms.CharField(
        max_length=255,
        required=False,
        initial="{name}",
        label=_("Display Template"),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )

    fieldsets = (FieldSet("sort_order", "display_template", name=_("Rule View")),)

    @classmethod
    def from_config_dict(cls, config: dict, *, slug: str | None = None) -> "NsmConfigForm":
        form_class = config_form_class_for_slug(slug)
        return form_class(
            initial=form_class.initial_from_config_dict(config),
        )

    @classmethod
    def initial_from_config_dict(cls, config: dict) -> dict:
        return {
            "sort_order": config.get("sort_order", 0),
            "display_template": config.get("display_template") or "{name}",
        }

    def to_config_dict(self) -> dict:
        return {
            "sort_order": self.cleaned_data["sort_order"],
            "display_template": self.cleaned_data.get("display_template") or "{name}",
        }


class NsmAddressConfigForm(NsmConfigForm):
    object_builder_enabled = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Object Sync enabled"),
    )
    template_ipaddress = forms.CharField(
        max_length=255,
        required=False,
        label=_("Build template — IP Address"),
        help_text=_("Use {host} for the address without CIDR, or {address} with mask."),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    template_prefix = forms.CharField(
        max_length=255,
        required=False,
        label=_("Build template — Prefix"),
        help_text=_("Use {network} and {prefix_length} (e.g. N-{network}-{prefix_length})."),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    template_iprange = forms.CharField(
        max_length=255,
        required=False,
        label=_("Build template — IP Range"),
        help_text=_("Use {start_host} / {end_host} for bounds without CIDR."),
        widget=forms.TextInput(attrs={"style": "font-family: monospace;"}),
    )
    copy_description_ipaddress = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Copy description from IP Address"),
    )

    fieldsets = (
        FieldSet("sort_order", "display_template", name=_("Rule View")),
        FieldSet(
            "object_builder_enabled",
            "template_ipaddress",
            "copy_description_ipaddress",
            "template_prefix",
            "template_iprange",
            name=_("Object Sync"),
        ),
    )

    @classmethod
    def initial_from_config_dict(cls, config: dict) -> dict:
        initial = super().initial_from_config_dict(config)
        builder = normalize_object_builder_config(config.get("object_builder"))
        sources = builder.get("sources") or {}
        initial.update(
            {
                "object_builder_enabled": bool(builder.get("enabled")),
                "template_ipaddress": (
                    sources.get("ipam.ipaddress", {}).get("build_template") or ""
                ),
                "template_prefix": (
                    sources.get("ipam.prefix", {}).get("build_template") or ""
                ),
                "template_iprange": (
                    sources.get("ipam.iprange", {}).get("build_template") or ""
                ),
                "copy_description_ipaddress": bool(
                    sources.get("ipam.ipaddress", {}).get("copy_description")
                ),
            }
        )
        return initial

    def to_config_dict(self) -> dict:
        result = super().to_config_dict()
        builder = normalize_object_builder_config(DEFAULT_OBJECT_BUILDER_CONFIG)
        builder["enabled"] = bool(self.cleaned_data.get("object_builder_enabled"))
        builder["sources"]["ipam.ipaddress"]["build_template"] = (
            self.cleaned_data.get("template_ipaddress") or ""
        )
        builder["sources"]["ipam.ipaddress"]["copy_description"] = bool(
            self.cleaned_data.get("copy_description_ipaddress")
        )
        builder["sources"]["ipam.prefix"]["build_template"] = (
            self.cleaned_data.get("template_prefix") or ""
        )
        builder["sources"]["ipam.iprange"]["build_template"] = (
            self.cleaned_data.get("template_iprange") or ""
        )
        result["object_builder"] = builder
        return result
