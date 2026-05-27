from django.db import migrations


def set_labels_display_template(apps, schema_editor):
    SecurityObjectType = apps.get_model("netbox_nsm", "SecurityObjectType")
    SecurityObjectType.objects.filter(name="Labels").update(
        display_template="{label_type_initial}:{name}"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0006_remove_application_area"),
    ]

    operations = [
        migrations.RunPython(set_labels_display_template, migrations.RunPython.noop),
    ]
