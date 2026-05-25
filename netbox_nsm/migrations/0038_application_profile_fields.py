from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0037_migrate_address_sets_to_object_groups"),
    ]

    operations = [
        migrations.AddField(
            model_name="application",
            name="category",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="application",
            name="subcategory",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="application",
            name="standard_ports_text",
            field=models.CharField(
                blank=True,
                help_text="Optional standard ports as text, e.g. tcp/22",
                max_length=255,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="application",
            name="technology",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="application",
            name="saas",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="application",
            name="reference",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
