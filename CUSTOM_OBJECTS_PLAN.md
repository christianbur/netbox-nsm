# Plan: Custom Security Objects für NetBox NSM

## Ziel
- `/object/custom/` als eigenen Bereich mit zwei Sub-Tabs: **Types** + **Objects**
- `ObjectCustomType` erhält `area`-Feld (Auswahlmenü) + konfigurierbare Textfeld-Definitionen
- `ObjectCustomObject` als neue Instanzklasse (name, FK→type, JSON-Felder, Key/Value-Tabelle)
- Custom Types erscheinen als dynamische Sub-Tabs in den jeweiligen Area-Haupttabs
- Policy-Integration: Custom Objects sind in SecurityZonePolicyRule verwendbar (area-basiert)

---

## Aktueller Zustand (Stand Pause)

### Bereits implementiert
- `ObjectCustomType` Model + Migration 0053 (aber **fehlerhaft**: `owner_id` Spalte fehlt in DB)
- Table, FilterSet, Form, View für ObjectCustomType → vorhanden aber owner_id-Fehler
- Tab "custom" in ObjectsSrcDstTabsView eingetragen
- Template `objectcustomtype.html` vorhanden

### Offene Probleme
1. **DB-Fehler**: `column netbox_nsm_objectcustomtype.owner_id does not exist`
   - Migration 0053 lief durch, hat aber `owner_id` FK vergessen
   - Muss über Migration 0054 per `AddField` nachträglich hinzugefügt werden
2. **Duplikate in urls.py**: `object/custom/` ist mehrfach registriert (zeigt auf ObjectsSrcDstTabsView + ObjectCustomType Edit View)
3. **Navigation**: "Custom Types" Menüeintrag muss entfernt werden
4. **Alter "custom" Tab** in ObjectsSrcDstTabsView muss durch neuen dedizierten View ersetzt werden

---

## Phase 1: DB-Fix + Bereinigung

### 1a. Migration 0054 – owner_id hinzufügen
Datei: `netbox_nsm/migrations/0054_objectcustomtype_owner.py`
```python
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0053_objectcustomtype"),
        ("users", "0015_owner"),
    ]
    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="owner",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="users.owner"
            ),
        ),
    ]
```

### 1b. urls.py bereinigen
ENTFERNEN:
- `path("object/custom/", ObjectsSrcDstTabsView.as_view(), name="objectcustomtype_list")`
- `path("object/custom/add/", ObjectCustomTypeEditView.as_view(), name="objectcustomtype_add")`
- `path("object/custom/<int:pk>/", ObjectCustomTypeView.as_view(), name="objectcustomtype")`
- `path("object/custom/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustomtype")))`
- `path("object/custom/edit/", ...)`
- `path("object/custom/delete/", ...)`
- `path("object/custom/import/", ...)`
- `# Custom Types - handled under object/custom/` Kommentar

HINZUFÜGEN (vor dem generischen `object/<str:tab>/`):
```python
# Custom area – eigener View
path("object/custom/", ObjectsCustomAreaView.as_view(), name="object_custom_root"),
path("object/custom/<str:tab>/", ObjectsCustomAreaView.as_view(), name="object_custom_tab"),
# Detail-URLs für Custom Types und Custom Objects
path("object/custom/types/add/", ObjectCustomTypeEditView.as_view(), name="objectcustomtype_add"),
path("object/custom/types/<int:pk>/", ObjectCustomTypeView.as_view(), name="objectcustomtype"),
path("object/custom/objects/add/", ObjectCustomEditView.as_view(), name="objectcustom_add"),
path("object/custom/objects/<int:pk>/", ObjectCustomView.as_view(), name="objectcustom"),
# Bulk-Operationen
path("custom-types/", include(get_model_urls("netbox_nsm", "objectcustomtype", detail=False))),
path("custom-types/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustomtype"))),
path("custom-objects/", include(get_model_urls("netbox_nsm", "objectcustom", detail=False))),
path("custom-objects/<int:pk>/", include(get_model_urls("netbox_nsm", "objectcustom"))),
```

### 1c. Navigation bereinigen
In `navigation.py`: Den `PluginMenuItem` für "Custom Types" (`objectcustomtype_list`) aus `objects_menu_items` entfernen.

