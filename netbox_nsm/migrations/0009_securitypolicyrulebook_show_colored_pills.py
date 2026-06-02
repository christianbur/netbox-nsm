from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0008_typeconfig_panel_linkable"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicyrulebook",
            name="show_colored_pills",
            field=models.BooleanField(
                default=True,
                verbose_name="Show colored pills",
                help_text=(
                    "Display object links as colored bubbles in the policy table. "
                    "Disable to show plain text pills without background color."
                ),
            ),
        ),
    ]
