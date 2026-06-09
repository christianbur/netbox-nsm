"""Remove native ObjectLink table (data must be migrated to COT first)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0003_cot_rulebook_hierarchy"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ObjectLink",
        ),
    ]