### 1d. ObjectsSrcDstTabsView bereinigen
In `views/object_tabs.py`:
- Den statischen "custom" Tab + Gruppe entfernen (wird durch dynamische ct_*-Tabs ersetzt)
- Den "Custom" main_tab-Eintrag BEHALTEN (→ href `/plugins/netbox-nsm/object/custom/types/`)
- `MODEL_BY_TAB["custom"]` und `TABLE_COLUMNS_BY_TAB["custom"]` entfernen

---

## Phase 2: ObjectCustomType erweitern

### 2a. Migration 0055 – area + field_definitions
Datei: `netbox_nsm/migrations/0055_objectcustomtype_area_fields.py`
```python
class Migration(migrations.Migration):
    dependencies = [("netbox_nsm", "0054_objectcustomtype_owner")]
    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="area",
            field=models.CharField(
                max_length=20,
                choices=[("srcdst","Source/Destination"),("services","Services"),("action","Action")],
                default="srcdst",
            ),
        ),
        migrations.AddField(
            model_name="objectcustomtype",
            name="field_definitions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
```

### 2b. Model `object_custom_type.py` aktualisieren
Neue Felder:
```python
class AreaChoices(models.TextChoices):
    SRCDST = "srcdst", _("Source/Destination")
    SERVICES = "services", _("Services")
    ACTION = "action", _("Action")

class ObjectCustomType(PrimaryModel):
    name = models.CharField(max_length=100, unique=True)
    area = models.CharField(max_length=20, choices=AreaChoices.choices, default=AreaChoices.SRCDST)
    field_definitions = models.JSONField(
        blank=True, default=list,
        help_text='[{"name": "slug", "label": "Readable label"}, ...]'
    )
```

### 2c. Form `forms/object_custom_type.py` aktualisieren
- `area` als ChoiceField hinzufügen
- `field_definitions` als JSON-Textarea mit Hilfetext:
  `[{"name": "notes", "label": "Notes"}, {"name": "config", "label": "Configuration"}]`
- Custom `JSONListField` Formfeld-Klasse für JSON-Serialisierung

### 2d. Table + Template aktualisieren
- `ObjectCustomTypeTable`: `area`-Spalte ergänzen
- `objectcustomtype.html`: area + field_definitions anzeigen

---

## Phase 3: ObjectCustomObject – Neues Modell

### 3a. Migration 0056 – ObjectCustomObject erstellen
Datei: `netbox_nsm/migrations/0056_objectcustomobject.py`
Felder:
- `name` CharField(max_length=100)
- `custom_type` FK → ObjectCustomType (PROTECT)
- `field_data` JSONField(default=dict) – `{"field_slug": "markdown content"}`
- `table_data` JSONField(default=list) – `[{"key": "...", "value": "..."}]`
- Standard-PrimaryModel-Felder: created, last_updated, custom_field_data, description, comments, owner, tags
- UniqueConstraint: (custom_type, name)

### 3b. Model `models/object_custom_object.py`
```python
class ObjectCustomObject(PrimaryModel):
    name = models.CharField(max_length=100)
    custom_type = models.ForeignKey("netbox_nsm.ObjectCustomType", on_delete=models.PROTECT, related_name="objects")
    field_data = models.JSONField(blank=True, default=dict)
    table_data = models.JSONField(blank=True, default=list)

    class Meta:
        verbose_name = _("Custom Object")
        verbose_name_plural = _("Custom Objects")
        ordering = ("custom_type", "name")
        constraints = [UniqueConstraint(fields=("custom_type","name"), name="...")]

    def get_absolute_url(self):
        return reverse("plugins:netbox_nsm:objectcustom", args=[self.pk])
```

### 3c. Form `forms/object_custom_object.py`
**Dynamische Felder** basierend auf dem gewählten CustomType:
- In `__init__`: wenn `custom_type` bekannt (Instanz oder POST-Daten), werden für jede
  `field_def` in `custom_type.field_definitions` ein `CharField(widget=Textarea)` dynamisch erzeugt
- `table_data` als HiddenInput + JS-basierter Tabellen-Editor (Add Row / Delete Row)
- In `save()`: field_data aus den dynamischen Feldern zusammenstellen, table_data parsen

### 3d. Table `tables/object_custom_object.py`
Spalten: name (Link), custom_type (Link), description, tags

### 3e. FilterSet `filtersets/object_custom_object.py`
Filter: name, custom_type_id, description

### 3f. Views `views/object_custom_object.py`
Standard-CRUD-Views (wie ObjectAction): ObjectView, ListView, EditView, DeleteView,
BulkEditView, BulkDeleteView, BulkImportView

