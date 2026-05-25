import django.db.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("netbox_nsm", "0031_securityzonematrix_and_policy_models"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="SecurityZonePolicyRulebook",
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
                    "rulebook_type",
                    models.CharField(
                        choices=[
                            ("matrix", "Security Zone Matrix"),
                            ("policy", "Security Zone Policy"),
                        ],
                        default="policy",
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
            ],
            options={
                "verbose_name": "Security Zone Rulebook",
                "verbose_name_plural": "Security Zone Rulebooks",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="SecurityZonePolicyRule",
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
                (
                    "policy_action",
                    models.CharField(
                        choices=[
                            ("permit", "Permit"),
                            ("deny", "Deny"),
                            ("count", "Count"),
                            ("log", "Log"),
                            ("reject", "Reject"),
                        ],
                        default="permit",
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
                    "rulebook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rules",
                        to="netbox_nsm.securityzonepolicyrulebook",
                    ),
                ),
                (
                    "applications",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_applications",
                        to="netbox_nsm.application",
                    ),
                ),
                (
                    "application_sets",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_application_sets",
                        to="netbox_nsm.applicationset",
                    ),
                ),
                (
                    "destination_addresses",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_destination_addresses",
                        to="netbox_nsm.addresslist",
                    ),
                ),
                (
                    "destination_users",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_destination_users",
                        to="users.user",
                    ),
                ),
                (
                    "destination_zones",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_destination_zones",
                        to="netbox_nsm.securityzone",
                    ),
                ),
                (
                    "source_addresses",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_source_addresses",
                        to="netbox_nsm.addresslist",
                    ),
                ),
                (
                    "source_users",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_source_users",
                        to="users.user",
                    ),
                ),
                (
                    "source_zones",
                    models.ManyToManyField(
                        blank=True,
                        related_name="securityzonepolicyrule_source_zones",
                        to="netbox_nsm.securityzone",
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
                "verbose_name": "Security Zone Policy Rule",
                "verbose_name_plural": "Security Zone Policy Rules",
                "ordering": ("rulebook", "name"),
            },
        ),
        migrations.CreateModel(
            name="SecurityZonePolicyRulebookAssignment",
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
                ("assigned_object_id", models.PositiveBigIntegerField()),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device"))
                            | models.Q(
                                ("app_label", "dcim"), ("model", "virtualdevicecontext")
                            )
                            | models.Q(
                                ("app_label", "virtualization"),
                                ("model", "virtualmachine"),
                            )
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "rulebook",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="netbox_nsm.securityzonepolicyrulebook",
                    ),
                ),
            ],
            options={
                "verbose_name": "Security Zone Rulebook assignment",
                "verbose_name_plural": "Security Zone Rulebook assignments",
                "ordering": ("rulebook", "assigned_object_id"),
            },
        ),
        migrations.AddConstraint(
            model_name="securityzonepolicyrule",
            constraint=models.UniqueConstraint(
                fields=("rulebook", "name"),
                name="netbox_nsm_securityzonepolicyrule_unique_rulebook_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="securityzonepolicyrulebookassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "rulebook"),
                name="netbox_nsm_securityzonepolicyrulebookassignment_unique_rulebook_assignment",
            ),
        ),
        migrations.AddIndex(
            model_name="securityzonepolicyrulebookassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_securityzonepolicyrulebookassignment_assigned_idx",
            ),
        ),
    ]
