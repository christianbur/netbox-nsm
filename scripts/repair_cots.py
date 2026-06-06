#!/usr/bin/env python3
"""Vollständiger DB-Reparatur-Script für alle COTs."""
import django_bootstrap

django_bootstrap.setup()

from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField
from django.db import connection


def get_existing_columns(table):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s",
            [table],
        )
        return {row[0] for row in cur.fetchall()}


def drop_column_if_exists(table, col):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s AND column_name=%s",
            [table, col],
        )
        if cur.fetchone():
            cur.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{col}"')
            print(f"  Dropped orphan column {table}.{col}")


# Schema-ID Mappings
AUTO_IDS = {
    "name": 1,
    "slug": 2,
    "description": 3,
    "owner_group": 4,
    "owner": 5,
    "comments": 6,
    "color": 7,
}
USER_IDS = {
    "nsm_action": {},
    "nsm_services": {"protocol": 100, "port": 101, "group": 102},
    "nsm_addresses": {"ip_address": 100, "prefix": 101, "range": 102, "group": 103},
    "nsm_labels": {"label_type": 100, "custom_type": 101, "display_template": 102},
    "nsm_zones": {"display_template": 100},
}

# suppress_fields: diese Felder sollen NICHT existieren
SUPPRESS = {
    "nsm_action": {"slug", "owner_group", "owner"},
    "nsm_services": {"slug", "owner_group", "owner"},
    "nsm_addresses": {"slug", "owner_group", "owner"},
    "nsm_labels": set(),
    "nsm_zones": set(),
}

for cot in CustomObjectType.objects.all().order_by("slug"):
    slug = cot.slug
    table = cot.get_database_table_name()
    full_id_map = {**AUTO_IDS, **USER_IDS.get(slug, {})}
    suppress = SUPPRESS.get(slug, set())

    print(f"\n=== {slug} (table={table}) ===")
    existing_cols = get_existing_columns(table)

    # 1. ORM-Felder löschen + Spalten droppen, die suppressed sind
    for fname in suppress:
        qs = CustomObjectTypeField.objects.filter(custom_object_type=cot, name=fname)
        if qs.exists():
            qs.delete()
            print(f"  Deleted ORM field: {fname}")
        if fname in existing_cols:
            drop_column_if_exists(table, fname)

    # 2. schema_ids für vorhandene ORM-Felder setzen
    for f in cot.fields.all():
        if f.name in suppress:
            continue
        if f.schema_id is None and f.name in full_id_map:
            f.schema_id = full_id_map[f.name]
            f.save(update_fields=["schema_id"])
            print(f"  Fixed schema_id: {f.name} → {f.schema_id}")
        elif f.schema_id is not None:
            pass  # bereits korrekt
        else:
            print(f"  UNKNOWN field (no id map): {f.name}")

    # 3. Orphan-Spalten droppen: Spalten in DB die kein ORM-Objekt haben
    #    (können entstehen wenn ORM-Objekt gelöscht aber DROP COLUMN nicht lief)
    orm_names = {f.name for f in cot.fields.all()}
    # Bekannte "Basis"-Spalten die vom Modell selbst kommen
    base_cols = {
        "id",
        "created",
        "last_updated",
        "custom_field_data",
        "tags",
        "bookmarks",
        "journal_entries",
        "subscriptions",
    }
    for col in existing_cols - base_cols - orm_names:
        if col in suppress:
            drop_column_if_exists(table, col)
        # Andere unbekannte Spalten NICHT anfassen

print("\nDone")
