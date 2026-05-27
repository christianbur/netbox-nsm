from django.db import migrations, models


BUILTIN_AREAS = [
    ("source", "Source", 1),
    ("destination", "Destination", 2),
    ("services", "Services", 3),
    ("application", "Applikation", 4),
    ("action", "Action", 5),
]

LEGACY_ORDER = {
    "srcdst": 1,
    "service": 3,
    "applications": 4,
    "info": 90,
}


def set_area_order_defaults(apps, schema_editor):
    SecurityArea = apps.get_model("netbox_nsm", "SecurityArea")

    for slug, name, order in BUILTIN_AREAS:
        SecurityArea.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "sort_order": order,
                "is_system": True,
            },
        )

    for slug, order in LEGACY_ORDER.items():
        SecurityArea.objects.filter(slug=slug).update(sort_order=order)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_securityobject_display_template_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="securityarea",
            name="sort_order",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.RunPython(set_area_order_defaults, noop),
    ]
