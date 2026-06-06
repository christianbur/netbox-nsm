"""Group matrix source rows by NSM ObjectGroup membership."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import ObjectGroup, ObjectGroupMember

__all__ = (
    "UNGROUPED_GROUP_KEY",
    "assign_zones_to_primary_groups",
    "build_source_display_items",
    "matrix_grouping_enabled",
)

UNGROUPED_GROUP_KEY = 0


def matrix_grouping_enabled(request) -> bool:
    """Default on; pass group_src=0 to disable."""
    return request.GET.get("group_src", "1") != "0"


def assign_zones_to_primary_groups(
    zones: list,
    *,
    content_type_id: int | None,
    source_field_slug: str | None,
) -> dict[int, ObjectGroup | None]:
    """Map zone pk → primary ObjectGroup (alphabetically first match)."""
    if not zones or content_type_id is None:
        return {}

    zone_pks = [z.pk for z in zones if getattr(z, "pk", None)]
    if not zone_pks:
        return {}

    by_zone: dict[int, list[ObjectGroup]] = defaultdict(list)
    members = ObjectGroupMember.objects.filter(
        content_type_id=content_type_id,
        object_id__in=zone_pks,
    ).select_related("group")
    slug = (source_field_slug or "").strip()

    for member in members:
        group = member.group
        slugs = group.field_slugs or []
        if slugs and slug and slug not in slugs:
            continue
        by_zone[member.object_id].append(group)

    result: dict[int, ObjectGroup | None] = {}
    for zone in zones:
        candidates = sorted(
            by_zone.get(zone.pk, []),
            key=lambda g: (g.name or "").lower(),
        )
        result[zone.pk] = candidates[0] if candidates else None
    return result


def build_source_display_items(
    zones: list,
    *,
    zone_to_group: dict[int, ObjectGroup | None],
    enabled: bool = True,
    zone_sort_key=None,
) -> list[dict]:
    """
    Flat list of display rows: group header entries followed by zone entries.

    Each item has ``kind`` ``group`` or ``zone`` and ``group_key`` for collapse.
    """
    if not zones:
        return []

    sort_key = zone_sort_key or (lambda z: str(z).lower())

    if not enabled:
        return [
            {
                "kind": "zone",
                "zone": zone,
                "group_key": UNGROUPED_GROUP_KEY,
            }
            for zone in sorted(zones, key=sort_key)
        ]

    buckets: dict[int, list] = defaultdict(list)
    for zone in zones:
        group = zone_to_group.get(zone.pk)
        key = group.pk if group is not None else UNGROUPED_GROUP_KEY
        buckets[key].append((group, zone))

    group_keys = sorted(
        (pk for pk in buckets if pk != UNGROUPED_GROUP_KEY),
        key=lambda pk: (buckets[pk][0][0].name or "").lower(),
    )
    if UNGROUPED_GROUP_KEY in buckets:
        group_keys.append(UNGROUPED_GROUP_KEY)

    items: list[dict] = []
    for gpk in group_keys:
        pairs = buckets[gpk]
        group = pairs[0][0] if gpk != UNGROUPED_GROUP_KEY else None
        zone_list = sorted([zone for _, zone in pairs], key=sort_key)
        items.append({"kind": "group", "group": group, "group_key": gpk})
        for zone in zone_list:
            items.append(
                {
                    "kind": "zone",
                    "zone": zone,
                    "group_key": gpk,
                }
            )
    return items


def group_header_label(group: ObjectGroup | None) -> str:
    if group is None:
        return str(_("Ungrouped"))
    return group.name