### 3g. Template `templates/netbox_nsm/objectcustom.html`
Detail-View zeigt:
- name, custom_type, description
- Dynamische Felder (aus field_data, gerendert als Markdown)
- Key/Value-Tabelle (aus table_data)

---

## Phase 4: /object/custom/ Dedicated Area View

### 4a. View `views/object_custom_tabs.py` (oder in object_tabs.py)
```python
class ObjectsCustomAreaView(TemplateView):
    template_name = "netbox_nsm/object_custom_area.html"

    SUB_TABS = [
        {"slug": "types", "label": "Types", "add_url_name": "plugins:netbox_nsm:objectcustomtype_add"},
        {"slug": "objects", "label": "Objects", "add_url_name": "plugins:netbox_nsm:objectcustom_add"},
    ]

    def get(self, request, *args, **kwargs):
        if not kwargs.get("tab"):
            return redirect("plugins:netbox_nsm:object_custom_tab", tab="types")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tab_slug = kwargs.get("tab", "types")
        if tab_slug == "types":
            rows = [...ObjectCustomType...]
            columns = [{"label": "Type", ...}, {"label": "Area", ...}, {"label": "Description", ...}]
        else:  # objects
            rows = [...ObjectCustomObject...]
            columns = [{"label": "Name", ...}, {"label": "Type", ...}, {"label": "Description", ...}]
        context.update({"active_tab": tab_slug, "sub_tabs": self.SUB_TABS, ...})
        return context
```

### 4b. Template `templates/netbox_nsm/object_custom_area.html`
Einfache zwei-Tab-Ansicht (Types / Objects) mit Add-Button und Tabelle.
Optional: Kann `object_tabs.html` Basis-Template verwenden oder eigenes Template.

### 4c. ObjectsSrcDstTabsView: Dynamische Custom-Type Sub-Tabs
In `get_context_data`:
```python
# Dynamische Custom-Type Tabs laden
from netbox_nsm.models import ObjectCustomType
custom_types = list(ObjectCustomType.objects.all().order_by("area","name"))

# Für jede Area werden entsprechende Tabs hinzugefügt
for ct in custom_types:
    tab_slug = f"ct_{ct.pk}"
    custom_tab = {"slug": tab_slug, "label": ct.name, "add_url_name": "plugins:netbox_nsm:objectcustom_add"}
    if ct.area == "srcdst":
        # Tab-Gruppe "srcdst" bekommt diesen Tab
    elif ct.area == "services":
        # Tab-Gruppe "services" bekommt diesen Tab
    elif ct.area == "action":
        # Tab-Gruppe "action" bekommt diesen Tab
```

In `_get_objects_for_tab`:
```python
if tab_slug.startswith("ct_"):
    pk = int(tab_slug[3:])
    return list(ObjectCustomObject.objects.filter(custom_type_id=pk))
```

In `_get_table_rows_for_tab` für ct_*-Slugs:
```python
row = {
    "url": f"/plugins/netbox-nsm/object/custom/objects/{obj.pk}/",
    "cells": [obj.name, str(obj.custom_type), obj.description or "-"]
}
```

### 4d. "Custom" Main-Tab in ObjectsSrcDstTabsView
```python
{
    "slug": "custom",
    "label": "Custom",
    "href": "/plugins/netbox-nsm/object/custom/types/",
}
```
`active_main_tab = "custom"` wenn tab_slug.startswith("ct_") oder tab_slug == "custom"

---

## Phase 5: Policy-Integration

### 5a. Migration 0057 – M2M-Felder in SecurityZonePolicyRule
Drei separate M2M-Felder für die drei Areas:
```python
migrations.AddField(model_name="securityzonepolicyrule", name="custom_srcdst_objects",
    field=models.ManyToManyField(blank=True, to="netbox_nsm.objectcustomobject",
        related_name="policyrule_srcdst_set")),
migrations.AddField(model_name="securityzonepolicyrule", name="custom_service_objects", ...),
migrations.AddField(model_name="securityzonepolicyrule", name="custom_action_objects", ...),
```

### 5b. Model `security_zone_policy_rulebook.py`
```python
custom_srcdst_objects = models.ManyToManyField(
    to="netbox_nsm.ObjectCustomObject", blank=True, related_name="policyrule_srcdst_set"
)
custom_service_objects = models.ManyToManyField(...)
custom_action_objects = models.ManyToManyField(...)
```

