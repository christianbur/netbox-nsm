import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0035_securityzonepolicy_zones_m2m"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectLabel",
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
                ("type_short", models.CharField(max_length=10)),
                ("type_long", models.CharField(max_length=100)),
                ("name", models.CharField(max_length=100)),
                ("color", models.CharField(default="gray", max_length=20)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
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
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "Label",
                "verbose_name_plural": "Labels",
                "ordering": ("type_short", "name"),
            },
        ),
        migrations.CreateModel(
            name="ObjectSGT",
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
                ("name", models.CharField(max_length=100)),
                ("tag", models.PositiveIntegerField(blank=True, null=True)),
                ("color", models.CharField(default="blue", max_length=20)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
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
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "SGT",
                "verbose_name_plural": "SGTs",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="ObjectUser",
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
                    "entry_type",
                    models.CharField(
                        choices=[("user", "User"), ("group", "Group")],
                        default="user",
                        max_length=20,
                    ),
                ),
                ("value", models.CharField(max_length=255)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
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
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "ordering": ("entry_type", "value"),
            },
        ),
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
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "group_type",
                    models.CharField(
                        choices=[
                            ("mixed", "Mixed"),
                            ("addresses", "Addresses"),
                            ("services", "Services"),
                            ("applications", "Applications"),
                            ("labels", "Labels"),
                            ("zones", "Zones"),
                            ("sgts", "SGTs"),
                            ("users", "Users"),
                        ],
                        default="mixed",
                        max_length=20,
                    ),
                ),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
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
                    taggit.managers.TaggableManager(
                        through="extras.TaggedItem", to="extras.Tag"
                    ),
                ),
                (
                    "addresses",
                    models.ManyToManyField(blank=True, to="netbox_nsm.address"),
                ),
                (
                    "applications",
                    models.ManyToManyField(blank=True, to="netbox_nsm.application"),
                ),
                (
                    "labels",
                    models.ManyToManyField(blank=True, to="netbox_nsm.objectlabel"),
                ),
                (
                    "services",
                    models.ManyToManyField(blank=True, to="netbox_nsm.applicationitem"),
                ),
                (
                    "sgts",
                    models.ManyToManyField(blank=True, to="netbox_nsm.objectsgt"),
                ),
                (
                    "users",
                    models.ManyToManyField(blank=True, to="netbox_nsm.objectuser"),
                ),
                (
                    "zones",
                    models.ManyToManyField(blank=True, to="netbox_nsm.securityzone"),
                ),
            ],
            options={
                "verbose_name": "Group",
                "verbose_name_plural": "Groups",
                "ordering": ("name",),
            },
        ),
        migrations.AddConstraint(
            model_name="objectlabel",
            constraint=models.UniqueConstraint(
                fields=("type_short", "name"),
                name="netbox_nsm_objectlabel_unique_type_short_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectsgt",
            constraint=models.UniqueConstraint(
                fields=("name", "tag"),
                name="netbox_nsm_objectsgt_unique_name_tag",
            ),
        ),
        migrations.AddConstraint(
            model_name="objectuser",
            constraint=models.UniqueConstraint(
                fields=("entry_type", "value"),
                name="netbox_nsm_objectuser_unique_entry_type_value",
            ),
        ),
    ]
