from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from netaddr import IPAddress as NetaddrIPAddress, IPNetwork

from ipam.models import IPAddress, IPRange, Prefix

from netbox_nsm.models import Address, AddressList, AddressSet


def _object_bounds(obj):
    if isinstance(obj, IPAddress) and getattr(obj, "address", None):
        return int(NetaddrIPAddress(str(obj.address).split("/")[0])), int(NetaddrIPAddress(str(obj.address).split("/")[0]))

    if isinstance(obj, IPRange):
        start_value = getattr(obj, "start_address", None) or getattr(obj, "start", None)
        end_value = getattr(obj, "end_address", None) or getattr(obj, "end", None)
        if start_value and end_value:
            start = int(IPNetwork(str(start_value)).first)
            end = int(IPNetwork(str(end_value)).last)
            return start, end

    if isinstance(obj, Prefix) and getattr(obj, "prefix", None):
        network = IPNetwork(str(obj.prefix))
        return int(network.first), int(network.last)

    return None


def _contains_object(parent_obj, child_obj):
    parent_bounds = _object_bounds(parent_obj)
    child_bounds = _object_bounds(child_obj)
    if not parent_bounds or not child_bounds:
        return False
    return parent_bounds[0] <= child_bounds[0] and parent_bounds[1] >= child_bounds[1]


def _get_inherited_address_ids(target_object, direct_address_ids):
    inherited_address_ids = set()

    if not target_object:
        return inherited_address_ids

    candidate_prefixes = Prefix.objects.filter(addresses__isnull=False).distinct()
    candidate_ranges = IPRange.objects.filter(addresses__isnull=False).distinct()

    for candidate in candidate_prefixes:
        if candidate.pk == target_object.pk and candidate.__class__ == target_object.__class__:
            continue
        if _contains_object(candidate, target_object):
            inherited_address_ids.update(
                candidate.addresses.exclude(pk__in=direct_address_ids).values_list("pk", flat=True)
            )

    for candidate in candidate_ranges:
        if candidate.pk == target_object.pk and candidate.__class__ == target_object.__class__:
            continue
        if _contains_object(candidate, target_object):
            inherited_address_ids.update(
                candidate.addresses.exclude(pk__in=direct_address_ids).values_list("pk", flat=True)
            )

    return inherited_address_ids


