"""Drop legacy ObjectGroup/Property* tables (replaced by COT group M2M and Custom Objects)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0004_delete_objectlink"),
    ]

    operations = [
        migrations.DeleteModel(name="ObjectGroupMember"),
        migrations.DeleteModel(name="Property"),
        migrations.DeleteModel(name="PropertyField"),
        migrations.DeleteModel(name="ObjectGroup"),
        migrations.DeleteModel(name="PropertyType"),
    ]
