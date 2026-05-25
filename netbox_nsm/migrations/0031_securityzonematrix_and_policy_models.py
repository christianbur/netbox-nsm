# Generated manually for netbox_nsm matrix extension

import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0030_securityzonerole_owner"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonerole",
            name="use_matrix",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="SecurityZoneMatrixPolicy",
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
                    "action",
                    models.CharField(
                        choices=[("permit", "Permit"), ("deny", "Deny")],
                        default="permit",
                        max_length=20,
                    ),
                ),
                ("color", models.CharField(default="green", max_length=20)),
                (
                    "description",
                    models.CharField(blank=True, max_length=200),
                ),
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
                "verbose_name": "Security Zone Matrix Policy",
                "verbose_name_plural": "Security Zone Matrix Policies",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="SecurityZoneMatrix",
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
                    "description",
                    models.CharField(blank=True, max_length=200),
                ),
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
                    "roles",
                    models.ManyToManyField(
                        blank=True,
                        related_name="matrices",
                        to="netbox_nsm.securityzonerole",
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
                "verbose_name": "Security Zone Matrix",
                "verbose_name_plural": "Security Zone Matrices",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="SecurityZoneMatrixCell",
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
                    "matrix",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cells",
                        to="netbox_nsm.securityzonematrix",
                    ),
                ),
                (
                    "source_zone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matrix_source_cells",
                        to="netbox_nsm.securityzone",
                    ),
                ),
                (
                    "destination_zone",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="matrix_destination_cells",
                        to="netbox_nsm.securityzone",
                    ),
                ),
                (
                    "policy",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cells",
                        to="netbox_nsm.securityzonematrixpolicy",
                    ),
                ),
            ],
            options={
                "verbose_name": "Security Zone Matrix Cell",
                "verbose_name_plural": "Security Zone Matrix Cells",
                "ordering": ("matrix", "source_zone", "destination_zone"),
            },
        ),
        migrations.AddConstraint(
            model_name="securityzonematrixcell",
            constraint=models.UniqueConstraint(
                fields=("matrix", "source_zone", "destination_zone"),
                name="%(app_label)s_%(class)s_unique_matrix_cell",
            ),
        ),
    ]
