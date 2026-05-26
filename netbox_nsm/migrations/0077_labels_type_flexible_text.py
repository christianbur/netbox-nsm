from django.db import migrations


NEW_FIELD_DEFINITIONS = [
    {"__meta__": True, "hide_table_data": True},
    {
        "name": "label_type",
        "type": "choice",
        "label": "Label Type",
        "choices": ["Role", "Application", "Environment", "Location", "Flexible labels"],
        "required": True,
    },
    {
        "name": "flexible_text",
        "type": "text",
        "label": "Label Text",
        "visible_when": {"field": "label_type", "value": "Flexible labels"},
    },
    {"name": "color", "type": "text", "label": "Color"},
]


def update_labels_type(apps, schema_editor):
    ObjectCustomType = apps.get_model("netbox_nsm", "ObjectCustomType")
    ObjectCustomType.objects.filter(name="Labels").update(
        field_definitions=NEW_FIELD_DEFINITIONS,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0076_labels_type_choice_field"),
    ]

    operations = [
        migrations.RunPython(update_labels_type, migrations.RunPython.noop),
    ]
