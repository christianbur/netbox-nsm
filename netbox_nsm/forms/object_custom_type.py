from django import forms
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelImportForm,
    PrimaryModelForm,
)
from utilities.forms.fields import TagFilterField
from utilities.forms.rendering import FieldSet

from netbox_nsm.models import ObjectCustomType

__all__ = (
    "ObjectCustomTypeForm",
    "ObjectCustomTypeFilterForm",
    "ObjectCustomTypeImportForm",
    "ObjectCustomTypeBulkEditForm",
)


class ObjectCustomTypeForm(PrimaryModelForm):
    name = forms.CharField(max_length=100, required=True, label=_("Type"))
    description = forms.CharField(max_length=200, required=False)
    area = forms.ChoiceField(
        choices=[
            ("srcdst", _("Source/Destination")),
            ("services", _("Services")),
            ("action", _("Action")),
        ],
        initial="srcdst",
        label=_("Area"),
    )
    field_definitions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 10, "style": "font-family: monospace;", "placeholder": '[\n  {"name": "host", "label": "Hostname"},\n  {"name": "port", "label": "Port"}\n]'}),
        label=_("Field Definitions"),
        help_text=_(
            'JSON-Liste von Felddefinitionen. Jedes Feld ist ein Objekt mit den folgenden Schlüsseln:<br>'
            '<ul style="margin-top:4px;margin-bottom:0">'
            '<li><code>name</code> <b>(erforderlich)</b> – interner Feldname (Kleinbuchstaben, kein Leerzeichen), z.B. <code>"host"</code></li>'
            '<li><code>label</code> <b>(erforderlich)</b> – Anzeigename, z.B. <code>"Hostname"</code></li>'
            '<li><code>type</code> – Feldtyp: <code>"text"</code> (Standard), <code>"number"</code>, <code>"boolean"</code>, <code>"url"</code></li>'
            '<li><code>required</code> – <code>true</code> / <code>false</code> (Standard: false)</li>'
            '<li><code>placeholder</code> – Platzhaltertext im Eingabefeld</li>'
            '</ul>'
            '<br>Beispiel:<br>'
            '<pre style="font-size:0.85em;margin:0">[\n'
            '  {"name": "host", "label": "Hostname", "type": "text", "required": true},\n'
            '  {"name": "port", "label": "Port", "type": "number", "placeholder": "443"},\n'
            '  {"name": "enabled", "label": "Aktiv", "type": "boolean"}\n'
            ']</pre>'
        ),
    )
    icon = forms.CharField(
        max_length=100,
        required=False,
        label=_("Icon"),
        help_text=_(
            'MDI-Icon-Name von <a href="https://pictogrammers.com/library/mdi/" target="_blank">'
            'pictogrammers.com</a> — immer mit <code>mdi-</code> Präfix, z.B. <code>mdi-server</code>, '
            '<code>mdi-tag</code>, <code>mdi-puzzle-outline</code>.'
        ),
    )
    fieldsets = (
        FieldSet("name", "area", "icon", "description", name=_("Custom Type")),
        FieldSet("field_definitions", name=_("Field Definitions")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectCustomType
        fields = ("name", "area", "icon", "field_definitions", "description", "comments", "tags")

    def clean_field_definitions(self):
        import json
        value = self.cleaned_data.get("field_definitions", "")
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise forms.ValidationError(_("Must be a JSON list."))
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_("Invalid JSON: %s") % exc)

    def __init__(self, *args, **kwargs):
        import json
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.field_definitions:
            self.initial["field_definitions"] = json.dumps(self.instance.field_definitions, indent=2)


class ObjectCustomTypeFilterForm(PrimaryModelFilterSetForm):
    model = ObjectCustomType
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", name=_("Custom Type")),
    )
    tags = TagFilterField(model)


class ObjectCustomTypeImportForm(PrimaryModelImportForm):
    class Meta:
        model = ObjectCustomType
        fields = ("name", "description", "tags")


class ObjectCustomTypeBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectCustomType
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
