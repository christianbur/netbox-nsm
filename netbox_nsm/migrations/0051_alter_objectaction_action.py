from django.db import migrations, models


DEFAULT_OBJECT_ACTIONS = (
    ("Permit", "permit"),
    ("Deny", "deny"),
    ("Drop", "drop"),
)


def seed_default_object_actions(apps, schema_editor):
    ObjectAction = apps.get_model("netbox_nsm", "ObjectAction")

    for default_name, default_action in DEFAULT_OBJECT_ACTIONS:
        existing = (
            ObjectAction.objects.filter(action__iexact=default_action).order_by("pk").first()
        )
        if existing is None:
            existing = (
                ObjectAction.objects.filter(name__iexact=default_name).order_by("pk").first()
            )

        if existing is None:
            ObjectAction.objects.create(name=default_name, action=default_action)
            continue

        updates = []
        if not existing.name:
            existing.name = default_name
            updates.append("name")
        if not existing.action:
            existing.action = default_action
            updates.append("action")
        if updates:
            existing.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0050_objectlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="objectaction",
            name="action",
            field=models.CharField(default="permit", max_length=100),
        ),
        migrations.RunPython(
            seed_default_object_actions,
            migrations.RunPython.noop,
        ),
    ]