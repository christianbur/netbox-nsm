"""ObjectGroups for Enterprise TrustSec demo (group rules by source zone tier)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.models import ObjectGroup, ObjectGroupMember

__all__ = (
    "TRUSTSEC_SOURCE_GROUP_DEFS",
    "ensure_trustsec_source_object_groups",
)

TRUSTSEC_SOURCE_GROUP_DEFS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("TS · Production", "#1565c0", ("prod",)),
    (
        "TS · Integration",
        "#2e7d32",
        ("integration-1", "integration-2", "integration-3"),
    ),
    ("TS · Development", "#e64a19", ("dev-1", "dev-2", "dev-3")),
    ("TS · Test", "#6a1b9a", ("test-1", "test-2", "test-3")),
)


def ensure_trustsec_source_object_groups(
    *,
    zones_by_name: dict,
    zone_content_type: ContentType,
) -> dict[str, ObjectGroup]:
    """
    Create/update source-tier ObjectGroups and attach zone members.

    Returns mapping zone name → ObjectGroup for zones that were assigned.
    """
    zone_to_group: dict[str, ObjectGroup] = {}

    for group_name, color, zone_names in TRUSTSEC_SOURCE_GROUP_DEFS:
        group, _ = ObjectGroup.objects.update_or_create(
            name=group_name,
            defaults={
                "color": color,
                "field_slugs": ["source"],
            },
        )
        if group.color != color or group.field_slugs != ["source"]:
            group.color = color
            group.field_slugs = ["source"]
            group.save(update_fields=["color", "field_slugs"])

        for zone_name in zone_names:
            zone = zones_by_name.get(zone_name)
            if zone is None:
                continue
            ObjectGroupMember.objects.get_or_create(
                group=group,
                content_type=zone_content_type,
                object_id=zone.pk,
            )
            zone_to_group[zone_name] = group

    return zone_to_group
