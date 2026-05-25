from django.db import migrations


OBJECT_TYPE_DEFINITIONS = (
    {
        "name": "builder_address",
        "verbose_name": "Builder Address",
        "verbose_name_plural": "Builder Addresses",
        "slug": "builder-address",
        "group_name": "Builder",
        "description": "Address objects managed via NSM builder.",
        "fields": (
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": True,
                "weight": 100,
                "description": "Human readable address object name.",
            },
            {
                "name": "value",
                "label": "Address Value",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 110,
                "description": "Address, prefix, range, or FQDN.",
            },
        ),
    },
    {
        "name": "builder_zone",
        "verbose_name": "Builder Zone",
        "verbose_name_plural": "Builder Zones",
        "slug": "builder-zone",
        "group_name": "Builder",
        "description": "Security zone objects managed via NSM builder.",
        "fields": (
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": True,
                "weight": 100,
                "description": "Zone name.",
            },
            {
                "name": "color",
                "label": "Color",
                "type": "text",
                "required": False,
                "unique": False,
                "weight": 110,
                "description": "Display color for this zone.",
            },
        ),
    },
    {
        "name": "builder_label",
        "verbose_name": "Builder Label",
        "verbose_name_plural": "Builder Labels",
        "slug": "builder-label",
        "group_name": "Builder",
        "description": "Label objects managed via NSM builder.",
        "fields": (
            {
                "name": "type_short",
                "label": "Type Short",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 100,
                "description": "Short label type identifier.",
            },
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 110,
                "description": "Label name.",
            },
        ),
    },
    {
        "name": "builder_sgt",
        "verbose_name": "Builder SGT",
        "verbose_name_plural": "Builder SGTs",
        "slug": "builder-sgt",
        "group_name": "Builder",
        "description": "SGT objects managed via NSM builder.",
        "fields": (
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 100,
                "description": "SGT name.",
            },
            {
                "name": "tag",
                "label": "Tag",
                "type": "integer",
                "required": False,
                "unique": False,
                "weight": 110,
                "description": "Numeric SGT tag.",
            },
        ),
    },
    {
        "name": "builder_user",
        "verbose_name": "Builder User",
        "verbose_name_plural": "Builder Users",
        "slug": "builder-user",
        "group_name": "Builder",
        "description": "User and group identity objects managed via NSM builder.",
        "fields": (
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 100,
                "description": "Identity object name.",
            },
            {
                "name": "dn",
                "label": "Distinguished Name",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 110,
                "description": "LDAP distinguished name.",
            },
            {
                "name": "entry_type",
                "label": "Entry Type",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 120,
                "description": "Expected values: user or group.",
            },
        ),
    },
    {
        "name": "builder_group",
        "verbose_name": "Builder Group",
        "verbose_name_plural": "Builder Groups",
        "slug": "builder-group",
        "group_name": "Builder",
        "description": "Object groups managed via NSM builder.",
        "fields": (
            {
                "name": "name",
                "label": "Name",
                "type": "text",
                "required": True,
                "unique": True,
                "weight": 100,
                "description": "Group name.",
            },
            {
                "name": "group_type",
                "label": "Group Type",
                "type": "text",
                "required": True,
                "unique": False,
                "weight": 110,
                "description": "Expected values: mixed, addresses, services, applications, labels, zones, sgts, users.",
            },
        ),
    },
)


def seed_builder_object_types(apps, schema_editor):
    NsmObjectType = apps.get_model("netbox_nsm", "NsmObjectType")
    NsmObjectTypeField = apps.get_model("netbox_nsm", "NsmObjectTypeField")

    for definition in OBJECT_TYPE_DEFINITIONS:
        object_type, _ = NsmObjectType.objects.get_or_create(
            name=definition["name"],
            defaults={
                "verbose_name": definition["verbose_name"],
                "verbose_name_plural": definition["verbose_name_plural"],
                "slug": definition["slug"],
                "group_name": definition["group_name"],
                "description": definition["description"],
            },
        )

        updates = {}
        if not object_type.verbose_name:
            updates["verbose_name"] = definition["verbose_name"]
        if not object_type.verbose_name_plural:
            updates["verbose_name_plural"] = definition["verbose_name_plural"]
        if not object_type.slug:
            updates["slug"] = definition["slug"]
        if not object_type.group_name:
            updates["group_name"] = definition["group_name"]
        if not object_type.description:
            updates["description"] = definition["description"]
        if updates:
            for key, value in updates.items():
                setattr(object_type, key, value)
            object_type.save(update_fields=list(updates.keys()) + ["last_updated"])

        for field_definition in definition["fields"]:
            NsmObjectTypeField.objects.get_or_create(
                nsm_object_type=object_type,
                name=field_definition["name"],
                defaults={
                    "label": field_definition["label"],
                    "type": field_definition["type"],
                    "required": field_definition["required"],
                    "unique": field_definition["unique"],
                    "weight": field_definition["weight"],
                    "description": field_definition["description"],
                },
            )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0043_nsm_object_builder"),
    ]

    operations = [
        migrations.RunPython(seed_builder_object_types, noop_reverse),
    ]
