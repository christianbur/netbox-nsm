import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0009_securitypolicyrulebook_show_colored_pills"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebookfieldtype",
            name="show_colored_pills",
            field=models.BooleanField(
                default=True,
                help_text="Display objects of this type as colored pills (using the TypeConfig color). Disable to show plain pills without background color.",
                verbose_name="Show colored pills",
            ),
        ),
    ]
