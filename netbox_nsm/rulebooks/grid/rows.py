from __future__ import annotations

from netbox_nsm.rulebooks.grid.cells import (
    _description_line_count,
    _enabled_filter_text,
)
from netbox_nsm.rulebooks.grid.constants import (
    RULES_ROW_CELL_PADDING,
    RULES_ROW_HEIGHT,
    RULES_ROW_ITEM_HEIGHT,
)
from netbox_nsm.rulebooks.grid.filter_parse import split_top_level

def _max_object_items(cells_items: dict) -> int:
    if not cells_items:
        return 1
    return max(max(1, len(items or [])) for items in cells_items.values())


def rules_row_height_for_object_lines(line_count: int) -> int:
    lines = max(1, int(line_count))
    return max(
        RULES_ROW_HEIGHT,
        RULES_ROW_CELL_PADDING + lines * RULES_ROW_ITEM_HEIGHT,
    )


def build_rulebook_rules_grid_row(row: dict) -> dict:
    """Serialize one grouped policy row as rules table record (raw object items)."""
    system = row.get("system") or {}
    record: dict = {
        "pk": row["pk"],
        "_detail_url": system.get("url") or row.get("url") or "",
        "_edit_url": row.get("edit_url") or "",
        "_delete_url": row.get("delete_url") or "",
    }
    enabled = bool(system.get("enabled"))
    record["enabled"] = enabled
    record["enabled__filter"] = _enabled_filter_text(enabled)
    record["name"] = system.get("name") or row.get("name") or ""
    record["index"] = system.get("index", row.get("index"))
    rulebook_name = system.get("rulebook") or row.get("rulebook") or ""
    record["rulebook"] = rulebook_name
    if rulebook_name:
        record["rulebook__filter"] = rulebook_name
    desc_raw = system.get("description") or row.get("description") or ""
    if desc_raw == "-":
        desc_raw = ""
    record["description"] = desc_raw
    if desc_raw:
        record["description__filter"] = desc_raw

    cells_items = row.get("cells_items") or {}
    cells_filter = row.get("cells_filter") or {}
    object_lines = _max_object_items(cells_items)
    desc_lines = _description_line_count(desc_raw)
    line_count = max(object_lines, desc_lines or 0, 1)
    record["_objectLineCount"] = object_lines
    record["_descriptionLineCount"] = desc_lines
    record["_rowHeight"] = rules_row_height_for_object_lines(line_count)
    for key, items in cells_items.items():
        record[key] = items or []
        filter_text = cells_filter.get(key)
        if filter_text:
            record[key + "__filter"] = filter_text
    return record


def _ag_filter_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).lower()


def _record_field_filter_text(record: dict, field: str) -> str:
    if field == "enabled":
        return _ag_filter_text(record.get("enabled__filter") or record.get("enabled"))
    filter_key = f"{field}__filter"
    if filter_key in record:
        return _ag_filter_text(record[filter_key])
    prefix = f"{field}::"
    merged_parts = [
        _ag_filter_text(record[f"{key}__filter"])
        for key in record
        if isinstance(key, str)
        and key.startswith(prefix)
        and not key.endswith("__filter")
        and f"{key}__filter" in record
    ]
    if merged_parts:
        return " ".join(part for part in merged_parts if part)
    value = record.get(field)
    if isinstance(value, list):
        return " ".join(
            str(item.get("name") or "") for item in value if isinstance(item, dict)
        ).lower()
    return _ag_filter_text(value)


def build_column_quick_filter_spec(raw: str) -> dict:
    """Parse per-column quick-search text into an rules table text filter spec."""
    raw = (raw or "").strip()
    if not raw:
        return {}
    or_segments = split_top_level(raw, "OR")
    and_segments = split_top_level(raw, "AND")
    has_or = len(or_segments) > 1
    has_and = len(and_segments) > 1
    if has_or and has_and:
        return {"filterType": "text", "type": "contains", "filter": raw}
    if has_or:
        return {
            "filterType": "text",
            "operator": "OR",
            "conditions": [
                {"filterType": "text", "type": "contains", "filter": segment.strip()}
                for segment in or_segments
                if segment.strip()
            ],
        }
    if has_and:
        return {
            "filterType": "text",
            "operator": "AND",
            "conditions": [
                {"filterType": "text", "type": "contains", "filter": segment.strip()}
                for segment in and_segments
                if segment.strip()
            ],
        }
    return {"filterType": "text", "type": "contains", "filter": raw}


def _text_filter_matches(text: str, spec: dict) -> bool:
    needle = str(spec.get("filter") or "").strip().lower()
    if not needle:
        return True
    ftype = spec.get("type") or "contains"
    if ftype == "notContains":
        return needle not in text
    if ftype == "equals":
        return text == needle
    if ftype == "notEqual":
        return text != needle
    if ftype == "startsWith":
        return text.startswith(needle)
    if ftype == "endsWith":
        return text.endswith(needle)
    return needle in text


def _filter_spec_matches(record: dict, field: str, spec: dict) -> bool:
    operator = (spec.get("operator") or "").upper()
    conditions = spec.get("conditions") or []
    if operator == "OR" and conditions:
        return any(
            _filter_spec_matches(record, field, cond)
            for cond in conditions
            if isinstance(cond, dict)
        )
    if operator == "AND" and conditions:
        return all(
            _filter_spec_matches(record, field, cond)
            for cond in conditions
            if isinstance(cond, dict)
        )
    text = _record_field_filter_text(record, field)
    return _text_filter_matches(text, spec)


def apply_ag_grid_row_filter(
    records: list[dict], filter_model: dict | None
) -> list[dict]:
    """Apply text filter model server-side for Rules row records."""
    if not filter_model:
        return records
    result = []
    for record in records:
        if all(
            _filter_spec_matches(record, field, spec)
            for field, spec in filter_model.items()
            if isinstance(spec, dict)
        ):
            result.append(record)
    return result
