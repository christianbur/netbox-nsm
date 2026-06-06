#!/usr/bin/env python3
"""Assign schema_id on COT fields from builtin_types portable schema document.

Run inside netbox-dev::

    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/set_schema_ids.py

Or with explicit NetBox root::

    NETBOX_ROOT=/opt/netbox python3 /opt/netbox-nsm/scripts/set_schema_ids.py
"""
import django_bootstrap

django_bootstrap.setup()

from netbox_custom_objects.models import CustomObjectType
from netbox_nsm.custom_objects_schema import load_portable_schema_document

doc = load_portable_schema_document()
id_maps = {t["slug"]: {f["name"]: f["id"] for f in t["fields"]} for t in doc["types"]}

updated = 0
for cot in CustomObjectType.objects.filter(slug__startswith="nsm_").order_by("slug"):
    id_map = id_maps.get(cot.slug)
    print(f"\n=== {cot.slug} ===")
    if not id_map:
        print("  (kein Eintrag in portable schema — übersprungen)")
        continue

    max_id = 0
    for field in cot.fields.all():
        expected = id_map.get(field.name)
        if expected is None:
            print(f"  UNBEKANNT: {field.name} (pk={field.pk})")
            continue
        max_id = max(max_id, expected, field.schema_id or 0)
        if field.schema_id != expected:
            field.schema_id = expected
            field.save(update_fields=["schema_id"])
            print(f"  Korrigiert: {field.name} → schema_id={expected}")
            updated += 1
        else:
            print(f"  OK: {field.name} schema_id={field.schema_id}")

    next_id = getattr(cot, "next_schema_id", None)
    needed = max_id + 1
    if next_id is not None and next_id < needed:
        cot.next_schema_id = needed
        cot.save(update_fields=["next_schema_id"])
        print(f"  next_schema_id → {needed}")

print(f"\nFertig. {updated} Feld(er) aktualisiert.")
