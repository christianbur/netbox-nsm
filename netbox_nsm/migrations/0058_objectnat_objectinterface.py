import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0057_policyrule_custom_objects"),
        ("dcim", "0001_initial"),
        ("ipam", "0001_initial"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="ObjectNAT",
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
                    "nat_type",
                    models.CharField(
                        choices=[("snat", "Source NAT (SNAT)"), ("dnat", "Destination NAT (DNAT)"), ("masquerade", "Masquerade")],
                        default="snat",
                        max_length=20,
                        verbose_name="NAT Type",
                    ),
                ),
                (
                    "source_address",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectnat_source_address",
                        to="ipam.ipaddress",
                        verbose_name="Source Address",
                    ),
                ),
                (
                    "source_prefix",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectnat_source_prefix",
                        to="ipam.prefix",
                        verbose_name="Source Prefix",
                    ),
                ),
                (
                    "destination_address",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectnat_destination_address",
                        to="ipam.ipaddress",
                        verbose_name="Destination Address",
                    ),
                ),
                (
                    "destination_prefix",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectnat_destination_prefix",
                        to="ipam.prefix",
                        verbose_name="Destination Prefix",
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
                "verbose_name": "NAT Object",
                "verbose_name_plural": "NAT Objects",
                "ordering": ("nat_type", "name"),
            },
        ),
        migrations.CreateModel(
            name="ObjectInterface",
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
                    "direction",
                    models.CharField(
                        choices=[("source", "Source"), ("destination", "Destination")],
                        default="source",
                        max_length=20,
                        verbose_name="Direction",
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectinterface_device",
                        to="dcim.device",
                        verbose_name="Device",
                    ),
                ),
                (
                    "interface",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="objectinterface_interface",
                        to="dcim.interface",
                        verbose_name="Interface",
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
                "verbose_name": "Interface Object",
                "verbose_name_plural": "Interface Objects",
                "ordering": ("direction", "name"),
            },
        ),
    ]
