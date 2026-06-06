"""Rename rulebook_type value policy → security_rules."""

from django.db import migrations


def forwards(apps, schema_editor):
    Rulebook = apps.get_model("netbox_nsm", "Rulebook")
    Rulebook.objects.filter(rulebook_type="policy").update(
        rulebook_type="security_rules"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
