from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="inherit_links",
            field=models.BooleanField(
                default=False,
                verbose_name="Inherit from parent",
                help_text=(
                    "When enabled, Security Panel shows NSM links of the containing Prefix "
                    "on child objects (IP Address, IP Range, sub-Prefix)."
                ),
            ),
        ),
        migrations.AddField(
            model_name="typeconfig",
            name="inherit_stop_on_own",
            field=models.BooleanField(
                default=False,
                verbose_name="Stop inheritance if own link present",
                help_text=(
                    "If the child object already has its own direct NSM link of the same "
                    "type, inherited links of that type are suppressed."
                ),
            ),
        ),
    ]
