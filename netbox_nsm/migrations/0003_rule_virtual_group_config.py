"""Add Rule.virtual_group_config for AND-group rendering in the rule editor."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_rulebook_type_security_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="rule",
            name="virtual_group_config",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
