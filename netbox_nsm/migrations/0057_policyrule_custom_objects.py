from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0056_objectcustomobject"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="custom_srcdst_objects",
            field=models.ManyToManyField(
                blank=True,
                related_name="%(class)s_custom_srcdst",
                to="netbox_nsm.objectcustomobject",
                limit_choices_to={"custom_type__area": "srcdst"},
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="custom_service_objects",
            field=models.ManyToManyField(
                blank=True,
                related_name="%(class)s_custom_services",
                to="netbox_nsm.objectcustomobject",
                limit_choices_to={"custom_type__area": "services"},
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="custom_action_objects",
            field=models.ManyToManyField(
                blank=True,
                related_name="%(class)s_custom_action",
                to="netbox_nsm.objectcustomobject",
                limit_choices_to={"custom_type__area": "action"},
            ),
        ),
    ]
