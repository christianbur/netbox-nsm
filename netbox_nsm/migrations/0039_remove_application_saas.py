from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0038_application_profile_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="application",
            name="saas",
        ),
    ]
