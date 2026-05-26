from django.db import migrations


def delete_object_changes_for_removed_models(apps, schema_editor):
    """Delete ObjectChange records referencing SecurityZone and ApplicationItem ContentTypes."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    ObjectChange = apps.get_model("extras", "ObjectChange")

    ct_qs = ContentType.objects.filter(
        app_label="netbox_nsm",
        model__in=["securityzone", "applicationitem"],
    )
    ObjectChange.objects.filter(changed_object_type__in=ct_qs).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0078_remove_application_applicationset"),
    ]

    operations = [
        migrations.RunPython(
            delete_object_changes_for_removed_models,
            migrations.RunPython.noop,
        ),
        # Remove M2M fields from SecurityZonePolicyRule
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="source_zones",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="destination_zones",
        ),
        migrations.RemoveField(
            model_name="securityzonepolicyrule",
            name="services",
        ),
        # Delete SecurityZone model
        migrations.DeleteModel(
            name="SecurityZone",
        ),
        # Delete ApplicationItem model
        migrations.DeleteModel(
            name="ApplicationItem",
        ),
    ]
