from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.text
import django.core.validators
import django.utils.translation
import taggit.managers
import utilities.json
from extras.choices import CustomFieldTypeChoices


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0042_objectuser_name_dn"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.CreateModel(
            name="NsmObjectType",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
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
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                ("name", models.CharField(max_length=100, unique=True, validators=[django.core.validators.RegexValidator(message='Only lowercase alphanumeric characters and underscores are allowed. Names may not start or end with an underscore, and double underscores are not permitted.', regex='^[a-z0-9]+(_[a-z0-9]+)*$')])),
                ("verbose_name", models.CharField(blank=True, max_length=100)),
                ("verbose_name_plural", models.CharField(blank=True, max_length=100)),
                ("slug", models.SlugField(db_index=True, max_length=100, unique=True)),
                ("group_name", models.CharField(blank=True, db_index=True, max_length=100)),
                ("schema_document", models.JSONField(blank=True, null=True)),
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
                "verbose_name": "NSM Object Type",
                "verbose_name_plural": "NSM Object Types",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="NsmObjectTypeField",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
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
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                ("name", models.CharField(max_length=50, validators=[django.core.validators.RegexValidator(message='Only lowercase alphanumeric characters and underscores are allowed. Names may not start or end with an underscore, and double underscores are not permitted.', regex='^[a-z0-9]+(_[a-z0-9]+)*$')])),
                ("label", models.CharField(blank=True, max_length=50)),
                ("type", models.CharField(choices=CustomFieldTypeChoices, default="text", max_length=50, verbose_name="type")),
                ("group_name", models.CharField(blank=True, max_length=50)),
                ("required", models.BooleanField(default=False)),
                ("unique", models.BooleanField(default=False)),
                ("default", models.JSONField(blank=True, null=True)),
                ("weight", models.PositiveSmallIntegerField(default=100)),
                ("nsm_object_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fields", to="netbox_nsm.nsmobjecttype")),
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
                "verbose_name": "NSM Object Type Field",
                "verbose_name_plural": "NSM Object Type Fields",
                "ordering": ("group_name", "weight", "name"),
            },
        ),
        migrations.AddConstraint(
            model_name="nsmobjecttype",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("name"), name="netbox_nsm_nsmobjecttype_name_ci_unique"),
        ),
        migrations.AddConstraint(
            model_name="nsmobjecttypefield",
            constraint=models.UniqueConstraint(fields=("nsm_object_type", "name"), name="netbox_nsm_nsmobjecttypefield_unique_name"),
        ),
    ]
