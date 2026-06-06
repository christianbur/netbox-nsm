from django.db import migrations, models


def set_empty_panel_labels(apps, schema_editor):
    NsmUiSettings = apps.get_model("netbox_nsm", "NsmUiSettings")
    NsmUiSettings.objects.filter(panel_label="").update(panel_label="Security")


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0003_nsm_ui_settings"),
    ]

    operations = [
        migrations.RunPython(set_empty_panel_labels, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="nsmuisettings",
            name="panel_label",
            field=models.CharField(
                default="Security",
                help_text="Security card title on object detail pages.",
                max_length=100,
                verbose_name="Panel label",
            ),
        ),
    ]
