from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0007_typeconfig_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="typeconfig",
            name="panel_linkable",
            field=models.BooleanField(
                default=True,
                help_text="If enabled, objects of this type can be linked from the NSM Security Panel.",
                verbose_name="Linkable in panel",
            ),
        ),
    ]
