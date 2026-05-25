from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0070_remove_policyrulebook_roles"),
    ]

    operations = [
        # Remove ObjectGroup.addresses M2M (referenced Address)
        migrations.RemoveField(
            model_name="objectgroup",
            name="addresses",
        ),
        # Remove M2M fields on SecurityZonePolicyRule that reference AddressList
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="source_addresses",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="destination_addresses",
        ),
        # Delete the Address / AddressSet / AddressList models
        migrations.DeleteModel(
            name="AddressSet",
        ),
        migrations.DeleteModel(
            name="AddressList",
        ),
        migrations.DeleteModel(
            name="Address",
        ),
    ]
