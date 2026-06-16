"""Remove TypeConfig permission anchor; map legacy perms to netbox-custom-objects."""

from django.db import migrations

_TYPECONFIG_PERMS = (
    "view_typeconfig",
    "add_typeconfig",
    "change_typeconfig",
    "delete_typeconfig",
)

_COT_PERM_MAP = {
    "view_typeconfig": "view_customobjecttype",
    "add_typeconfig": "add_customobjecttype",
    "change_typeconfig": "change_customobjecttype",
    "delete_typeconfig": "change_customobjecttype",
}


def _map_typeconfig_permissions_to_cot(apps, schema_editor):
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    typeconfig_perms = Permission.objects.filter(
        content_type__app_label="netbox_nsm",
        content_type__model="typeconfig",
    )
    perm_by_codename = {p.codename: p for p in typeconfig_perms}

    cot_perms = {
        p.codename: p
        for p in Permission.objects.filter(
            content_type__app_label="netbox_custom_objects",
            content_type__model="customobjecttype",
        )
    }

    for legacy_codename, cot_codename in _COT_PERM_MAP.items():
        legacy_perm = perm_by_codename.get(legacy_codename)
        cot_perm = cot_perms.get(cot_codename)
        if legacy_perm is None or cot_perm is None:
            continue
        for group in Group.objects.filter(permissions=legacy_perm):
            group.permissions.add(cot_perm)


def _remove_typeconfig_object_type(apps, schema_editor):
    ObjectType = apps.get_model("core", "ObjectType")
    ObjectType.objects.filter(app_label="netbox_nsm", model="typeconfig").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0002_private_permission_anchors"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("core", "0008_contenttype_proxy"),
        ("netbox_custom_objects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            _map_typeconfig_permissions_to_cot,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="TypeConfig",
        ),
        migrations.RunPython(
            _remove_typeconfig_object_type,
            migrations.RunPython.noop,
        ),
    ]
