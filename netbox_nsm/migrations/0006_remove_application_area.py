from django.db import migrations


def remove_application_area(apps, schema_editor):
    SecurityArea = apps.get_model("netbox_nsm", "SecurityArea")
    SecurityObjectType = apps.get_model("netbox_nsm", "SecurityObjectType")
    SecurityObjectGroup = apps.get_model("netbox_nsm", "SecurityObjectGroup")
    SecurityPolicyRuleObjectItem = apps.get_model("netbox_nsm", "SecurityPolicyRuleObjectItem")
    SecurityPolicyRuleGroupItem = apps.get_model("netbox_nsm", "SecurityPolicyRuleGroupItem")

    services, _ = SecurityArea.objects.update_or_create(
        slug="services",
        defaults={
            "name": "Services",
            "sort_order": 3,
            "placement_mode": "fixed",
            "is_system": True,
        },
    )

    application = SecurityArea.objects.filter(slug="application").first()
    if not application:
        return

    SecurityObjectType.objects.filter(area=application).update(area=services)
    SecurityObjectGroup.objects.filter(area=application).update(area=services)
    SecurityPolicyRuleObjectItem.objects.filter(area=application).update(area=services)
    SecurityPolicyRuleGroupItem.objects.filter(area=application).update(area=services)

    application.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0005_normalize_system_areas"),
    ]

    operations = [
        migrations.RunPython(remove_application_area, migrations.RunPython.noop),
    ]
