from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0063_objectcustomobjectassignment"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="icon",
            field=models.CharField(
                blank=True,
                default="",
                help_text='MDI-Icon-Name von pictogrammers.com (z.B. "mdi-server", "mdi-tag"). Immer mit "mdi-" Präfix angeben.',
                max_length=100,
            ),
        ),
    ]
