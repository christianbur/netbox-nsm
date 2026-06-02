import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0001_initial"),
        ("netbox_nsm", "0005_securitypolicyrulebook_mgmt_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicyrulebook",
            name="platform",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="nsm_rulebooks",
                to="dcim.platform",
                verbose_name="Platform",
                help_text="Firewall platform or security fabric (e.g. PAN-OS, Cisco ASA, TrustSec, Zscaler).",
            ),
        ),
    ]
