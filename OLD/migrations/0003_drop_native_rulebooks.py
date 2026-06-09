from django.db import migrations, models
import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json


def _reassign_rulebook_permissions(apps, schema_editor):
    """Keep legacy codenames on the new CotRulebookAssignment content type."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    CotRulebookAssignment = apps.get_model("netbox_nsm", "CotRulebookAssignment")

    new_ct = ContentType.objects.get_for_model(CotRulebookAssignment)
    old_cts = ContentType.objects.filter(
        app_label="netbox_nsm",
        model__in=(
            "rulebook",
            "rulebookassignment",
            "rule",
            "rulebookfield",
            "rulebookfieldtype",
            "ruleobjectitem",
            "rulegroupitem",
        ),
    )
    codenames = {
        "view_rulebook",
        "view_rulebookassignment",
        "add_rulebookassignment",
        "change_rulebookassignment",
        "delete_rulebookassignment",
    }
    for old_ct in old_cts:
        for perm in Permission.objects.filter(content_type=old_ct, codename__in=codenames):
            Permission.objects.get_or_create(
                codename=perm.codename,
                content_type=new_ct,
                defaults={"name": perm.name},
            )


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("netbox_nsm", "0002_nsmuisettings_setup_menu_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="CotRulebookAssignment",
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
                ("description", models.CharField(blank=True, max_length=200)),
                ("comments", models.TextField(blank=True)),
                ("assigned_object_id", models.PositiveBigIntegerField()),
                ("cot_slug", models.SlugField(max_length=100)),
                (
                    "assigned_object_type",
                    models.ForeignKey(
                        limit_choices_to=models.Q(
                            models.Q(("app_label", "dcim"), ("model", "device")),
                            models.Q(
                                ("app_label", "dcim"), ("model", "virtualdevicecontext")
                            ),
                            models.Q(
                                ("app_label", "virtualization"), ("model", "virtualmachine")
                            ),
                            _connector="OR",
                        ),
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
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
                "verbose_name": "Rulebook Assignment",
                "verbose_name_plural": "Rulebook Assignments",
                "ordering": ("cot_slug", "assigned_object_id"),
                "permissions": [
                    ("view_rulebook", "Can view rulebooks"),
                    ("view_rulebookassignment", "Can view rulebook assignments"),
                    ("add_rulebookassignment", "Can add rulebook assignments"),
                    ("change_rulebookassignment", "Can change rulebook assignments"),
                    ("delete_rulebookassignment", "Can delete rulebook assignments"),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="cotrulebookassignment",
            index=models.Index(
                fields=["assigned_object_type", "assigned_object_id"],
                name="netbox_nsm_cotrulebookassignment_obj_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="cotrulebookassignment",
            constraint=models.UniqueConstraint(
                fields=("assigned_object_type", "assigned_object_id", "cot_slug"),
                name="netbox_nsm_cotrulebookassignment_unique_cot_assignment",
            ),
        ),
        migrations.RunPython(
            _reassign_rulebook_permissions,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(name="RuleGroupItem"),
        migrations.DeleteModel(name="RuleObjectItem"),
        migrations.DeleteModel(name="RulebookFieldType"),
        migrations.DeleteModel(name="RulebookField"),
        migrations.DeleteModel(name="Rule"),
        migrations.DeleteModel(name="RulebookAssignment"),
        migrations.DeleteModel(name="Rulebook"),
    ]
