from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0079_remove_securityzone_applicationitem"),
    ]

    operations = [
        migrations.AlterField(
            model_name="securityzonepolicyrulebook",
            name="rulebook_type",
            field=models.CharField(
                choices=[("policy", "Security Rules")],
                default="policy",
                max_length=20,
            ),
        ),
    ]
