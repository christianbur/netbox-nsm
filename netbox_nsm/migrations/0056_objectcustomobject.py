import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0055_objectcustomtype_area_fields"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectCustomObject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                ("field_data", models.JSONField(blank=True, default=dict)),
                ("table_data", models.JSONField(blank=True, default=list)),
                (
                    "custom_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="custom_objects",
                        to="netbox_nsm.objectcustomtype",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="users.owner",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag"),
                ),
            ],
            options={
                "verbose_name": "Custom Object",
                "verbose_name_plural": "Custom Objects",
                "ordering": ("custom_type", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="objectcustomobject",
            constraint=models.UniqueConstraint(
                fields=("custom_type", "name"),
                name="netbox_nsm_objectcustomobject_unique_type_name",
            ),
        ),
    ]
