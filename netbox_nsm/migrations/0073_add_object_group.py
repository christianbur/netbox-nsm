import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("extras", "0001_initial"),
        ("netbox_nsm", "0072_remove_legacy_object_models"),
        ("users", "0001_squashed_0011"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False
                    ),
                ),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        encoder=utilities.json.CustomFieldJSONEncoder,
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
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                (
                    "name",
                    models.CharField(
                        max_length=100,
                        unique=True,
                        verbose_name="Name",
                    ),
                ),
                (
                    "area",
                    models.CharField(
                        choices=[
                            ("srcdst", "Source/Destination"),
                            ("services", "Services"),
                            ("action", "Action"),
                            ("info", "Info"),
                        ],
                        default="srcdst",
                        max_length=20,
                        verbose_name="Area",
                    ),
                ),
                (
                    "members",
                    models.ManyToManyField(
                        blank=True,
                        related_name="object_groups",
                        to="netbox_nsm.objectcustomobject",
                        verbose_name="Members",
                    ),
                ),
                (
                    "sub_groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="parent_groups",
                        symmetrical=False,
                        to="netbox_nsm.objectgroup",
                        verbose_name="Sub-Groups",
                    ),
                ),
                (
                    "tags",
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Object Group",
                "verbose_name_plural": "Object Groups",
                "ordering": ("area", "name"),
            },
        ),
    ]
