"""Mark permission-anchor models private and drop legacy stub tables."""

from django.db import migrations


def mark_permission_anchors_private(apps, schema_editor):
    ObjectType = apps.get_model("core", "ObjectType")
    ObjectType.objects.filter(
        app_label="netbox_nsm",
        model__in=("typeconfig", "rulebooklistproxy"),
    ).update(public=False)


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
        ("core", "0008_contenttype_proxy"),
    ]

    operations = [
        migrations.RunPython(
            mark_permission_anchors_private,
            migrations.RunPython.noop,
        ),
        migrations.RunSQL(
            sql=(
                "DROP TABLE IF EXISTS netbox_nsm_typeconfig CASCADE;"
                "DROP TABLE IF EXISTS netbox_nsm_rulebooklistproxy CASCADE;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
