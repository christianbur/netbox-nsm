from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_nsm", "0077_labels_type_flexible_text"),
    ]

    operations = [
        # Remove M2M fields from SecurityZonePolicyRule
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="applications",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="application_sets",
        ),
        # Remove M2M fields from ApplicationSet itself
        migrations.RemoveField(
            model_name="applicationset",
            name="applications",
        ),
        migrations.RemoveField(
            model_name="applicationset",
            name="application_sets",
        ),
        # Remove M2M from Application
        migrations.RemoveField(
            model_name="application",
            name="application_items",
        ),
        # Delete models
        migrations.DeleteModel(name="ApplicationSet"),
        migrations.DeleteModel(name="Application"),
    ]
