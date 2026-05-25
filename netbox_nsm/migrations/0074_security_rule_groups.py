from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0073_add_object_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="destination_custom_objects",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={"custom_type__area": "srcdst"},
                related_name="securityzonepolicyrule_destination_custom",
                to="netbox_nsm.objectcustomobject",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="source_groups",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={"area": "srcdst"},
                related_name="securityzonepolicyrule_source_groups",
                to="netbox_nsm.objectgroup",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="destination_groups",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={"area": "srcdst"},
                related_name="securityzonepolicyrule_destination_groups",
                to="netbox_nsm.objectgroup",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="service_groups",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={"area": "services"},
                related_name="securityzonepolicyrule_service_groups",
                to="netbox_nsm.objectgroup",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="action_groups",
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={"area": "action"},
                related_name="securityzonepolicyrule_action_groups",
                to="netbox_nsm.objectgroup",
            ),
        ),
    ]
