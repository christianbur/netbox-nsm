#!/usr/bin/env python3
"""Zeigt den Diff zwischen portable schema JSON und der DB (ohne Apply)."""
import django_bootstrap

django_bootstrap.setup()

from netbox_custom_objects.models import CustomObjectType
from netbox_custom_objects.schema.comparator import diff_document
from netbox_nsm.custom_objects_schema import load_portable_schema_document

doc = load_portable_schema_document()

print("=== Schema document fields ===")
for t in doc["types"]:
    print(f"{t['slug']}: {[(f['id'], f['name']) for f in t['fields']]}")
    print(f"  removed_fields: {t['removed_fields']}")

print()
print("=== DB fields ===")
for cot in CustomObjectType.objects.filter(slug__startswith="nsm_").order_by("slug"):
    fields = list(cot.fields.all().order_by("schema_id", "name"))
    print(f"{cot.slug}: {[(f.schema_id, f.name) for f in fields]}")

print()
print("=== Diff ===")
diffs = diff_document(doc)
for d in diffs:
    print(f"\n{d.slug}:")
    if d.warnings:
        print(f"  WARNINGS: {d.warnings}")
    for fc in d.field_changes:
        name = fc.db_name or fc.schema_def.get("name")
        print(f"  {fc.op.name} schema_id={fc.schema_id} name={name}")
