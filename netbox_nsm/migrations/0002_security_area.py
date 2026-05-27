"""
Migration 0002: Introduce SecurityArea model, migrate area CharField → FK,
remove icon field from SecurityObjectType.
"""

import django.db.models.deletion
import taggit.managers
import utilities.json

from django.db import migrations, models


def create_system_areas(apps, schema_editor):
    """Create the four built-in system areas."""
    SecurityArea = apps.get_model("netbox_nsm", "SecurityArea")
    for slug, name in [
        ("srcdst",   "Source/Destination"),
        ("services", "Services"),
        ("action",   "Action"),
        ("info",     "Info"),
    ]:
        SecurityArea.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "is_system": True, "description": "", "custom_field_data": {}},
        )


def migrate_area_to_fk(apps, schema_editor):
    """Copy old area string values to new area_new FK field."""
    SecurityObjectType = apps.get_model("netbox_nsm", "SecurityObjectType")
    SecurityObjectGroup = apps.get_model("netbox_nsm", "SecurityObjectGroup")
    SecurityArea = apps.get_model("netbox_nsm", "SecurityArea")

    area_map = {a.slug: a for a in SecurityArea.objects.all()}

    for obj in SecurityObjectType.objects.order_by("id"):
        area = area_map.get(obj.area_old, area_map.get("srcdst"))
        if area:
            obj.area_new = area
            obj.save(update_fields=["area_new"])

    for obj in SecurityObjectGroup.objects.order_by("id"):
        area = area_map.get(obj.area_old, area_map.get("srcdst"))
        if area:
            obj.area_new = area
            obj.save(update_fields=["area_new"])


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
        ("extras", "0138_customfieldchoiceset_choice_colors"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        # 1. Create SecurityArea table
        migrations.CreateModel(
            name="SecurityArea",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                ("custom_field_data", models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True, default="")),
                ("slug", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("is_system", models.BooleanField(default=False)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="users.owner")),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "verbose_name": "Area",
                "verbose_name_plural": "Areas",
                "ordering": ("slug",),
            },
        ),

        # 2. Insert the 4 system areas
        migrations.RunPython(create_system_areas, migrations.RunPython.noop),

        # 3a. Rename old area fields to area_old
        migrations.RenameField("SecurityObjectType",  "area", "area_old"),
        migrations.RenameField("SecurityObjectGroup", "area", "area_old"),

        # 3b. Add new nullable area FK columns
        migrations.AddField(
            model_name="securityobjecttype",
            name="area_new",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="object_types",
                to="netbox_nsm.securityarea",
                verbose_name="Area",
            ),
        ),
        migrations.AddField(
            model_name="securityobjectgroup",
            name="area_new",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="object_groups",
                to="netbox_nsm.securityarea",
                verbose_name="Area",
            ),
        ),

        # 4. Data migration: fill area_new from area_old slug
        migrations.RunPython(migrate_area_to_fk, migrations.RunPython.noop),

        # 5. Remove old area_old fields
        migrations.RemoveField("SecurityObjectType",  "area_old"),
        migrations.RemoveField("SecurityObjectGroup", "area_old"),

        # 6. Rename area_new → area
        migrations.RenameField("SecurityObjectType",  "area_new", "area"),
        migrations.RenameField("SecurityObjectGroup", "area_new", "area"),

        # 7. Make area non-nullable
        migrations.AlterField(
            model_name="securityobjecttype",
            name="area",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="object_types",
                to="netbox_nsm.securityarea",
                verbose_name="Area",
            ),
        ),
        migrations.AlterField(
            model_name="securityobjectgroup",
            name="area",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="object_groups",
                to="netbox_nsm.securityarea",
                verbose_name="Area",
            ),
        ),

        # 8. Remove icon field from SecurityObjectType
        migrations.RemoveField("SecurityObjectType", "icon"),
    ]
