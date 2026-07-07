"""Forms for creating COT-backed rulebooks."""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.cot_hierarchy import (
    deployed_rulebook_parent_choices,
    validate_cot_parent_slug,
)
from netbox_nsm.rulebooks.create import (
    derive_rulebook_name,
    normalize_rulebook_display_name,
    resolve_rulebook_slug,
)
from netbox_nsm.rulebooks.templates import (
    default_rulebook_schema_json,
    extract_rulebook_wizard_metadata_from_schema_yaml,
    validate_substituted_rulebook_schema_yaml,
)

__all__ = (
    "CotRulebookCreateForm",
    "CotRulebookDetailForm",
    "CotRulebookMetadataForm",
    "CotRulebookParentForm",
)


class CotRulebookCreateForm(forms.Form):
    schema_json = forms.CharField(
        label="",
        help_text=_(
            "Portable-schema JSON defining rulebook columns (netbox-custom-objects format)."
        ),
        widget=forms.Textarea(
            attrs={
                "class": "form-control font-monospace nsm-schema-json-editor",
                "rows": 24,
                "spellcheck": "false",
                "wrap": "off",
            }
        ),
    )
    verbose_name = forms.CharField(
        label=_("Display name"),
        max_length=100,
        help_text=_("Label in the rulebook list and detail page."),
    )
    name = forms.CharField(
        label=_("Name"),
        required=False,
        help_text=_(
            "Derived from the display name (lowercase, spaces as _, no special characters). "
            "Creates slug nsm_rb_<name>."
        ),
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
            }
        ),
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
        widget=forms.Select(attrs={"class": "form-select no-ts"}),
        help_text=_("Optional parent for hierarchical grouping in the rulebook list."),
        choices=[],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent_slug"].choices = deployed_rulebook_parent_choices()
        self.schema_metadata_locked: dict[str, str] = {}
        if not self.is_bound:
            self.initial.setdefault("schema_json", default_rulebook_schema_json())
            self.initial.setdefault("name", "")
        self._apply_schema_metadata_lock()

    def _apply_schema_metadata_lock(self) -> None:
        schema_text = (
            self.data.get("schema_json")
            or self.data.get("schema_yaml")
            if self.is_bound
            else self.initial.get("schema_json")
            or self.initial.get("schema_yaml")
            or ""
        )
        locked = extract_rulebook_wizard_metadata_from_schema_yaml(schema_text)
        self.schema_metadata_locked = locked
        if not locked:
            return
        readonly_attrs = {"readonly": "readonly", "tabindex": "-1"}
        if locked.get("verbose_name") is not None:
            if not self.is_bound:
                self.initial["verbose_name"] = locked["verbose_name"]
            self.fields["verbose_name"].widget.attrs.update(readonly_attrs)
        if locked.get("name") is not None:
            if not self.is_bound:
                self.initial["name"] = locked["name"]
            self.fields["name"].widget.attrs.update(readonly_attrs)
        if locked.get("description") is not None:
            if not self.is_bound:
                self.initial["description"] = locked["description"]
            self.fields["description"].widget.attrs.update(readonly_attrs)

    def clean_schema_json(self):
        value = (
            self.cleaned_data.get("schema_json")
            or self.data.get("schema_yaml")
            or ""
        )
        try:
            validate_substituted_rulebook_schema_yaml(
                value,
                display_name=self.data.get("verbose_name", ""),
                name=self.data.get("name", ""),
                description=self.data.get("description", ""),
            )
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages[0]) from exc
        return value

    def clean_verbose_name(self):
        value = (self.cleaned_data.get("verbose_name") or "").strip()
        if not value:
            raise forms.ValidationError(_("Enter a display name."))
        return value

    def clean_name(self):
        value = (self.cleaned_data.get("name") or "").strip()
        raw_verbose_name = (self.data.get("verbose_name") or "").strip()
        if not value and raw_verbose_name:
            value = derive_rulebook_name(raw_verbose_name)
        if not value:
            raise forms.ValidationError(_("Enter a name."))
        if value == "x":
            raise forms.ValidationError(_("Enter a valid name."))
        resolve_rulebook_slug(value)
        return value

    def clean(self):
        cleaned = super().clean()
        locked = extract_rulebook_wizard_metadata_from_schema_yaml(
            cleaned.get("schema_json") or ""
        )
        if locked.get("verbose_name") is not None:
            cleaned["verbose_name"] = locked["verbose_name"]
        if locked.get("name") is not None:
            cleaned["name"] = locked["name"]
        if locked.get("description") is not None:
            cleaned["description"] = locked["description"]

        parent_slug = (cleaned.get("parent_slug") or "").strip() or None
        raw_verbose_name = (cleaned.get("verbose_name") or "").strip()
        name = (cleaned.get("name") or "").strip()
        if not raw_verbose_name or not name:
            return cleaned

        cleaned["name"] = name
        cleaned["verbose_name"] = normalize_rulebook_display_name(raw_verbose_name)

        child_slug = resolve_rulebook_slug(name)
        error = validate_cot_parent_slug(child_slug, parent_slug)
        if error:
            raise ValidationError({"parent_slug": error})
        cleaned["parent_slug"] = parent_slug or ""
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
        widget=forms.Select(attrs={"class": "form-select no-ts"}),
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
    row_group_by_col_id = forms.ChoiceField(
        label=_("Grouped rows"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select no-ts"}),
        help_text=_(
            "Group rules on the Rules tab into a vertical tab column by the "
            "selected column (e.g. Source - Zone). Choose None to disable."
        ),
    )

    def __init__(self, *, cot, rulebook_slug: str, **kwargs):
        self.cot = cot
        self.rulebook_slug = rulebook_slug
        super().__init__(**kwargs)
        from netbox_nsm.rulebooks.cot_hierarchy import (
            get_cot_matrix_tab_enabled,
            get_cot_parent_slug,
            get_cot_row_group_by_col_id,
            invalid_parent_slugs,
            load_cot_parent_map,
        )
        from netbox_nsm.rulebooks.matrix.cot_matrix_tab_context import cot_rulebook_matrix_capable
        from netbox_nsm.rulebooks.rules_row_grouping import build_cot_row_group_column_choices

        self.fields["row_group_by_col_id"].choices = build_cot_row_group_column_choices(
            cot
        )
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
            self.initial.setdefault(
                "row_group_by_col_id",
                get_cot_row_group_by_col_id(rulebook_slug),
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
        row_group_col_id = (cleaned.get("row_group_by_col_id") or "").strip()
        valid_ids = {
            choice[0] for choice in self.fields["row_group_by_col_id"].choices
        }
        if row_group_col_id not in valid_ids:
            raise ValidationError(
                {"row_group_by_col_id": _("Select a valid column.")}
            )
        cleaned["row_group_by_col_id"] = row_group_col_id
        return cleaned


class CotRulebookParentForm(forms.Form):
    parent_slug = forms.ChoiceField(
        label=_("Parent rulebook"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select no-ts"}),
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
