"""
Group / member-of inheritance for NSM ObjectLinks.

Resolves parent containers via:
- ObjectGroup.parent_groups (NSM security groups)
- ObjectGroupMember (NetBox object is member of an ObjectGroup)
- Custom Object ``group`` M2M (member-of: parent objects listing *obj* in ``group``)
"""

from __future__ import annotations

from collections import deque
from typing import Iterator

from netbox_nsm.ipam_inheritance import (
    InheritedNsmLink,
    _linked_dedupe_key,
    _type_config_map,
    direct_nsm_type_keys_for_ipam,
    should_include_inherited_type,
)

__all__ = (
    "MAX_ANCESTOR_CONTAINERS",
    "ancestor_containers_for_group_inheritance",
    "direct_parent_containers",
    "iter_inherited_group_nsm_links",
)

MAX_ANCESTOR_CONTAINERS = 30


def direct_parent_containers(obj) -> list:
    """Immediate parent groups/containers for *obj* (one hop)."""
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.models import ObjectGroup, ObjectGroupMember

    parents: list = []

    if isinstance(obj, ObjectGroup):
        parents.extend(list(obj.parent_groups.all().order_by("name")))
        return parents

    try:
        ct = ContentType.objects.get_for_model(obj)
        for member in ObjectGroupMember.objects.filter(
            content_type=ct, object_id=obj.pk
        ).select_related("group"):
            parents.append(member.group)
    except Exception:
        pass

    group_rel = getattr(obj, "group", None)
    if group_rel is not None and hasattr(group_rel, "all"):
        Model = type(obj)
        try:
            parents.extend(list(Model.objects.filter(group=obj).order_by("name")))
        except Exception:
            pass

    return parents


def ancestor_containers_for_group_inheritance(obj) -> list:
    """
    Transitive parent containers for group-member inheritance (BFS, direct first).
    """
    queue = deque(direct_parent_containers(obj))
    seen: set[tuple] = set()
    result: list = []

    while queue and len(result) < MAX_ANCESTOR_CONTAINERS:
        parent = queue.popleft()
        key = (parent.__class__.__name__, parent.pk)
        if key in seen:
            continue
        seen.add(key)
        result.append(parent)
        for next_parent in direct_parent_containers(parent):
            next_key = (next_parent.__class__.__name__, next_parent.pk)
            if next_key not in seen:
                queue.append(next_parent)

    return result


def iter_inherited_group_nsm_links(obj) -> Iterator[InheritedNsmLink]:
    """
    Yield NSM links inherited from parent groups / member-of containers.

    Only ObjectLinks on ancestor containers with ``propagation=inherit_group``.
    """
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import prefetch_related_objects

    from netbox_nsm.models import ObjectLink

    ancestors = ancestor_containers_for_group_inheritance(obj)
    if not ancestors:
        return

    obj_ct = ContentType.objects.get_for_model(obj)
    tc_map = _type_config_map()
    covered_type_keys = direct_nsm_type_keys_for_ipam(obj, obj_ct)
    seen_dedupe_keys: set[tuple] = set()
    seen_group_type_keys: set[str] = set()

    from netbox_nsm.models.object_link import LinkPropagationChoices

    def _yield_inherited(link, type_key, lct, linked, ancestor, tc):
        if not should_include_inherited_type(
            link,
            type_key,
            covered_type_keys,
            expected_propagation=LinkPropagationChoices.INHERIT_GROUP,
        ):
            return
        dedupe_key = _linked_dedupe_key(linked, type_key)
        if dedupe_key in seen_dedupe_keys:
            return
        seen_dedupe_keys.add(dedupe_key)
        if type_key not in seen_group_type_keys:
            seen_group_type_keys.add(type_key)
            covered_type_keys.add(type_key)
        yield InheritedNsmLink(
            linked=linked,
            linked_ct=lct,
            type_key=type_key,
            ancestor=ancestor,
            tc=tc,
        )

    for ancestor in ancestors:
        container_ct = ContentType.objects.get_for_model(ancestor)
        for direction in ("fwd", "rev"):
            if direction == "fwd":
                qs_inh = list(
                    ObjectLink.objects.filter(
                        object_a_type=container_ct,
                        object_a_id=ancestor.pk,
                        propagation=LinkPropagationChoices.INHERIT_GROUP,
                    ).select_related("object_b_type")
                )
                prefetch_related_objects(qs_inh, "object_b")
            else:
                qs_inh = list(
                    ObjectLink.objects.filter(
                        object_b_type=container_ct,
                        object_b_id=ancestor.pk,
                        propagation=LinkPropagationChoices.INHERIT_GROUP,
                    ).select_related("object_a_type")
                )
                prefetch_related_objects(qs_inh, "object_a")

            for link in qs_inh:
                linked = link.object_b if direction == "fwd" else link.object_a
                if linked is None:
                    continue
                lct = link.object_b_type if direction == "fwd" else link.object_a_type
                type_key = f"{lct.app_label}__{lct.model}"
                tc = tc_map.get(lct.pk)
                yield from _yield_inherited(link, type_key, lct, linked, ancestor, tc)
