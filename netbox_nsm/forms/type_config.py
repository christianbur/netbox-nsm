from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox.forms import NetBoxModelForm
from utilities.forms.fields import (
    ContentTypeChoiceField,
    ContentTypeMultipleChoiceField,
)
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import MatchingClassChoices, PANEL_LINKABLE_DISABLED, TypeConfig

__all__ = ("TypeConfigForm", "TypeConfigAddForm")


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
    panel_linkable_types = ContentTypeMultipleChoiceField(
        queryset=ContentType.objects.filter(app_label__in=_NETBOX_APPS).order_by(
            "app_label", "model"
        ),
        required=False,
        label=_("Linkable in panel"),
        help_text=_(
            "NetBox object types that may assign this NSM type via + Assign in the "
            "Security Panel. Leave empty to allow all object types."
        ),
    )

    fieldsets = (
        FieldSet("name", name=_("Identity")),
        FieldSet(
            "matching_class",
            "display_template",
            "panel_linkable_types",
            name=_("Configuration"),
        ),
    )

    class Meta:
        model = TypeConfig
        fields = (
            "name",
            "matching_class",
            "display_template",
            "panel_linkable_types",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        if instance and instance.pk:
            ct_ids = [
                int(pk)
                for pk in (instance.panel_linkable_types or [])
                if int(pk) != PANEL_LINKABLE_DISABLED
            ]
            if ct_ids:
                self.initial["panel_linkable_types"] = ct_ids

    def clean_panel_linkable_types(self):
        selected = self.cleaned_data.get("panel_linkable_types")
        if not selected:
            return []
        return list(selected.values_list("pk", flat=True))

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.panel_linkable_types = self.cleaned_data.get(
            "panel_linkable_types", []
        )
        if commit and instance.pk and hasattr(instance, "_prechange_snapshot"):
            from netbox_nsm.core.changelog_utils import apply_type_config_changelog_message

            apply_type_config_changelog_message(instance)
        if commit:
            instance.save()
        return instance


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
            "panel_linkable_types",
            name=_("Configuration"),
        ),
    )

    class Meta(TypeConfigForm.Meta):
        fields = TypeConfigForm.Meta.fields + ("content_type",)
