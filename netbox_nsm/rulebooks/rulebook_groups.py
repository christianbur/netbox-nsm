"""Rulebook field ``group_name`` display helpers.

NSM never assigns rulebook field groups itself. Values come only from the COT /
portable-schema definition (``CustomObjectTypeField.group_name``).
"""

from __future__ import annotations

import re

__all__ = (
    "parse_rulebook_group_sort_key",
    "resolve_group_name_for_display",
    "rulebook_group_heading_parts",
    "strip_rulebook_group_sort_prefix",
    "apply_schema_yaml_field_groups",
    "apply_portable_schema_field_groups",
    "sync_all_rulebook_cots",
)

_GROUP_SORT_PREFIX_RE = re.compile(r"^[1-9]#\s*", re.IGNORECASE)


def strip_rulebook_group_sort_prefix(raw_group: str | None) -> str:
    """Drop a leading ``N# `` sort prefix (``N`` = 1–9) from *raw_group*."""
    raw = (raw_group or "").strip()
    if not raw:
        return ""
    return _GROUP_SORT_PREFIX_RE.sub("", raw, count=1).strip()


def resolve_group_name_for_display(raw_group: str | None, *, cot=None) -> str:
    """Return the COT ``group_name`` for rules/form display (pass-through)."""
    return (raw_group or "").strip()


def parse_rulebook_group_sort_key(raw_group: str | None) -> tuple[str, str]:
    """Parse ``1# Common`` into ``(\"1\", \"Common\")`` when present in the COT."""
    raw = (raw_group or "").strip()
    match = re.match(r"^(\d+)#\s*(.+)$", raw)
    if match:
        return match.group(1), match.group(2).strip()
    return "", raw


def rulebook_group_heading_parts(
    raw_group: str | None, *, cot=None
) -> dict[str, str] | None:
    """Build rulebook form section heading from the COT field group label."""
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


def apply_portable_schema_field_groups(portable: dict) -> int:
    """Sync rulebook field ``group_name`` rows from an applied portable-schema document."""
    from netbox_custom_objects.models import CustomObjectType

    updated = 0
    for type_def in portable.get("types") or []:
        if not isinstance(type_def, dict):
            continue
        slug = (type_def.get("slug") or type_def.get("name") or "").strip()
        if not slug:
            continue
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is None:
            continue
        updated += apply_schema_yaml_field_groups(
            cot,
            list(type_def.get("fields") or []),
        )
    return updated


def sync_all_rulebook_cots() -> int:
    """Drop legacy ``nsm_setting`` comment YAML on rulebook COTs."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.rulebooks.registry import is_deployed_rulebook_cot
    from netbox_nsm.rulebooks.templates import is_rulebook_template_slug

    cleared = 0
    for cot in CustomObjectType.objects.order_by("slug"):
        if is_rulebook_template_slug(cot.slug) or is_deployed_rulebook_cot(cot):
            if clear_legacy_nsm_setting_comments(cot):
                cleared += 1
    return cleared