def get_address_set_hierarchy(*, app_label, model, object_id):
    """Return transitive security context for an assigned IPAM object.

    Traversal:
    assigned object -> Address -> AddressSet (direct + parent hierarchy) ->
    AddressList -> SecurityZonePolicy (source/destination)
    """
    content_type = ContentType.objects.filter(app_label=app_label, model=model).first()
    if not content_type:
        return {
            "assigned_object_id": None,
            "address_ids": [],
            "inherited_address_ids": [],
            "address_objects": [],
            "inherited_address_objects": [],
            "direct_address_set_ids": [],
            "all_address_set_ids": [],
            "address_set_paths": [],
            "address_set_object_paths": [],
            "address_set_hierarchy_rows": [],
            "address_set_name_paths": [],
            "address_list_ids": [],
            "address_list_names": [],
            "policy_paths": [],
        }

    address_ids = list(
        Address.objects.filter(
            assigned_object_type=content_type,
            assigned_object_id=object_id,
        ).values_list("id", flat=True)
    )
    target_object = content_type.model_class().objects.filter(pk=object_id).first()
    inherited_address_ids = _get_inherited_address_ids(target_object, address_ids)
    effective_address_ids = sorted(set(address_ids) | set(inherited_address_ids))

    if not effective_address_ids:
        return {
            "assigned_object_id": object_id,
            "address_ids": [],
            "inherited_address_ids": [],
            "address_objects": [],
            "inherited_address_objects": [],
            "direct_address_set_ids": [],
            "all_address_set_ids": [],
            "address_set_paths": [],
            "address_set_object_paths": [],
            "address_set_hierarchy_rows": [],
            "address_set_name_paths": [],
            "address_list_ids": [],
            "address_list_names": [],
            "policy_paths": [],
        }

    direct_address_set_ids = set(
        AddressSet.objects.filter(addresses__id__in=effective_address_ids)
        .values_list("id", flat=True)
        .distinct()
    )

    relation_field = AddressSet._meta.get_field("address_sets")
    parent_field = relation_field.m2m_field_name()
    child_field = relation_field.m2m_reverse_field_name()
    through_model = relation_field.remote_field.through

    parent_map = defaultdict(set)
    all_address_set_ids = set(direct_address_set_ids)
    frontier = set(direct_address_set_ids)

    while frontier:
        relation_rows = through_model.objects.filter(
            **{f"{child_field}_id__in": list(frontier)}
        ).values_list(f"{parent_field}_id", f"{child_field}_id")

        new_frontier = set()
        for parent_id, child_id in relation_rows:
            parent_map[child_id].add(parent_id)
            if parent_id not in all_address_set_ids:
                all_address_set_ids.add(parent_id)
                new_frontier.add(parent_id)

        frontier = new_frontier

    def build_addressset_paths(child_id, trail=None):
        if trail is None:
            trail = set()
        if child_id in trail:
            return []

        parents = sorted(parent_map.get(child_id, ()))
        if not parents:
            return [[child_id]]

        paths = []
        for parent_id in parents:
            for parent_path in build_addressset_paths(parent_id, trail | {child_id}):
                paths.append([*parent_path, child_id])
        return paths

    addressset_paths = []
    paths_by_direct_set = {}
    for direct_id in sorted(direct_address_set_ids):
        direct_paths = build_addressset_paths(direct_id)
        paths_by_direct_set[direct_id] = direct_paths
        addressset_paths.extend(direct_paths)
    unique_addressset_paths = sorted({tuple(path) for path in addressset_paths})
    direct_memberships = (
        AddressSet.objects.filter(addresses__id__in=effective_address_ids)
        .values_list("addresses__id", "id")
        .distinct()
    )
    direct_sets_by_address = defaultdict(set)
    for address_id, address_set_id in direct_memberships:
        direct_sets_by_address[address_id].add(address_set_id)

    address_object_map = {
        obj.pk: obj for obj in Address.objects.filter(id__in=effective_address_ids)
    }
    address_set_object_map = {
        obj.pk: obj for obj in AddressSet.objects.filter(id__in=all_address_set_ids)
    }

    hierarchy_rows = set()
    for address_id in sorted(effective_address_ids):
        for direct_set_id in sorted(direct_sets_by_address.get(address_id, ())):
            for path in paths_by_direct_set.get(direct_set_id, [[direct_set_id]]):
                hierarchy_rows.add((tuple(path), address_id))
    sorted_hierarchy_rows = sorted(hierarchy_rows)

    address_ct = ContentType.objects.get_for_model(Address)
    address_set_ct = ContentType.objects.get_for_model(AddressSet)

    address_list_ids = set(
        AddressList.objects.filter(
            assigned_object_type=address_ct,
            assigned_object_id__in=effective_address_ids,
        ).values_list("id", flat=True)
    )
    if all_address_set_ids:
        address_list_ids.update(
            AddressList.objects.filter(
                assigned_object_type=address_set_ct,
                assigned_object_id__in=all_address_set_ids,
            ).values_list("id", flat=True)
        )
    address_list_object_map = {
        obj.pk: obj for obj in AddressList.objects.filter(id__in=address_list_ids)
    }

    return {
        "assigned_object_id": object_id,
        "address_ids": sorted(address_ids),
        "inherited_address_ids": sorted(inherited_address_ids),
        "address_objects": list(
            Address.objects.filter(id__in=address_ids).order_by("name", "pk")
        ),
        "inherited_address_objects": list(
            Address.objects.filter(id__in=inherited_address_ids).order_by("name", "pk")
        ),
        "direct_address_set_ids": sorted(direct_address_set_ids),
        "all_address_set_ids": sorted(all_address_set_ids),
        "address_set_paths": [list(path) for path in unique_addressset_paths],
        "address_set_object_paths": [
            [address_set_object_map.get(address_set_id) for address_set_id in path]
            for path in unique_addressset_paths
        ],
        "address_set_hierarchy_rows": [
            {
                "path": [
                    address_set_object_map.get(address_set_id)
                    for address_set_id in path
                ],
                "address": address_object_map.get(address_id),
            }
            for path, address_id in sorted_hierarchy_rows
        ],
        "address_set_name_paths": [
            [
                (
                    address_set_object_map.get(address_set_id).name
                    if address_set_object_map.get(address_set_id)
                    else str(address_set_id)
                )
                for address_set_id in path
            ]
            for path in unique_addressset_paths
        ],
        "address_list_ids": sorted(address_list_ids),
        "address_list_objects": [
            address_list_object_map[address_list_id]
            for address_list_id in sorted(address_list_ids)
            if address_list_id in address_list_object_map
        ],
        "address_list_names": [
            address_list_object_map[address_list_id].name
            for address_list_id in sorted(address_list_ids)
            if address_list_id in address_list_object_map
        ],
        "policy_paths": [],
    }
