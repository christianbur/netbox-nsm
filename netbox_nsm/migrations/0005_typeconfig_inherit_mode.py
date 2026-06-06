from django.db import migrations, models


def set_inherit_modes(apps, schema_editor):
    TypeConfig = apps.get_model("netbox_nsm", "TypeConfig")
    group_member_classes = {
        "label",
        "label-scope",
        "service",
        "action",
        "info",
        "group",
    }
    for tc in TypeConfig.objects.all():
        if tc.matching_class in group_member_classes:
            tc.inherit_mode = "group_member"
        else:
            tc.inherit_mode = "ipam_prefix"
        tc.save(update_fields=["inherit_mode"])


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0004_nsm_ui_settings_panel_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="inherit_mode",
            field=models.CharField(
                choices=[
                    ("ipam_prefix", "Containing prefix (IPAM parent → child)"),
                    ("group_member", "Parent group (member-of)"),
                ],
                default="ipam_prefix",
                help_text="ipam_prefix: containing Prefix → child (IP, Range, sub-Prefix). group_member: parent group / member-of container → member.",
                max_length=20,
                verbose_name="Inheritance mode",
            ),
        ),
        migrations.RunPython(set_inherit_modes, migrations.RunPython.noop),
    ]
