from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0003_rulebookfield_facet_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookfieldtype",
            name="show_as_facet_tab",
            field=models.BooleanField(
                default=False,
                verbose_name="Show as facet tab",
                help_text=(
                    "When enabled, objects of this type are shown as a dedicated sidebar tab "
                    "(named after this type). Clicking an entry sets an exclusive filter for that value."
                ),
            ),
        ),
    ]
