from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0045_nsm_object_instances"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectgroup",
            name="groups",
            field=models.ManyToManyField(blank=True, symmetrical=False, to="netbox_nsm.objectgroup"),
        ),
        migrations.AlterField(
            model_name="objectgroup",
            name="group_type",
            field=models.CharField(
                choices=[
                    ("mixed", "Mixed"),
                    ("groups", "Groups"),
                    ("addresses", "Addresses"),
                    ("services", "Services"),
                    ("applications", "Applications"),
                    ("labels", "Labels"),
                    ("zones", "Zones"),
                    ("sgts", "SGTs"),
                    ("users", "Users"),
                ],
                default="mixed",
                max_length=20,
            ),
        ),
    ]
