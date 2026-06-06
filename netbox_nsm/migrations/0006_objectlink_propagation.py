from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0005_typeconfig_inherit_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectlink",
            name="propagation",
            field=models.CharField(
                choices=[
                    ("direct", "Direct (this object only)"),
                    ("inherit_ipam", "Inherit to IPAM children"),
                    ("inherit_group", "Inherit to group members"),
                ],
                default="direct",
                help_text="Direct: only object A. Inherit: also applies to IPAM children or group members, depending on object A.",
                max_length=20,
                verbose_name="Link type",
            ),
        ),
        migrations.AddField(
            model_name="objectlink",
            name="propagate_stop_on_own",
            field=models.BooleanField(
                default=False,
                help_text="When enabled, children with their own direct link of the same NSM type no longer inherit this assignment.",
                verbose_name="Stop when child has own link",
            ),
        ),
        migrations.AddIndex(
            model_name="objectlink",
            index=models.Index(fields=["propagation"], name="netbox_nsm__propaga_idx"),
        ),
    ]
