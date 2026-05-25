# Generated manually for netbox_nsm

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0029_securityzonerole_and_zone_role_fk"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonerole",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="users.owner",
            ),
        ),
    ]
