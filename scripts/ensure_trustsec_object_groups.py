#!/usr/bin/env python3
"""Create TrustSec source-tier ObjectGroups for an existing Enterprise DC demo."""

import os
import sys

sys.path.insert(0, "/opt/netbox/netbox")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

import django

django.setup()

from django.contrib.contenttypes.models import ContentType

from netbox_custom_objects.models import CustomObjectType
from netbox_nsm.demos.trustsec_object_groups import ensure_trustsec_source_object_groups

zone_type = CustomObjectType.objects.filter(slug="nsm_zones").first()
if zone_type is None:
    print("ERROR: nsm_zones custom object type not found")
    sys.exit(1)

ZoneModel = zone_type.get_model()
zone_ct = ContentType.objects.get_for_model(ZoneModel)
zones_by_name = {z.name: z for z in ZoneModel.objects.all()}

mapping = ensure_trustsec_source_object_groups(
    zones_by_name=zones_by_name,
    zone_content_type=zone_ct,
)
print(f"TrustSec ObjectGroups ready ({len(mapping)} zone memberships).")
