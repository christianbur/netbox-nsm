from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0068_remove_firewall_filter_object_label_sgt_user_log"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AddressAssignment",
        ),
        migrations.DeleteModel(
            name="AddressListAssignment",
        ),
        migrations.DeleteModel(
            name="AddressSetAssignment",
        ),
        migrations.DeleteModel(
            name="ApplicationAssignment",
        ),
        migrations.DeleteModel(
            name="ApplicationSetAssignment",
        ),
        migrations.DeleteModel(
            name="ObjectGroupAssignment",
        ),
        migrations.DeleteModel(
            name="SecurityZoneAssignment",
        ),
        migrations.RemoveField(
            model_name="securityzone",
            name="roles",
        ),
        migrations.DeleteModel(
            name="SecurityZoneRole",
        ),
    ]
