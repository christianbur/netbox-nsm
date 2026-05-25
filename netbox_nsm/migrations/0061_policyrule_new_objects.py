from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0060_objectfilter_objectpolicer"),
    ]

    operations = [
        # Add new M2M fields
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_nat",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_nat",
                to="netbox_nsm.objectnat",
                verbose_name="NAT Objects",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_interface",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_interface",
                to="netbox_nsm.objectinterface",
                verbose_name="Interface Objects",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_filter",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_filter",
                to="netbox_nsm.objectfilter",
                verbose_name="Filter Objects",
            ),
        ),
        migrations.AddField(
            model_name="securityzonepolicyrule",
            name="object_policer",
            field=models.ManyToManyField(
                blank=True,
                related_name="securityzonepolicyrule_object_policer",
                to="netbox_nsm.objectpolicer",
                verbose_name="Policer Objects",
            ),
        ),
        # Remove old M2M fields
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="nat_rules",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="firewall_filters",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="policers",
        ),
    ]
