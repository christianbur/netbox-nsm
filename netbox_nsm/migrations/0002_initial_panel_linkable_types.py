"""
Add panel_linkable_content_types M2M to TypeConfig.

Data migration behaviour (documented):
- panel_linkable=True  → empty M2M (linkable from all NetBox object types)
- panel_linkable=False → empty M2M, panel_linkable stays False (not assignable)
"""

from django.db import migrations, models


def migrate_panel_linkable_to_m2m(apps, schema_editor):
    TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
    for tc in TypeConfig.objects.all().only("id", "panel_linkable"):
        if tc.panel_linkable:
            # Empty M2M = unrestricted (all object types).
            continue
        # panel_linkable=False: leave M2M empty; master switch remains False.


def reverse_migrate_panel_linkable_to_m2m(apps, schema_editor):
    TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
    for tc in TypeConfig.objects.all().prefetch_related("panel_linkable_content_types"):
        if not tc.panel_linkable:
            continue
        if tc.panel_linkable_content_types.exists():
            tc.panel_linkable = True
            tc.save(update_fields=["panel_linkable"])


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="panel_linkable_content_types",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "NetBox object types that may link this NSM type from the Security Panel "
                    "(e.g. Interface, Prefix). Leave empty to allow all object types."
                ),
                related_name="nsm_panel_linkable_type_configs",
                to="contenttypes.contenttype",
                verbose_name="Linkable in panel",
            ),
        ),
        migrations.AlterField(
            model_name="typeconfig",
            name="panel_linkable",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Master switch: if disabled, this NSM type cannot be assigned from the "
                    "Security Panel regardless of the object-type list below."
                ),
                verbose_name="Linkable in panel",
            ),
        ),
        migrations.RunPython(
            migrate_panel_linkable_to_m2m,
            reverse_migrate_panel_linkable_to_m2m,
        ),
    ]
