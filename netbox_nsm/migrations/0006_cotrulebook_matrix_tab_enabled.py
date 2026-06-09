from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0005_remove_legacy_object_and_property_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotrulebook",
            name="matrix_tab_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "When enabled, show the Matrix tab for rulebooks with source and "
                    "destination zone columns."
                ),
                verbose_name="Matrix tab enabled",
            ),
        ),
    ]
