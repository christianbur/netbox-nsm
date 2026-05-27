from django.db import migrations


def normalize_system_areas(apps, schema_editor):
    SecurityArea = apps.get_model("netbox_nsm", "SecurityArea")
    SecurityObjectType = apps.get_model("netbox_nsm", "SecurityObjectType")
    SecurityObjectGroup = apps.get_model("netbox_nsm", "SecurityObjectGroup")
    SecurityPolicyRuleObjectItem = apps.get_model("netbox_nsm", "SecurityPolicyRuleObjectItem")
    SecurityPolicyRuleGroupItem = apps.get_model("netbox_nsm", "SecurityPolicyRuleGroupItem")

    srcdst, _ = SecurityArea.objects.update_or_create(
        slug="srcdst",
        defaults={
            "name": "Source/Destination",
            "sort_order": 1,
            "placement_mode": "directional",
            "is_system": True,
        },
    )

    SecurityArea.objects.update_or_create(
        slug="services",
        defaults={"name": "Services", "sort_order": 3, "placement_mode": "fixed", "is_system": True},
    )
    SecurityArea.objects.update_or_create(
        slug="application",
        defaults={"name": "Applikation", "sort_order": 4, "placement_mode": "fixed", "is_system": True},
    )
    SecurityArea.objects.update_or_create(
        slug="action",
        defaults={"name": "Action", "sort_order": 5, "placement_mode": "fixed", "is_system": True},
    )
    SecurityArea.objects.update_or_create(
        slug="info",
        defaults={"name": "Info", "sort_order": 90, "placement_mode": "fixed", "is_system": True},
    )

    legacy_areas = list(SecurityArea.objects.filter(slug__in=("source", "destination")))
    legacy_ids = [area.pk for area in legacy_areas]
    if legacy_ids:
        SecurityObjectType.objects.filter(area_id__in=legacy_ids).update(area=srcdst)
        SecurityObjectGroup.objects.filter(area_id__in=legacy_ids).update(area=srcdst)
        SecurityPolicyRuleObjectItem.objects.filter(area_id__in=legacy_ids).update(area=srcdst)
        SecurityPolicyRuleGroupItem.objects.filter(area_id__in=legacy_ids).update(area=srcdst)
        SecurityArea.objects.filter(pk__in=legacy_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0004_area_placement_mode_and_rule_items"),
    ]

    operations = [
        migrations.RunPython(normalize_system_areas, migrations.RunPython.noop),
    ]