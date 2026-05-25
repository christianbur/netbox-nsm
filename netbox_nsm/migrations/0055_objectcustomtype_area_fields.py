from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0054_objectcustomtype_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="area",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("srcdst", "Source/Destination"),
                    ("services", "Services"),
                    ("action", "Action"),
                ],
                default="srcdst",
            ),
        ),
        migrations.AddField(
            model_name="objectcustomtype",
            name="field_definitions",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
