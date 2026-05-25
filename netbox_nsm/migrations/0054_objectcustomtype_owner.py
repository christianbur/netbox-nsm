import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0053_objectcustomtype"),
        ("users", "0015_owner"),
    ]

    operations = [
        migrations.AddField(
            model_name="objectcustomtype",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="users.owner",
            ),
        ),
    ]
