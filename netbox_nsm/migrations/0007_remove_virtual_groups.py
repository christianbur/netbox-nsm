from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0006_objectlink_propagation"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="typeconfig",
            name="allow_virtual_groups",
        ),
        migrations.RemoveField(
            model_name="rule",
            name="virtual_group_config",
        ),
    ]
