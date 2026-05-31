#!/usr/bin/env python3
"""Setzt schema_ids auf den korrekten Wert gemäß builtin_types.py.
Auto-injected: name=1, description=3, comments=6, color=7
IDs 2/4/5 (slug/owner_group/owner) werden NIE injiziert.
User-fields starten bei 100.
"""
import os, sys
os.environ['DJANGO_SETTINGS_MODULE'] = 'netbox.settings'
sys.path.insert(0, '/app/netbox/netbox')
import django; django.setup()

from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField
from django.db import connection

# Vollständiges ID-Mapping: auto + user-defined pro COT
SCHEMA_IDS = {
    'nsm_action':    {'name': 1, 'description': 3, 'comments': 6, 'color': 7},
    'nsm_addresses': {'name': 1, 'description': 3, 'comments': 6, 'color': 7,
                      'ip_address': 100, 'prefix': 101, 'range': 102, 'group': 103},
    'nsm_labels':    {'name': 1, 'description': 3, 'comments': 6, 'color': 7,
                      'label_type': 100},
    'nsm_services':  {'name': 1, 'description': 3, 'comments': 6, 'color': 7,
                      'protocol': 100, 'port': 101, 'group': 102},
    'nsm_zones':     {'name': 1, 'description': 3, 'comments': 6, 'color': 7},
}

for cot in CustomObjectType.objects.all().order_by('slug'):
    id_map = SCHEMA_IDS.get(cot.slug, {})
    table = cot.get_database_table_name()
    print(f'\n=== {cot.slug} ===')

    for f in cot.fields.all():
        if f.name not in id_map:
            print(f'  UNBEKANNT: {f.name} (pk={f.pk}) — wird nicht angefasst')
            continue
        expected = id_map[f.name]
        if f.schema_id != expected:
            f.schema_id = expected
            f.save(update_fields=['schema_id'])
            print(f'  Korrigiert: {f.name} → schema_id={expected}')
        else:
            print(f'  OK: {f.name} schema_id={f.schema_id}')

print('\nFertig.')
