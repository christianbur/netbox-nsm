from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0008_rulebook_parent"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulebook",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("deprecated", "Deprecated"),
                    ("reserved", "Reserved"),
                    ("container", "Container"),
                ],
                default="active",
                max_length=20,
                verbose_name="Status",
            ),
        ),
    ]
