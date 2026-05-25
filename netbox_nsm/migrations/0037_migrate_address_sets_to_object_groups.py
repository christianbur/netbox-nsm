from django.db import IntegrityError, migrations


MIGRATION_MARKER = "[migrated-from-address-set]"


def _build_unique_name(base_name, used_names):
    name = (base_name or "Address Set").strip() or "Address Set"
    if name not in used_names:
        return name

    idx = 2
    while True:
        candidate = f"{name} ({idx})"
        if candidate not in used_names:
            return candidate
        idx += 1


def _collect_address_ids(root_set, by_id):
    address_ids = set(root_set.addresses.values_list("id", flat=True))
    visited = {root_set.id}
    queue = list(root_set.address_sets.values_list("id", flat=True))

    while queue:
        set_id = queue.pop(0)
        if set_id in visited:
            continue
        visited.add(set_id)

        nested = by_id.get(set_id)
        if not nested:
            continue

        address_ids.update(nested.addresses.values_list("id", flat=True))
        queue.extend(nested.address_sets.values_list("id", flat=True))

    return address_ids


def forwards(apps, schema_editor):
    AddressSet = apps.get_model("netbox_nsm", "AddressSet")
    ObjectGroup = apps.get_model("netbox_nsm", "ObjectGroup")

    address_sets = list(
        AddressSet.objects.all().prefetch_related("addresses", "address_sets")
    )
    by_id = {obj.id: obj for obj in address_sets}

    used_names = set(ObjectGroup.objects.values_list("name", flat=True))

    for address_set in address_sets:
        marker = f"{MIGRATION_MARKER}:{address_set.id}"
        if ObjectGroup.objects.filter(comments__contains=marker).exists():
            continue

        comments = (address_set.comments or "").strip()
        if comments:
            comments = f"{comments}\n\n{marker}"
        else:
            comments = marker

        name_seed = (address_set.name or "Address Set").strip() or "Address Set"
        attempt = 1
        group = None
        while group is None:
            group_name = _build_unique_name(name_seed, used_names)
            try:
                group = ObjectGroup.objects.create(
                    name=group_name,
                    group_type="addresses",
                    description=address_set.description or "",
                    comments=comments,
                    owner_id=address_set.owner_id,
                )
            except IntegrityError:
                # Handle pre-existing names or race-like collisions deterministically.
                attempt += 1
                name_seed = f"{(address_set.name or 'Address Set').strip() or 'Address Set'} ({attempt})"

        used_names.add(group.name)

        address_ids = _collect_address_ids(address_set, by_id)
        if address_ids:
            group.addresses.set(address_ids)


def reverse(apps, schema_editor):
    ObjectGroup = apps.get_model("netbox_nsm", "ObjectGroup")
    ObjectGroup.objects.filter(comments__contains=MIGRATION_MARKER).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_nsm", "0036_objects_menu_models"),
    ]

    operations = [
        migrations.RunPython(forwards, reverse),
    ]
