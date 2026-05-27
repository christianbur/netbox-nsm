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

from netbox_nsm.models import SecurityObjectType

__all__ = (
    "SecurityObjectTypeForm",
    "SecurityObjectTypeFilterForm",
    "SecurityObjectTypeImportForm",
    "SecurityObjectTypeBulkEditForm",
)


class SecurityObjectTypeForm(PrimaryModelForm):
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
            'JSON list of field definitions. Each field is an object with the following keys:<br>'
            '<ul style="margin-top:4px;margin-bottom:0">'
            '<li><code>name</code> <b>(required)</b> – internal field name (lowercase, no spaces), e.g. <code>"host"</code></li>'
            '<li><code>label</code> <b>(required)</b> – display name, e.g. <code>"Hostname"</code></li>'
            '<li><code>type</code> – field type: <code>"text"</code> (default), <code>"number"</code>, <code>"boolean"</code>, <code>"url"</code>, <code>"date"</code> (date picker), <code>"markdown"</code>, <code>"object_ref"</code></li>'
            '<li><code>required</code> – <code>true</code> / <code>false</code> (default: false)</li>'
            '<li><code>placeholder</code> – placeholder text for the input field</li>'
            '</ul>'
            '<br>Example:<br>'
            '<pre style="font-size:0.85em;margin:0">[\n'
            '  {"name": "host", "label": "Hostname", "type": "text", "required": true},\n'
            '  {"name": "port", "label": "Port", "type": "number", "placeholder": "443"},\n'
            '  {"name": "enabled", "label": "Active", "type": "boolean"}\n'
            ']</pre>'
        ),
    )
    icon = forms.CharField(
        max_length=100,
        required=False,
        label=_("Icon"),
        help_text=_(
            'MDI icon name from <a href="https://pictogrammers.com/library/mdi/" target="_blank">'
            'pictogrammers.com</a> — always with <code>mdi-</code> prefix, e.g. <code>mdi-server</code>, '
            '<code>mdi-tag</code>, <code>mdi-puzzle-outline</code>.'
        ),
    )
    display_template = forms.CharField(
        max_length=500,
        required=False,
        label=_("Display Template"),
        help_text=_(
            'Template string for rendering objects of this type. '
            'Use <code>{name}</code> and field data keys such as <code>{port}</code>, '
            '<code>{protocol}</code>. Example: <code>{name} ({port}/{protocol})</code>. '
            'Leave empty to use the object name only.'
        ),
    )
    fieldsets = (
        FieldSet("name", "area", "icon", "display_template", "description", name=_("Custom Type")),
        FieldSet("field_definitions", name=_("Field Definitions")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = SecurityObjectType
        fields = ("name", "area", "icon", "display_template", "field_definitions", "description", "comments", "tags")

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


class SecurityObjectTypeFilterForm(PrimaryModelFilterSetForm):
    model = SecurityObjectType
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("name", name=_("Custom Type")),
    )
    tags = TagFilterField(model)


class SecurityObjectTypeImportForm(PrimaryModelImportForm):
    class Meta:
        model = SecurityObjectType
        fields = ("name", "description", "tags")


class SecurityObjectTypeBulkEditForm(PrimaryModelBulkEditForm):
    model = SecurityObjectType
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