### 5c. Form `forms/security_zone_policy_rulebook.py`
In `SecurityZonePolicyRuleForm`:
```python
custom_srcdst_objects = forms.ModelMultipleChoiceField(
    queryset=ObjectCustomObject.objects.filter(custom_type__area="srcdst"),
    required=False, label=_("Custom Src/Dst Objects"),
)
custom_service_objects = forms.ModelMultipleChoiceField(
    queryset=ObjectCustomObject.objects.filter(custom_type__area="services"),
    required=False, label=_("Custom Service Objects"),
)
custom_action_objects = forms.ModelMultipleChoiceField(
    queryset=ObjectCustomObject.objects.filter(custom_type__area="action"),
    required=False, label=_("Custom Action Objects"),
)
```

In `fieldsets`: `custom_srcdst_objects` zu Source/Destination hinzufügen, usw.

### 5d. Serializer `api/serializers_/security_zone_policy_rulebook.py`
`custom_srcdst_objects`, `custom_service_objects`, `custom_action_objects` in fields hinzufügen

---

## Dateien-Übersicht

### Neu zu erstellen
| Datei | Inhalt |
|-------|--------|
| `migrations/0054_objectcustomtype_owner.py` | owner FK hinzufügen |
| `migrations/0055_objectcustomtype_area_fields.py` | area + field_definitions |
| `migrations/0056_objectcustomobject.py` | ObjectCustomObject Modell |
| `migrations/0057_policyrule_custom_objects.py` | M2M Felder in PolicyRule |
| `models/object_custom_object.py` | ObjectCustomObject |
| `tables/object_custom_object.py` | ObjectCustomObjectTable |
| `filtersets/object_custom_object.py` | ObjectCustomObjectFilterSet |
| `forms/object_custom_object.py` | Dynamisches Form |
| `views/object_custom_object.py` | CRUD Views |
| `views/object_custom_tabs.py` | ObjectsCustomAreaView |
| `templates/netbox_nsm/objectcustom.html` | Detail-Template |
| `templates/netbox_nsm/object_custom_area.html` | Area-Tab-Template |

### Zu modifizieren
| Datei | Änderung |
|-------|----------|
| `models/object_custom_type.py` | area + field_definitions Felder |
| `models/__init__.py` | ObjectCustomObject importieren |
| `tables/object_custom_type.py` | area-Spalte |
| `tables/__init__.py` | ObjectCustomObjectTable importieren |
| `filtersets/object_custom_type.py` | area Filter |
| `filtersets/__init__.py` | ObjectCustomObjectFilterSet importieren |
| `forms/object_custom_type.py` | area Feld + field_definitions JSON-Widget |
| `forms/__init__.py` | ObjectCustomObject Forms importieren |
| `views/__init__.py` | ObjectCustomObject Views + CustomAreaView importieren |
| `views/object_tabs.py` | Dynamische ct_*-Tabs; "custom" Gruppe/Tab entfernen |
| `urls.py` | Custom URLs neu strukturieren, custom-types/ entfernen |
| `navigation.py` | "Custom Types" Menüeintrag entfernen |
| `models/security_zone_policy_rulebook.py` | custom_*_objects M2M |
| `forms/security_zone_policy_rulebook.py` | custom_*_objects Formfelder |
| `api/serializers_/security_zone_policy_rulebook.py` | Felder ergänzen |
| `templates/netbox_nsm/objectcustomtype.html` | area + field_definitions anzeigen |

---

## Offene Designfragen
1. **field_definitions Widget**: Für die erste Version JSON-Textarea (einfach). Später JS-Widget.
2. **table_data Widget**: Für die erste Version HiddenInput + JS inline im Template.
3. **Reload beim Type-Wechsel**: Im ObjectCustomObject-Form, wenn Type geändert wird,
   müssen die dynamischen Felder neu geladen werden. Vorschlag: Nach Type-Auswahl
   Seite neu laden mit `?custom_type=<pk>` als Query-Parameter.

---

## Build-Befehl
```bash
cd /home/christian/homelab/docker/netbox && \
  docker compose build netbox && \
  docker compose up -d netbox
```

## Verifikation
1. `GET /plugins/netbox-nsm/object/custom/` → zeigt Tabs "Types" + "Objects" ohne Server Error
2. Custom Type "label-ng" mit area=srcdst anlegen → erscheint als Sub-Tab neben "Groups"
3. Custom Object mit dynamischen Feldern anlegen → Felder werden gespeichert + angezeigt
4. In Policy Rule → custom_srcdst_objects / _service_objects / _action_objects wählbar
5. `docker logs netbox | grep -i error` → keine neuen Fehler
