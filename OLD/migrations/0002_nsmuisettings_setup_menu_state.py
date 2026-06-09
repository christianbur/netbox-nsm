from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="nsmuisettings",
            name="setup_menu_config_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Tracks the last observed PLUGINS_CONFIG setup_menu value for "
                    "restore after toggling false → true."
                ),
                verbose_name="Last seen setup_menu config",
            ),
        ),
        migrations.AddField(
            model_name="nsmuisettings",
            name="setup_menu_dismissed",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, the Setup menu entry stays hidden until restored "
                    "via plugin configuration."
                ),
                verbose_name="Setup menu dismissed",
            ),
        ),
    ]
