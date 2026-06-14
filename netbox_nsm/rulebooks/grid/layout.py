from __future__ import annotations

import re

from netbox_nsm.query.engine import RulebookContext


def _segment_key(value: str) -> str:
    return re.sub(r"[\s\-_.]+", "", (value or "").lower())


def _condition_filter_value(condition) -> str:
    val = condition.value
    if isinstance(val, list):
        val = val[0] if val else ""
    text = str(val or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text


def _ag_text_filter_type(operator: str) -> str:
    if operator in ("=", "=="):
        return "contains"
    if operator == "contains":
        return "contains"
    if operator in ("!=", "notin"):
        return "notContains"
    return "contains"


def _layout_object_columns(rules_layout: list) -> list[dict]:
    columns: list[dict] = []
    for entry in rules_layout or []:
        if entry.get("kind") != "object":
            continue
        group = entry.get("group") or {}
        field_slug = group.get("slug") or entry.get("slug") or ""
        for col in group.get("columns") or []:
            columns.append(
                {
                    "key": col["key"],
                    "label": col.get("label") or "",
                    "area_slug": col.get("area_slug") or field_slug,
                }
            )
    return columns


def _columns_for_condition(condition, columns: list[dict], context: RulebookContext):
    rb_field = context.get_field(condition.field)
    if rb_field is None:
        return []
    field_slug = rb_field.slug
    candidates = [c for c in columns if c["area_slug"] == field_slug]
    if not candidates:
        return []

    if condition.type_segment:
        seg = _segment_key(condition.type_segment)
        typed = [c for c in candidates if _segment_key(c["label"]) == seg]
        if typed:
            return typed

    zones = [c for c in candidates if "zone" in c["label"].lower()]
    return zones or candidates

