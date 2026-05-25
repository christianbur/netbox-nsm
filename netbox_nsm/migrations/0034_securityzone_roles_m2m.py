from django.db import migrations, models


def copy_role_to_roles(apps, schema_editor):
    SecurityZone = apps.get_model("netbox_nsm", "SecurityZone")
    ThroughModel = SecurityZone.roles.through

    rows = []
    for zone in SecurityZone.objects.exclude(role_id__isnull=True).only("id", "role_id"):
        rows.append(
            ThroughModel(
                securityzone_id=zone.id,
                securityzonerole_id=zone.role_id,
            )
        )

    if rows:
        ThroughModel.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0033_securitypolicy_add_roles"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzone",
            name="roles",
            field=models.ManyToManyField(
                blank=True,
                related_name="zones",
                to="netbox_nsm.securityzonerole",
            ),
        ),
        migrations.RunPython(copy_role_to_roles, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="securityzone",
            name="role",
        ),
    ]
