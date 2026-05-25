from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0040_objectlabel_single_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzone",
            name="color",
            field=models.CharField(default="#808080", max_length=7),
        ),
    ]
