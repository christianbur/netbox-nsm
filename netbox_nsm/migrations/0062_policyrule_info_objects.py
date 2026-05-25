from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0061_policyrule_new_objects"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_comment",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_comment",
                to="netbox_nsm.objectcomment",
                verbose_name="Comment Objects",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_installed_on",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_installed_on",
                to="netbox_nsm.objectinstalledon",
                verbose_name="Installed On Objects",
            ),
        ),
    ]
