import taggit.managers
import utilities.json
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0059_objectcomment_objectinstalledon"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectFilter",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("name", models.CharField(max_length=200, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                (
                    "family",
                    models.CharField(
                        choices=[("inet", "IPv4 (inet)"), ("inet6", "IPv6 (inet6)"), ("any", "Any"), ("mpls", "MPLS"), ("ccc", "CCC")],
                        default="inet",
                        max_length=20,
                        verbose_name="Address Family",
                    ),
                ),
                (
                    "rules",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="Rules",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True, null=True,
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
                "verbose_name": "Filter Object",
                "verbose_name_plural": "Filter Objects",
                "ordering": ("family", "name"),
            },
        ),
        migrations.CreateModel(
            name="ObjectPolicer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                (
                    "bandwidth_limit",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="Bandwidth Limit (bits/s)",
                    ),
                ),
                (
                    "bandwidth_percent",
                    models.PositiveIntegerField(
                        blank=True, null=True,
                        verbose_name="Bandwidth Percent",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        blank=True, null=True,
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
                "verbose_name": "Policer Object",
                "verbose_name_plural": "Policer Objects",
                "ordering": ("name",),
            },
        ),
    ]
