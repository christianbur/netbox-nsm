from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0006_cotrulebook_matrix_tab_enabled"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="typeconfig",
            options={
                "ordering": (
                    "name",
                    "content_type__app_label",
                    "content_type__model",
                    "matching_class",
                ),
                "verbose_name": "Type Config",
                "verbose_name_plural": "Type Configs",
            },
        ),
        migrations.RemoveField(
            model_name="typeconfig",
            name="order_id",
        ),
        migrations.RemoveField(
            model_name="typeconfig",
            name="panel_slugs",
        ),
    ]
