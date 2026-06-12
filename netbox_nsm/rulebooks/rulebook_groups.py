"""Rulebook field ``group_name`` sort keys and display-label resolution."""

from __future__ import annotations

import re

__all__ = (
    "GROUP_ACTIONS",
    "GROUP_COMMON",
    "GROUP_DESTINATION",
    "GROUP_INFOS",
    "GROUP_NOTES",
    "GROUP_SERVICES",
    "GROUP_SOURCE",
    "default_group_name_map",
    "parse_rulebook_group_sort_key",
    "resolve_group_name_for_display",
    "rulebook_field_group_name",
    "rulebook_group_heading_parts",
    "strip_rulebook_group_sort_prefix",
    "apply_schema_yaml_field_groups",
    "sync_all_rulebook_cots",
    "sync_rulebook_field_groups",
)

_GROUP_SORT_PREFIX_RE = re.compile(r"^[1-9]#\s*", re.IGNORECASE)

GROUP_COMMON = "1# Common"
GROUP_SOURCE = "2# Source"
GROUP_DESTINATION = "3# Destination"
GROUP_SERVICES = "4# Services"
GROUP_ACTIONS = "5# Actions"
GROUP_INFOS = "6# Infos"
GROUP_NOTES = "7# Notes"

RULEBOOK_FIELD_GROUPS: dict[str, str] = {
    "index": GROUP_COMMON,
    "status": GROUP_COMMON,
    "name": GROUP_COMMON,
    "source": GROUP_SOURCE,
    "destination": GROUP_DESTINATION,
    "source_zones": GROUP_SOURCE,
    "source_labels": GROUP_SOURCE,
    "source_addresses": GROUP_SOURCE,
    "destination_zones": GROUP_DESTINATION,
    "destination_labels": GROUP_DESTINATION,
    "destination_addresses": GROUP_DESTINATION,
    "services_applications": GROUP_SERVICES,
    "actions": GROUP_ACTIONS,
    "infos": GROUP_INFOS,
    "description": GROUP_NOTES,
}

def rulebook_field_group_name(field_name: str) -> str | None:
    """Return the sort-key ``group_name`` for a bundled rulebook field, if known."""
    return RULEBOOK_FIELD_GROUPS.get(field_name)


def default_group_name_map() -> dict[str, str]:
    """Built-in sort-key → display-label map (identity: show ``N# `` prefix verbatim)."""
    return {
        GROUP_COMMON: GROUP_COMMON,
        GROUP_SOURCE: GROUP_SOURCE,
        GROUP_DESTINATION: GROUP_DESTINATION,
        GROUP_SERVICES: GROUP_SERVICES,
        GROUP_ACTIONS: GROUP_ACTIONS,
        GROUP_INFOS: GROUP_INFOS,
        GROUP_NOTES: GROUP_NOTES,
    }


def strip_rulebook_group_sort_prefix(raw_group: str | None) -> str:
    """Drop a leading ``N# `` sort prefix (``N`` = 1–9) from *raw_group*."""
    raw = (raw_group or "").strip()
    if not raw:
        return ""
    return _GROUP_SORT_PREFIX_RE.sub("", raw, count=1).strip()


def resolve_group_name_for_display(raw_group: str | None, *, cot=None) -> str:
    """Return ``group_name`` for rules/form display (including ``N# `` sort prefix)."""
    key = (raw_group or "").strip()
    if not key:
        return ""
    mapping = default_group_name_map()
    if key in mapping:
        return mapping[key]
    for map_key, value in mapping.items():
        if map_key.lower() == key.lower():
            return value
    return key


def parse_rulebook_group_sort_key(raw_group: str | None) -> tuple[str, str]:
    """Parse ``1# Common`` into ``(\"1\", \"Common\")``."""
    raw = (raw_group or "").strip()
    match = re.match(r"^(\d+)#\s*(.+)$", raw)
    if match:
        return match.group(1), match.group(2).strip()
    return "", raw


def rulebook_group_heading_parts(
    raw_group: str | None, *, cot=None
) -> dict[str, str] | None:
    """Build rulebook form section heading: ``1==`` prefix, label, trailing line."""
    raw = (raw_group or "").strip()
    if not raw:
        return None
    index, fallback_label = parse_rulebook_group_sort_key(raw)
    display = resolve_group_name_for_display(raw, cot=cot)
    label = display if display else fallback_label
    if not label:
        return None
    return {
        "index_prefix": f"{index}==" if index else "",
        "label": label,
    }


def _is_rulebook_cot_slug(slug: str) -> bool:
    from netbox_nsm.rulebooks.templates import (
        is_deployed_rulebook_slug,
        is_rulebook_template_slug,
    )

    slug = (slug or "").strip()
    return bool(slug) and (
        is_deployed_rulebook_slug(slug) or is_rulebook_template_slug(slug)
    )


def clear_legacy_nsm_setting_comments(cot) -> bool:
    """Remove deprecated ``nsm_setting`` YAML from rulebook COT comments."""
    if not _is_rulebook_cot_slug(getattr(cot, "slug", None)):
        return False
    current = (getattr(cot, "comments", None) or "").strip()
    if not current.startswith("nsm_setting:"):
        return False
    cot.comments = ""
    cot.save(update_fields=["comments"])
    return True


def apply_schema_yaml_field_groups(cot, schema_fields: list[dict]) -> int:
    """Apply ``group_name`` only for fields that declare it in schema YAML; clear others."""
    if not _is_rulebook_cot_slug(getattr(cot, "slug", None)):
        return 0
    group_by_name: dict[str, str] = {}
    for field_def in schema_fields or []:
        name = (field_def.get("name") or "").strip()
        if name and "group_name" in field_def:
            group_by_name[name] = (field_def.get("group_name") or "").strip()
    updated = 0
    for field in cot.fields.all():
        if field.name in group_by_name:
            target = group_by_name[field.name]
        else:
            target = ""
        if field.group_name != target:
            field.group_name = target
            field.save(update_fields=["group_name"])
            updated += 1
    clear_legacy_nsm_setting_comments(cot)
    return updated


def sync_rulebook_field_groups(cot) -> int:
    """Apply bundled ``group_name`` sort keys on rulebook **template** COTs only."""
    from netbox_nsm.rulebooks.templates import is_rulebook_template_slug

    slug = getattr(cot, "slug", None)
    if not is_rulebook_template_slug(slug):
        if _is_rulebook_cot_slug(slug):
            return clear_legacy_nsm_setting_comments(cot)
        return 0
    updated = 0
    for field in cot.fields.all():
        target = rulebook_field_group_name(field.name)
        if target is None:
            continue
        if field.group_name != target:
            field.group_name = target
            field.save(update_fields=["group_name"])
            updated += 1
    clear_legacy_nsm_setting_comments(cot)
    return updated


def sync_all_rulebook_cots() -> int:
    """Sync field groups on all rulebook/template COTs and drop legacy comment YAML."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP, RULEBOOK_TEMPLATE_GROUP

    fields_updated = 0
    for cot in CustomObjectType.objects.filter(
        group_name__in=(RULEBOOK_GROUP, RULEBOOK_TEMPLATE_GROUP)
    ).order_by("slug"):
        fields_updated += sync_rulebook_field_groups(cot)
    return fields_updated
