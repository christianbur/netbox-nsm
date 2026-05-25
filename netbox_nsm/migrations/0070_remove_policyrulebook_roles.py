from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0069_remove_assignment_models_and_securityzonerole"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="securityzonepolicyrulebook",
            name="roles",
        ),
    ]
