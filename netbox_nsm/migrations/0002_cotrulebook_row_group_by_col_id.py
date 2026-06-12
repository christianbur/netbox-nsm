from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotrulebook",
            name="row_group_by_col_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Rules tab column used for side-tab row grouping (col_id from the rules table layout).",
                max_length=200,
                verbose_name="Row group column",
            ),
        ),
    ]
