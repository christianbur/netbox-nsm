#!/usr/bin/env python3
"""Fix schema_ids und entfernt unerwünschte Felder aus nsm_action/nsm_services."""
import django_bootstrap

django_bootstrap.setup()

from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField
from django.db import connection

# 1. schema_ids fixen für nsm_services
cot_svc = CustomObjectType.objects.get(slug='nsm_services')
fix_map = {'name': 1, 'description': 3, 'comments': 6, 'color': 7,
           'protocol': 100, 'port': 101, 'group': 102}
for f in cot_svc.fields.all():
    if f.schema_id is None and f.name in fix_map:
        f.schema_id = fix_map[f.name]
        f.save(update_fields=['schema_id'])
        print(f'Fixed nsm_services.{f.name} -> {f.schema_id}')

# 2. slug/owner_group/owner aus nsm_services + nsm_action entfernen
table_svc = cot_svc.get_database_table_name()
cot_act = CustomObjectType.objects.get(slug='nsm_action')
table_act = cot_act.get_database_table_name()

for cot, table in [(cot_svc, table_svc), (cot_act, table_act)]:
    for fname in ('slug', 'owner_group', 'owner'):
        # ORM löschen
        qs = CustomObjectTypeField.objects.filter(custom_object_type=cot, name=fname)
        qs.delete()
        # Spalte in DB droppen falls vorhanden
        with connection.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name=%s AND column_name=%s",
                [table, fname]
            )
            if cur.fetchone():
                cur.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS "{fname}"')
                print(f'Dropped {cot.slug}.{fname}')

print('Done')
