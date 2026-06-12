#!/usr/bin/env python3
"""Standalone: ChoiceSets + portable schema apply + default object seed."""
import django_bootstrap

django_bootstrap.setup()

from extras.models import CustomFieldChoiceSet
from netbox_custom_objects.models import CustomObjectType
from netbox_custom_objects.schema.executor import apply_document
from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.objects.custom_objects_schema import (
    build_choice_set_specs,
    build_schema_document,
)
from netbox_nsm.objects.type_config_export import sync_cot_nsm_config_comments_for_slugs

choice_specs = build_choice_set_specs()
for spec in choice_specs:
    extra_choices = [(c, c) for c in spec["choices"]]
    _obj, created = CustomFieldChoiceSet.objects.update_or_create(
        name=spec["name"],
        defaults={"extra_choices": extra_choices},
    )
    print(f'  ChoiceSet {spec["name"]}: {"created" if created else "updated"}')

doc = build_schema_document()
apply_document(doc, allow_destructive=True)
sync_cot_nsm_config_comments_for_slugs(t["slug"] for t in doc["types"])
print("Sync OK")

for cot in CustomObjectType.objects.filter(slug__startswith="nsm_").order_by("slug"):
    print(f"=== {cot.slug} ===")
    for f in cot.fields.all().order_by("schema_id", "name"):
        print(f"  [{f.schema_id}] {f.name} ({f.type})")
