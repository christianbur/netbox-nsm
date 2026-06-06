"""Replace TypeConfig.panel_linkable boolean with panel_linkable_types JSONField."""

from django.db import migrations, models

PANEL_LINKABLE_DISABLED = 0


def migrate_panel_linkable_forward(apps, schema_editor):
    TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
    for tc in TypeConfig.objects.all().only("pk", "panel_linkable"):
        if tc.panel_linkable:
            tc.panel_linkable_types = []
        else:
            tc.panel_linkable_types = [PANEL_LINKABLE_DISABLED]
        tc.save(update_fields=["panel_linkable_types"])


def migrate_panel_linkable_backward(apps, schema_editor):
    TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
    for tc in TypeConfig.objects.all().only("pk", "panel_linkable_types"):
        types = tc.panel_linkable_types or []
        tc.panel_linkable = types != [PANEL_LINKABLE_DISABLED]
        tc.save(update_fields=["panel_linkable"])


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0003_rule_virtual_group_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="panel_linkable_types",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(
            migrate_panel_linkable_forward,
            migrate_panel_linkable_backward,
        ),
        migrations.RemoveField(
            model_name="typeconfig",
            name="panel_linkable",
        ),
    ]
