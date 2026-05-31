#!/usr/bin/env python3
"""Zeigt den Diff ohne ihn anzuwenden."""
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'netbox.settings'
sys.path.insert(0, '/app/netbox/netbox')
import django; django.setup()

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.custom_objects_schema import build_schema_document, build_choice_set_specs
from netbox_custom_objects.schema.comparator import diff_document
from netbox_custom_objects.models import CustomObjectType

doc = build_schema_document(BUILTIN_CUSTOM_TYPES)

print("=== Schema document fields ===")
for t in doc['types']:
    print(f"{t['slug']}: {[(f['id'], f['name']) for f in t['fields']]}")
    print(f"  removed_fields: {t['removed_fields']}")

print()
print("=== DB fields ===")
for cot in CustomObjectType.objects.all().order_by('slug'):
    fields = list(cot.fields.all().order_by('schema_id'))
    print(f"{cot.slug}: {[(f.schema_id, f.name) for f in fields]}")

print()
print("=== Diff ===")
diffs = diff_document(doc)
for d in diffs:
    print(f"\n{d.slug}:")
    if d.warnings:
        print(f"  WARNINGS: {d.warnings}")
    for fc in d.field_changes:
        print(f"  {fc.op.name} schema_id={fc.schema_id} name={fc.db_name or fc.schema_def.get('name')}")
