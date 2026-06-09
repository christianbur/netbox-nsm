"""Forms for creating COT-backed rulebooks."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from utilities.forms.widgets import HTMXSelect

from netbox_nsm.rulebooks.cot_hierarchy import (
    deployed_rulebook_parent_choices,
    validate_cot_parent_slug,
)
from netbox_nsm.rulebooks.create import (
    format_rulebook_display_name,
    normalize_rulebook_display_name,
    resolve_rulebook_slug,
)
from netbox_nsm.rulebooks.templates import iter_rulebook_template_choices

__all__ = (
    "CotRulebookCreateForm",
    "CotRulebookDetailForm",
    "CotRulebookMetadataForm",
    "CotRulebookParentForm",
)


class CotRulebookCreateForm(forms.Form):
    template_slug = forms.ChoiceField(
        label=_("Template"),
        choices=[],
        widget=HTMXSelect(),
    )
    name = forms.CharField(
        label=_("Name"),
        help_text=_("Creates rulebook slug nsm_rb_<name>."),
        max_length=100,
    )
    verbose_name = forms.CharField(
        label=_("Display name"),
        required=False,
        max_length=100,
        help_text=_('Optional label in the UI (defaults to "Rulebook <name>").'),
    )
    description = forms.CharField(
        label=_("Description"),
        required=False,
        max_length=200,
        help_text=_("Optional rulebook description (defaults to template text)."),
    )
    parent_slug = forms.ChoiceField(
        label=_("Parent rulebook"),
        required=False,
        help_text=_("Optional parent for hierarchical grouping in the rulebook list."),
        choices=[],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template_slug"].choices = iter_rulebook_template_choices()
        self.fields["parent_slug"].choices = deployed_rulebook_parent_choices()

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise forms.ValidationError(_("Enter a rulebook name."))
        resolve_rulebook_slug(name)
        return name

    def clean(self):
        cleaned = super().clean()
        parent_slug = (cleaned.get("parent_slug") or "").strip() or None
        name = cleaned.get("name")
        if not name:
            return cleaned
        child_slug = resolve_rulebook_slug(name)
        error = validate_cot_parent_slug(child_slug, parent_slug)
        if error:
            raise ValidationError({"parent_slug": error})
        cleaned["parent_slug"] = parent_slug or ""
        verbose_name = (cleaned.get("verbose_name") or "").strip()
        if not verbose_name:
            cleaned["verbose_name"] = format_rulebook_display_name(name)
        return cleaned


class CotRulebookMetadataForm(forms.Form):
    verbose_name = forms.CharField(
        label=_("Display name"),
        max_length=100,
        help_text=_("Label shown in the rulebook list and detail page."),
    )
    description = forms.CharField(
        label=_("Description"),
        required=False,
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *, cot, **kwargs):
        self.cot = cot
        super().__init__(**kwargs)
        if not self.is_bound:
            self.initial.setdefault("verbose_name", cot.verbose_name or cot.name)
            self.initial.setdefault("description", cot.description or "")

    def clean_verbose_name(self):
        value = (self.cleaned_data.get("verbose_name") or "").strip()
        if not value:
            raise forms.ValidationError(_("Enter a display name."))
        return value


class CotRulebookDetailForm(forms.Form):
    """Inline edit form for the COT rulebook detail page."""

    verbose_name = forms.CharField(
        label=_("Display name"),
        max_length=100,
        help_text=_(
            'Sets both singular and plural display names on the custom object type '
            '(defaults to "Rulebook <name>" when the prefix is omitted).'
        ),
    )
    description = forms.CharField(
        label=_("Description"),
        required=False,
        max_length=200,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    parent_slug = forms.ChoiceField(
        label=_("Parent rulebook"),
        required=False,
        help_text=_("Optional parent for hierarchical grouping in the rulebook list."),
        choices=[],
    )
    matrix_tab_enabled = forms.BooleanField(
        label=_("Matrix tab"),
        required=False,
        help_text=_(
            "Show the Matrix tab for rulebooks with source and destination zone columns."
        ),
    )

    def __init__(self, *, cot, rulebook_slug: str, **kwargs):
        self.cot = cot
        self.rulebook_slug = rulebook_slug
        super().__init__(**kwargs)
        from netbox_nsm.rulebooks.cot_hierarchy import (
            get_cot_matrix_tab_enabled,
            get_cot_parent_slug,
            invalid_parent_slugs,
            load_cot_parent_map,
        )
        from netbox_nsm.matrix.cot_matrix_tab_context import cot_rulebook_matrix_capable

        self.matrix_capable = cot_rulebook_matrix_capable(cot)
        if not self.matrix_capable:
            self.fields.pop("matrix_tab_enabled", None)

        parent_map = load_cot_parent_map()
        exclude = invalid_parent_slugs(rulebook_slug, parent_map=parent_map)
        self.fields["parent_slug"].choices = deployed_rulebook_parent_choices(
            exclude_slugs=exclude,
        )
        if not self.is_bound:
            self.initial.setdefault("verbose_name", cot.verbose_name or cot.name)
            self.initial.setdefault("description", cot.description or "")
            self.initial.setdefault(
                "parent_slug",
                get_cot_parent_slug(rulebook_slug) or "",
            )
            if self.matrix_capable:
                self.initial.setdefault(
                    "matrix_tab_enabled",
                    get_cot_matrix_tab_enabled(rulebook_slug),
                )

    def clean_verbose_name(self):
        value = (self.cleaned_data.get("verbose_name") or "").strip()
        if not value:
            raise forms.ValidationError(_("Enter a display name."))
        return normalize_rulebook_display_name(value)

    def clean(self):
        cleaned = super().clean()
        parent_slug = (cleaned.get("parent_slug") or "").strip() or None
        error = validate_cot_parent_slug(self.rulebook_slug, parent_slug)
        if error:
            raise ValidationError({"parent_slug": error})
        cleaned["parent_slug"] = parent_slug or ""
        return cleaned


class CotRulebookParentForm(forms.Form):
    parent_slug = forms.ChoiceField(
        label=_("Parent rulebook"),
        required=False,
        help_text=_("Optional parent for hierarchical grouping in the rulebook list."),
        choices=[],
    )

    def __init__(self, *, rulebook_slug: str, **kwargs):
        self.rulebook_slug = rulebook_slug
        super().__init__(**kwargs)
        from netbox_nsm.rulebooks.cot_hierarchy import (
            get_cot_parent_slug,
            invalid_parent_slugs,
            load_cot_parent_map,
        )

        parent_map = load_cot_parent_map()
        exclude = invalid_parent_slugs(rulebook_slug, parent_map=parent_map)
        self.fields["parent_slug"].choices = deployed_rulebook_parent_choices(
            exclude_slugs=exclude,
        )
        if not self.is_bound:
            self.initial.setdefault(
                "parent_slug",
                get_cot_parent_slug(rulebook_slug) or "",
            )

    def clean(self):
        cleaned = super().clean()
        parent_slug = (cleaned.get("parent_slug") or "").strip() or None
        error = validate_cot_parent_slug(self.rulebook_slug, parent_slug)
        if error:
            raise ValidationError({"parent_slug": error})
        cleaned["parent_slug"] = parent_slug or ""
        return cleaned
