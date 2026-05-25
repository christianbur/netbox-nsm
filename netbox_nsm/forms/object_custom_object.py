import json
from collections import OrderedDict

from django import forms
from django.apps import apps
from django.utils.translation import gettext_lazy as _

from netbox.forms import (
    PrimaryModelBulkEditForm,
    PrimaryModelFilterSetForm,
    PrimaryModelForm,
)
from utilities.forms.fields import DynamicModelChoiceField, TagFilterField
from utilities.forms.rendering import FieldSet, TabbedGroups

from netbox_nsm.models import ObjectCustomObject, ObjectCustomType

__all__ = (
    "ObjectCustomObjectForm",
    "ObjectCustomObjectFilterForm",
    "ObjectCustomObjectBulkEditForm",
)


class ObjectCustomObjectForm(PrimaryModelForm):
    custom_type = DynamicModelChoiceField(
        queryset=ObjectCustomType.objects.all(),
        label=_("Type"),
    )
    description = forms.CharField(max_length=200, required=False)
    table_data = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        label=_("Key/Value Table"),
    )
    fieldsets = (
        FieldSet("custom_type", "name", "description", name=_("Custom Object")),
        FieldSet("tags", name=_("Tags")),
    )

    class Meta:
        model = ObjectCustomObject
        fields = ("custom_type", "name", "description", "comments", "table_data", "tags")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate table_data JSON for editing
        if self.instance.pk and self.instance.table_data:
            self.initial["table_data"] = json.dumps(self.instance.table_data)
        # Dynamically add fields based on custom_type
        ct = None
        if self.instance.pk:
            ct = self.instance.custom_type
        elif "custom_type" in (self.data or {}):
            try:
                ct = ObjectCustomType.objects.get(pk=self.data["custom_type"])
            except (ObjectCustomType.DoesNotExist, ValueError):
                pass
        elif "custom_type" in (self.initial or {}):
            try:
                ct = ObjectCustomType.objects.get(pk=self.initial["custom_type"])
            except (ObjectCustomType.DoesNotExist, ValueError):
                pass
        if ct:
            for field_def in (ct.field_definitions or []):
                fname = f"dyn_{field_def['name']}"
                ftype = field_def.get("type", "text")
                if ftype == "object_ref":
                    model_str = field_def.get("model", "")
                    try:
                        model_class = apps.get_model(model_str)
                        stored = (self.instance.field_data.get(field_def["name"], {}) or {}) if self.instance.pk else {}
                        initial_pk = stored.get("pk") if isinstance(stored, dict) else None
                        self.fields[fname] = DynamicModelChoiceField(
                            queryset=model_class.objects.all(),
                            required=field_def.get("required", False),
                            label=field_def.get("label", field_def["name"]),
                            selector=field_def.get("selector", False),
                        )
                        if initial_pk:
                            self.initial[fname] = initial_pk
                    except (LookupError, Exception):
                        self.fields[fname] = forms.CharField(
                            required=False,
                            label=field_def.get("label", field_def["name"]),
                            initial=self.instance.field_data.get(field_def["name"], "") if self.instance.pk else "",
                        )
                elif ftype == "date":
                    self.fields[fname] = forms.DateField(
                        required=field_def.get("required", False),
                        label=field_def.get("label", field_def["name"]),
                        widget=forms.DateInput(attrs={"type": "date"}),
                        initial=self.instance.field_data.get(field_def["name"], "") if self.instance.pk else "",
                    )
                else:
                    self.fields[fname] = forms.CharField(
                        required=False,
                        label=field_def.get("label", field_def["name"]),
                        widget=forms.Textarea(attrs={"rows": 2}),
                        initial=self.instance.field_data.get(field_def["name"], "") if self.instance.pk else "",
                    )

            # Build fieldsets — fields with the same tab_group become a TabbedGroups block
            grouped = OrderedDict()   # group_name -> [(fname, label)]
            ungrouped = []
            for field_def in (ct.field_definitions or []):
                fname = f"dyn_{field_def['name']}"
                tab_group = field_def.get("tab_group")
                if tab_group:
                    grouped.setdefault(tab_group, []).append(
                        (fname, field_def.get("label", field_def["name"]))
                    )
                else:
                    ungrouped.append(fname)

            dynamic_parts = []
            for group_name, fields in grouped.items():
                if len(fields) > 1:
                    tabbed = TabbedGroups(
                        *[FieldSet(fname, name=_(label)) for fname, label in fields]
                    )
                    dynamic_parts.append(FieldSet(tabbed, name=_(group_name)))
                else:
                    fname = fields[0][0]
                    dynamic_parts.append(FieldSet(fname, name=_(group_name)))

            if ungrouped:
                dynamic_parts.append(FieldSet(*ungrouped, name=_("Custom Fields")))

            if dynamic_parts:
                self.fieldsets = (
                    FieldSet("custom_type", "name", "description", name=_("Custom Object")),
                    *dynamic_parts,
                    FieldSet("table_data", name=_("Key/Value Table")),
                    FieldSet("tags", name=_("Tags")),
                )

    def clean_table_data(self):
        value = self.cleaned_data.get("table_data", "")
        if not value:
            return []
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise forms.ValidationError(_("table_data must be a JSON list."))
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(_("Invalid JSON: %s") % exc)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Collect dynamic field values into field_data
        ct = instance.custom_type
        if ct:
            field_data = {}
            for field_def in (ct.field_definitions or []):
                fname = f"dyn_{field_def['name']}"
                ftype = field_def.get("type", "text")
                val = self.cleaned_data.get(fname)
                if not val:
                    continue
                if ftype == "object_ref":
                    field_data[field_def["name"]] = {
                        "pk": val.pk,
                        "url": val.get_absolute_url(),
                        "str": str(val),
                    }
                elif ftype == "date":
                    field_data[field_def["name"]] = val.isoformat() if hasattr(val, "isoformat") else str(val)
                else:
                    field_data[field_def["name"]] = val
            instance.field_data = field_data
        instance.table_data = self.cleaned_data.get("table_data", [])
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ObjectCustomObjectFilterForm(PrimaryModelFilterSetForm):
    model = ObjectCustomObject
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("custom_type_id", name=_("Custom Object")),
    )
    custom_type_id = DynamicModelChoiceField(
        queryset=ObjectCustomType.objects.all(),
        required=False,
        label=_("Type"),
    )
    tags = TagFilterField(model)


class ObjectCustomObjectBulkEditForm(PrimaryModelBulkEditForm):
    model = ObjectCustomObject
    description = forms.CharField(max_length=200, required=False)
    tags = TagFilterField(model)
    nullable_fields = ["description"]
    fieldsets = (
        FieldSet("description"),
        FieldSet("tags", name=_("Tags")),
    )
