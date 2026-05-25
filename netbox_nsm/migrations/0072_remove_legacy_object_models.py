from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0071_remove_address_models"),
    ]

    operations = [
        # Remove M2M fields from SecurityZonePolicyRule
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="source_groups",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="destination_groups",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_nat",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_interface",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_filter",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_policer",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_comment",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="action_objects",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="object_installed_on",
        ),
        # Delete legacy model tables
        migrations.DeleteModel(name="ObjectGroup"),
        migrations.DeleteModel(name="ObjectNAT"),
        migrations.DeleteModel(name="ObjectInterface"),
        migrations.DeleteModel(name="ObjectFilter"),
        migrations.DeleteModel(name="ObjectPolicer"),
        migrations.DeleteModel(name="ObjectComment"),
        migrations.DeleteModel(name="ObjectInstalledOn"),        migrations.DeleteModel(name="ObjectAction"),
        migrations.DeleteModel(name="CustomPrefix"),    ]
