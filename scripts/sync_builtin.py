#!/usr/bin/env python3
"""Standalone-Skript zum Synchronisieren der builtin COTs."""
import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'netbox.settings'
sys.path.insert(0, '/app/netbox/netbox')

import django
django.setup()

from extras.models import CustomFieldChoiceSet
from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.custom_objects_schema import build_schema_document, build_choice_set_specs
from netbox_custom_objects.schema.executor import apply_document
from netbox_custom_objects.models import CustomObjectType

# 1. Choice Sets sicherstellen
choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
for spec in choice_specs:
    extra_choices = [(c, c) for c in spec["choices"]]
    obj, created = CustomFieldChoiceSet.objects.update_or_create(
        name=spec["name"],
        defaults={"extra_choices": extra_choices},
    )
    print(f'  ChoiceSet {spec["name"]}: {"created" if created else "updated"}')

# 2. Sync
doc = build_schema_document(BUILTIN_CUSTOM_TYPES)
apply_document(doc, allow_destructive=True)
print("Sync OK")

# 3. Resultat prüfen
for cot in CustomObjectType.objects.all().order_by("slug"):
    print(f"=== {cot.slug} ===")
    for f in cot.fields.all().order_by("schema_id"):
        print(f"  [{f.schema_id}] {f.name} ({f.type})")
