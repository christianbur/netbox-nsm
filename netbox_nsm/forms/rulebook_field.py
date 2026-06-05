import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from netbox_nsm.custom_objects_schema import slugify_identifier
from netbox_nsm.models import (
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    TypeConfig,
)

__all__ = ("RulebookFieldForm", "RulebookFieldTypeForm")

_PLACEMENT_CHOICES = [
    ("source", _("Source")),
    ("destination", _("Destination")),
    ("fixed", _("Fixed")),
]


class RulebookFieldForm(forms.ModelForm):
    """Add / Edit form for a RulebookField."""

    slug = forms.SlugField(
        max_length=50,
        required=False,
        label=_("Slug"),
        help_text=_(
            "Internal identifier, generated from the name (lowercase, no special characters). "
            "Unique within the Rulebook."
        ),
        widget=forms.TextInput(
            attrs={
                "readonly": "readonly",
                "style": "font-family: monospace; background-color: var(--tblr-bg-surface-secondary, #f8f9fa);",
            }
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
            "name",
            "slug",
            "sort_order",
            "placement",
            "visible",
            "max_visible_pills",
        )
        widgets = {
            "name": forms.TextInput(),
            "sort_order": forms.NumberInput(attrs={"min": 0}),
            "max_visible_pills": forms.NumberInput(attrs={"min": 1, "max": 99}),
            "visible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "name": _("Name"),
            "sort_order": _("Sort Order"),
            "visible": _("Visible in policy table"),
            "max_visible_pills": _("Max visible pills"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("visible", "max_visible_pills"):
            if name in self.fields:
                self.fields[name].required = False
        is_new = not (self.instance and self.instance.pk)
        is_system = (
            self.instance
            and self.instance.pk
            and self.instance.field_kind == RulebookFieldKind.SYSTEM
        )
        if is_new and not is_system:
            del self.fields["slug"]
        elif not is_system:
            self.fields["slug"].widget.attrs.setdefault("readonly", "readonly")
        if is_system:
            self.fields["slug"].disabled = True
            self.fields["placement"].disabled = True
            self.fields["placement"].choices = list(_PLACEMENT_CHOICES) + [
                ("system", _("System")),
            ]
            self.fields.pop("max_visible_pills", None)

    @staticmethod
    def slug_from_name(name):
        return slugify_identifier(name)[:50]

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned

        for flag in ("visible",):
            if flag in self.fields:
                cleaned[flag] = bool(cleaned.get(flag))

        if "max_visible_pills" in self.fields:
            raw = cleaned.get("max_visible_pills")
            if raw in (None, ""):
                cleaned["max_visible_pills"] = (
                    self.instance.max_visible_pills
                    if self.instance.pk
                    else RulebookField._meta.get_field("max_visible_pills").default
                )

        is_system = (
            self.instance
            and self.instance.pk
            and self.instance.field_kind == RulebookFieldKind.SYSTEM
        )
        if is_system:
            cleaned["slug"] = self.instance.slug
            cleaned["placement"] = self.instance.placement
            cleaned["field_kind"] = self.instance.field_kind
        else:
            name = (cleaned.get("name") or "").strip()
            if self.instance and self.instance.pk:
                cleaned["slug"] = self.instance.slug
            elif name:
                cleaned["slug"] = self.slug_from_name(name)
            else:
                self.add_error("name", _("Name is required."))

            slug = cleaned.get("slug")
            rulebook_pk = self.data.get("rulebook")
            if slug and rulebook_pk:
                qs = RulebookField.objects.filter(
                    rulebook_id=rulebook_pk, slug=slug
                )
                if self.instance and self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    self.add_error(
                        "name",
                        _(
                            "A field with slug “%(slug)s” already exists in this rulebook."
                        )
                        % {"slug": slug},
                    )

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        for field_name in (
            "visible",
            "sort_order",
            "name",
            "slug",
            "placement",
            "max_visible_pills",
        ):
            if field_name in self.cleaned_data:
                setattr(instance, field_name, self.cleaned_data[field_name])
        if commit:
            instance.save()
        return instance


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
        fields = ("type_config", "sort_order", "visible", "max_items", "name_filter_regex")
        widgets = {
            "sort_order": forms.NumberInput(attrs={"min": 0}),
            "max_items": forms.NumberInput(attrs={"min": 1}),
            "name_filter_regex": forms.TextInput(
                attrs={"placeholder": r"^prod-|Env-Prod"}
            ),
            "visible": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "sort_order": _("Sort Order"),
            "visible": _("Visible in policy table"),
            "max_items": _("Max Items"),
            "name_filter_regex": _("Name filter (regex)"),
        }
        help_texts = {
            "max_items": _(
                "Maximum number of objects of this type per rule. Leave empty for unlimited."
            ),
            "name_filter_regex": _(
                "Optional regex on object name in the rule picker. Empty = all objects."
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "visible" in self.fields:
            self.fields["visible"].required = False

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        if "visible" in self.fields:
            cleaned["visible"] = bool(cleaned.get("visible"))
        return cleaned

    def clean_name_filter_regex(self):
        value = (self.cleaned_data.get("name_filter_regex") or "").strip()
        if not value:
            return ""
        try:
            re.compile(value)
        except re.error as exc:
            raise ValidationError(
                _("Invalid regex: %(error)s") % {"error": exc}
            ) from exc
        return value
