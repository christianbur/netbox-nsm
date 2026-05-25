import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0032_security_zone_policy_rulebook"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityzonepolicyrulebook",
            name="roles",
            field=models.ManyToManyField(
                blank=True,
                related_name="policy_rulebooks",
                to="netbox_nsm.securityzonerole",
            ),
        ),
    ]
