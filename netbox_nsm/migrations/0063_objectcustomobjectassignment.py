import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("extras", "0001_initial"),
        ("netbox_nsm", "0062_policyrule_info_objects"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectCustomObjectAssignment",
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
                    "assigned_object_id",
                    models.PositiveBigIntegerField(blank=True, null=True),
                ),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"),
                                ("model", "virtualdevicecontext"),
                            ),
                            models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            ),
                            models.Q(
                                ("app_label", "netbox_nsm"),
                                ("model", "securityzone"),
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "custom_object",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.objectcustomobject",
                        verbose_name="Custom Object",
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
                "verbose_name": "Custom Object Assignment",
                "verbose_name_plural": "Custom Object Assignments",
                "ordering": ("custom_object",),
            },
        ),
        migrations.AddIndex(
            model_name="objectcustomobjectassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_objcustobj_assign_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectcustomobjectassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "custom_object"),
                name="netbox_nsm_objectcustomobjectassignment_unique",
            ),
        ),
    ]
