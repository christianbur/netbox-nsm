from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0004_typeconfig_multi_matching_class"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicyrulebook",
            name="mgmt_url",
            field=models.URLField(
                blank=True,
                default="",
                verbose_name="Management URL",
                help_text="Link to the management interface of the associated firewall or device.",
            ),
        ),
    ]
