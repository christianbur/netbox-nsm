from django.db import migrations


RULEBOOK_PERMISSIONS = (
    ("view_rulebook", "Can view rulebooks"),
    ("add_rulebook", "Can add rulebooks"),
)

ASSIGNMENT_PERMISSIONS = (
    ("view_rulebookassignment", "Can view rulebook assignments"),
    ("add_rulebookassignment", "Can add rulebook assignments"),
    ("change_rulebookassignment", "Can change rulebook assignments"),
    ("delete_rulebookassignment", "Can delete rulebook assignments"),
)


def _reassign_auth_permissions(apps, *, old_ct, new_ct_by_codename):
    Permission = apps.get_model("auth", "Permission")
    for codename, new_ct in new_ct_by_codename.items():
        old_perm = Permission.objects.filter(
            content_type=old_ct,
            codename=codename,
        ).first()
        if old_perm is None:
            continue
        new_perm, _created = Permission.objects.get_or_create(
            content_type=new_ct,
            codename=codename,
            defaults={"name": old_perm.name},
        )
        for user in old_perm.user_set.all():
            user.user_permissions.remove(old_perm)
            user.user_permissions.add(new_perm)
        for group in old_perm.group_set.all():
            group.permissions.remove(old_perm)
            group.permissions.add(new_perm)
        old_perm.delete()


def _reassign_object_permissions(apps, *, old_ct, rulebook_ct, assignment_ct):
    ObjectPermission = apps.get_model("users", "ObjectPermission")
    rulebook_names = {
        f"netbox_nsm.{codename}" for codename, _label in RULEBOOK_PERMISSIONS
    }
    assignment_names = {
        f"netbox_nsm.{codename}" for codename, _label in ASSIGNMENT_PERMISSIONS
    }

    for obj_perm in ObjectPermission.objects.filter(object_types=old_ct).distinct():
        name = obj_perm.name or ""
        obj_perm.object_types.remove(old_ct)
        if name in rulebook_names:
            obj_perm.object_types.add(rulebook_ct)
        elif name in assignment_names:
            obj_perm.object_types.add(assignment_ct)
        else:
            obj_perm.object_types.add(old_ct)


def migrate_rulebook_permissions(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    old_ct = ContentType.objects.filter(
        app_label="netbox_nsm",
        model="cotrulebookassignment",
    ).first()
    rulebook_ct = ContentType.objects.filter(
        app_label="netbox_nsm",
        model="rulebook",
    ).first()
    assignment_ct = ContentType.objects.filter(
        app_label="netbox_nsm",
        model="rulebookassignment",
    ).first()
    if old_ct is None or rulebook_ct is None or assignment_ct is None:
        return

    new_ct_by_codename = {
        codename: rulebook_ct for codename, _label in RULEBOOK_PERMISSIONS
    }
    new_ct_by_codename.update(
        {codename: assignment_ct for codename, _label in ASSIGNMENT_PERMISSIONS}
    )
    _reassign_auth_permissions(
        apps,
        old_ct=old_ct,
        new_ct_by_codename=new_ct_by_codename,
    )
    _reassign_object_permissions(
        apps,
        old_ct=old_ct,
        rulebook_ct=rulebook_ct,
        assignment_ct=assignment_ct,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0003_migrate_cotrulebook_to_nsm_config"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="Rulebook",
            fields=[],
            options={
                "verbose_name": "Rulebook",
                "verbose_name_plural": "Rulebooks",
                "permissions": list(RULEBOOK_PERMISSIONS),
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.CreateModel(
            name="RulebookAssignment",
            fields=[],
            options={
                "verbose_name": "Rulebook Assignment",
                "verbose_name_plural": "Rulebook Assignments",
                "permissions": list(ASSIGNMENT_PERMISSIONS),
                "proxy": True,
                "default_permissions": (),
                "indexes": [],
                "constraints": [],
            },
            bases=("netbox_nsm.cotrulebookassignment",),
        ),
        migrations.AlterModelOptions(
            name="cotrulebookassignment",
            options={
                "ordering": ("cot_slug", "assigned_object_id"),
                "verbose_name": "Rulebook Assignment",
                "verbose_name_plural": "Rulebook Assignments",
            },
        ),
        migrations.RunPython(
            migrate_rulebook_permissions,
            migrations.RunPython.noop,
        ),
    ]
