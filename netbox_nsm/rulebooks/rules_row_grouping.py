"""Grouped Rows: group rules by column value with expand/collapse."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.grid_payload import enabled_status_labels
from utilities.paginator import EnhancedPaginator

from .rules_tab_base import _rules_clamp_page

__all__ = (
    "RULE_GROUP_COLUMN_ID",
    "RULES_ROW_GROUP_TAB_QUERY_PARAM",
    "ROW_GROUP_TAB_SUMMARIES_CACHE_TIMEOUT",
    "build_cot_row_group_column_choices",
    "build_rule_group_column_def",
    "build_group_key",
    "build_row_group_column_choices",
    "build_row_group_tab_summaries",
    "build_row_grouped_display_rows",
    "build_system_row_group_tab_summaries_from_queryset",
    "cached_row_group_tab_summaries",
    "filter_queryset_by_system_group_key",
    "filter_rows_by_group_key",
    "find_row_group_column",
    "is_row_groupable_column",
    "paginate_grouped_rule_rows",
    "prepare_row_grouping_columns",
    "prepare_row_grouping_tab_columns",
    "resolve_row_group_tab",
    "resolve_stored_row_group_column_id",
    "row_group_column_display_label",
    "row_group_column_label_for_cot",
    "row_group_sort_applies_to_groups",
    "row_group_tab_summaries_cache_key",
    "system_group_db_field",
    "system_group_key_from_db_value",
)

ROW_GROUP_TAB_SUMMARIES_CACHE_TIMEOUT = 300

RULES_ROW_GROUP_TAB_QUERY_PARAM = "row_group_tab"
RULE_GROUP_COLUMN_ID = "_rule_group"


def _empty_group_label() -> str:
    return str(_("(empty)"))


def is_row_groupable_column(col: dict) -> bool:
    """Columns that may be used as a grouped-rows key (all except actions)."""
    return col.get("kind") in ("system", "object")


def _column_match_ids(col: dict) -> set[str]:
    ids = {
        str(col.get("col_id") or ""),
        str(col.get("key") or ""),
        str(col.get("slug") or ""),
        str(col.get("area_slug") or ""),
    }
    return {value for value in ids if value}


def _parse_row_group_column_id(
    raw: str,
    flat_columns: list,
) -> str | None:
    value = (raw or "").strip()
    if not value:
        return None
    for col in flat_columns:
        if value in _column_match_ids(col) and is_row_groupable_column(col):
            return col.get("col_id") or col.get("key") or value
    return None


def resolve_stored_row_group_column_id(
    stored_col_id: str,
    flat_columns: list,
) -> str | None:
    """Validate a persisted rulebook grouping column against the rules layout."""
    return _parse_row_group_column_id(stored_col_id, flat_columns)


def build_cot_row_group_column_choices(cot) -> list[tuple[str, str]]:
    """Groupable rules columns for a COT rulebook (long display labels)."""
    from netbox_nsm.rulebooks.grid_payload import build_rulebook_rules_grid_column_defs
    from netbox_nsm.rulebooks.rules_layout import build_cot_rules_layout
    from netbox_nsm.rulebooks.rules_tab_base import (
        COLUMN_MODE_EXPANDED,
        attach_rules_column_defs_meta,
        flatten_rules_column_defs,
    )

    layout = build_cot_rules_layout(cot)
    grouped_layout = {**layout, "rows": []}
    column_defs = build_rulebook_rules_grid_column_defs(grouped_layout)["columnDefs"]
    flat_columns = flatten_rules_column_defs(column_defs, column_mode=COLUMN_MODE_EXPANDED)
    attach_rules_column_defs_meta(column_defs, flat_columns)
    return build_row_group_column_choices(flat_columns)


def row_group_column_label_for_cot(cot, column_id: str) -> str:
    if not column_id:
        return ""
    for col_id, label in build_cot_row_group_column_choices(cot):
        if col_id == column_id:
            return label
    return column_id


def build_row_group_column_choices(flat_columns: list[dict]) -> list[tuple[str, str]]:
    """Dropdown choices: empty option plus groupable columns (long labels)."""
    choices: list[tuple[str, str]] = [("", str(_("— none —")))]
    for col in flat_columns:
        if not is_row_groupable_column(col):
            continue
        col_id = col.get("col_id") or col.get("key") or ""
        if not col_id:
            continue
        label = row_group_column_display_label(col)
        choices.append((col_id, label))
    return choices


def row_group_column_display_label(col: dict) -> str:
    """Setting/dropdown label, e.g. ``Source - Zone`` for object columns."""
    if col.get("kind") == "object":
        from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

        type_label = (col.get("header_subtitle") or "").strip()
        group_name = (
            (col.get("field_group") or "").strip()
            or (col.get("group_header") or "").strip()
        )
        if group_name and type_label:
            group = resolve_group_name_for_display(group_name) or group_name
            if group != type_label:
                return f"{group} - {type_label}"
            return group
        header_title = (col.get("header_title") or col.get("label") or "").strip()
        if header_title and type_label and header_title != type_label:
            return f"{header_title} - {type_label}"
    return (
        col.get("display_label")
        or col.get("header_title")
        or col.get("label")
        or col.get("col_id")
        or ""
    )


def build_rule_group_column_def() -> dict:
    label = str(_("Rule-Group"))
    return {
        "kind": "rule_group",
        "col_id": RULE_GROUP_COLUMN_ID,
        "slug": RULE_GROUP_COLUMN_ID,
        "label": label,
        "header_title": label,
        "header_subtitle": "",
        "display_label": label,
        "default_width_px": 280,
        "min_width_px": 160,
        "width_px": 280,
    }


def build_group_key(row: dict, column: dict) -> str:
    """Composite group key; multi-value object cells join as ``a, b``."""
    kind = column.get("kind")
    if kind == "system":
        system = row.get("system") or {}
        slug = column.get("slug") or column.get("col_id")
        if slug == "status":
            labels = enabled_status_labels()
            return labels["on"] if system.get("enabled") else labels["off"]
        if slug == "rulebook":
            return str(
                row.get("rulebook_name") or system.get("rulebook") or ""
            ).strip() or _empty_group_label()
        if slug == "index":
            idx = system.get("index", row.get("index"))
            return "" if idx is None else str(idx)
        if slug == "name":
            return str(system.get("name") or row.get("name") or "").strip() or _empty_group_label()
        if slug == "description":
            desc = system.get("description") or row.get("description") or ""
            if desc == "-":
                desc = ""
            return str(desc).strip() or _empty_group_label()
        return _empty_group_label()

    if kind == "object":
        cells_items = row.get("cells_items") or {}
        names: list[str] = []
        merged_keys = column.get("merged_keys")
        if merged_keys:
            for key in merged_keys:
                for item in cells_items.get(key) or []:
                    name = (item.get("name") or "").strip()
                    if name:
                        names.append(name)
        else:
            key = column.get("key") or column.get("col_id") or ""
            for item in cells_items.get(key) or []:
                name = (item.get("name") or "").strip()
                if name:
                    names.append(name)
        unique = sorted(set(names), key=lambda value: value.lower())
        if not unique:
            return _empty_group_label()
        return ", ".join(unique)

    return _empty_group_label()


def _slugify_group_id(key: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")
    return slug or "empty"


def system_group_db_field(group_column: dict) -> str | None:
    """ORM field name when grouping uses a COT system column, else ``None``."""
    if group_column.get("kind") != "system":
        return None
    slug = group_column.get("slug") or group_column.get("col_id")
    if slug == "status":
        return "status"
    if slug in ("index", "name", "description"):
        return slug
    return None


def system_group_key_from_db_value(slug: str, value) -> str:
    """Map a queryset ``values()`` row to the same key as :func:`build_group_key`."""
    if slug == "status":
        labels = enabled_status_labels()
        return labels["on"] if value else labels["off"]
    if slug == "index":
        return "" if value is None else str(value)
    if slug == "description":
        text = str(value or "").strip()
        if text == "-":
            text = ""
        return text or _empty_group_label()
    if slug == "name":
        return str(value or "").strip() or _empty_group_label()
    return _empty_group_label()


def _summaries_from_group_counts(
    buckets: dict[str, int],
    group_column: dict,
    *,
    sort_field: str,
    sort_order: str,
) -> list[dict]:
    if row_group_sort_applies_to_groups(sort_field, group_column):
        sorted_keys = _sort_group_keys(list(buckets.keys()), sort_order=sort_order)
    else:
        sorted_keys = _sort_group_keys(list(buckets.keys()), sort_order="asc")

    return [
        {
            "group_key": key,
            "group_label": key,
            "group_id": _slugify_group_id(key),
            "rule_count": buckets[key],
        }
        for key in sorted_keys
    ]


def build_system_row_group_tab_summaries_from_queryset(
    qs,
    group_column: dict,
    *,
    sort_field: str = "index",
    sort_order: str = "asc",
) -> list[dict]:
    """Aggregate tab counts in the database for system group columns."""
    db_field = system_group_db_field(group_column)
    if not db_field:
        raise ValueError("group_column is not a DB-aggregatable system column")
    slug = group_column.get("slug") or group_column.get("col_id") or ""

    buckets: dict[str, int] = defaultdict(int)
    for row in qs.values(db_field).annotate(rule_count=Count("pk")):
        key = system_group_key_from_db_value(slug, row[db_field])
        buckets[key] += row["rule_count"]

    return _summaries_from_group_counts(
        buckets,
        group_column,
        sort_field=sort_field,
        sort_order=sort_order,
    )


def filter_queryset_by_system_group_key(qs, group_column: dict, group_key: str | None):
    """Restrict *qs* to rules belonging to one system-column group tab."""
    if not group_key:
        return qs.none()
    db_field = system_group_db_field(group_column)
    if not db_field:
        return qs.none()
    slug = group_column.get("slug") or group_column.get("col_id") or ""
    empty_label = _empty_group_label()

    if slug == "status":
        labels = enabled_status_labels()
        if group_key == labels["on"]:
            return qs.filter(status=True)
        if group_key == labels["off"]:
            return qs.filter(status=False)
        return qs.none()

    if group_key == empty_label:
        if slug == "index":
            return qs.filter(index__isnull=True)
        if slug == "description":
            return qs.filter(
                Q(description__isnull=True)
                | Q(description="")
                | Q(description="-")
            )
        return qs.filter(Q(**{f"{db_field}__isnull": True}) | Q(**{db_field: ""}))

    if slug == "index":
        if group_key == "":
            return qs.filter(index__isnull=True)
        try:
            return qs.filter(index=int(group_key))
        except (TypeError, ValueError):
            return qs.none()

    return qs.filter(**{db_field: group_key})


def row_group_tab_summaries_cache_key(
    rulebook_slug: str,
    group_col_id: str,
    filter_model: dict,
    sort_field: str,
    sort_order: str,
) -> str:
    payload = json.dumps(filter_model or {}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return (
        f"nsm:row_group_tabs:{rulebook_slug}:{group_col_id}:"
        f"{digest}:{sort_field}:{sort_order}"
    )


def cached_row_group_tab_summaries(
    cache_key: str,
    builder,
) -> list[dict]:
    """Return cached tab summaries or build and store them."""
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    summaries = builder()
    cache.set(cache_key, summaries, ROW_GROUP_TAB_SUMMARIES_CACHE_TIMEOUT)
    return summaries


def build_row_group_tab_summaries(
    rows: list[dict],
    group_column: dict,
    *,
    sort_field: str = "index",
    sort_order: str = "asc",
) -> list[dict]:
    """Distinct group keys with rule counts for tab navigation (no full row build)."""
    buckets: dict[str, int] = defaultdict(int)
    for row in rows:
        buckets[build_group_key(row, group_column)] += 1

    return _summaries_from_group_counts(
        buckets,
        group_column,
        sort_field=sort_field,
        sort_order=sort_order,
    )


def resolve_row_group_tab(
    request,
    tab_summaries: list[dict],
) -> tuple[str | None, str]:
    """Return ``(group_key, group_id)`` for the active tab (defaults to first)."""
    raw = (request.GET.get(RULES_ROW_GROUP_TAB_QUERY_PARAM) or "").strip()
    if raw:
        for tab in tab_summaries:
            if tab["group_id"] == raw:
                return tab["group_key"], tab["group_id"]
    if tab_summaries:
        first = tab_summaries[0]
        return first["group_key"], first["group_id"]
    return None, ""


def filter_rows_by_group_key(
    rows: list[dict],
    group_column: dict,
    group_key: str | None,
) -> list[dict]:
    if not group_key:
        return []
    return [row for row in rows if build_group_key(row, group_column) == group_key]


def find_row_group_column(flat_columns: list, group_col_id: str | None) -> dict | None:
    if not group_col_id:
        return None
    for col in flat_columns:
        if group_col_id in _column_match_ids(col):
            return col
    return None


def row_group_sort_applies_to_groups(sort_field: str, group_column: dict | None) -> bool:
    if not group_column:
        return False
    if group_column.get("kind") == "system":
        slug = group_column.get("slug") or group_column.get("col_id")
        if slug == "status" and sort_field in ("status", "enabled"):
            return True
        return sort_field == slug
    if group_column.get("kind") == "object":
        area = group_column.get("area_slug") or ""
        key = group_column.get("key") or group_column.get("col_id") or ""
        return sort_field in {area, key, group_column.get("col_id")}
    return False


def _sort_group_keys(keys: list[str], *, sort_order: str) -> list[str]:
    reverse = sort_order == "desc"
    return sorted(keys, key=lambda value: value.lower(), reverse=reverse)


def _sort_rules_within_group(rows: list[dict], sort_field: str, sort_order: str) -> None:
    reverse = sort_order == "desc"

    def _key(row: dict):
        system = row.get("system") or {}
        if sort_field == "enabled":
            return (0 if system.get("enabled") else 1, row.get("index") or 0)
        if sort_field == "name":
            return (system.get("name") or row.get("name") or "").lower()
        if sort_field == "description":
            return (system.get("description") or row.get("description") or "").lower()
        if sort_field == "index":
            return row.get("index") or 0
        if sort_field == "rulebook":
            return (row.get("rulebook_name") or "").lower()
        cells_filter = row.get("cells_filter") or {}
        area = sort_field.split("::", 1)[0]
        text = cells_filter.get(sort_field) or cells_filter.get(area) or ""
        return text.lower()

    rows.sort(key=_key, reverse=reverse)


def build_row_grouped_display_rows(
    rows: list[dict],
    group_column: dict,
    *,
    sort_field: str = "index",
    sort_order: str = "asc",
) -> list[dict]:
    """Flat list of group header rows followed by child rule rows (all collapsed)."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = build_group_key(row, group_column)
        buckets[key].append(row)

    if row_group_sort_applies_to_groups(sort_field, group_column):
        sorted_keys = _sort_group_keys(list(buckets.keys()), sort_order=sort_order)
    else:
        sorted_keys = _sort_group_keys(list(buckets.keys()), sort_order="asc")

    display: list[dict] = []
    for key in sorted_keys:
        members = list(buckets[key])
        if not row_group_sort_applies_to_groups(sort_field, group_column):
            _sort_rules_within_group(members, sort_field, sort_order)
        group_id = _slugify_group_id(key)
        display.append(
            {
                "kind": "group",
                "group_key": key,
                "group_label": key,
                "group_id": group_id,
                "rule_count": len(members),
                "rules_group_collapsed": True,
            }
        )
        for member in members:
            child = dict(member)
            child["kind"] = "rule"
            child["parent_group_id"] = group_id
            child["parent_group_label"] = key
            child["rules_group_collapsed"] = True
            display.append(child)
    return display


def paginate_grouped_rule_rows(
    grouped_rows: list[dict],
    *,
    per_page: int,
    page_num: int,
) -> tuple[list[dict], EnhancedPaginator, object]:
    """Paginate top-level group headers; include all child rules for groups on page."""
    group_headers = [row for row in grouped_rows if row.get("kind") == "group"]
    children_by_group: dict[str, list[dict]] = defaultdict(list)
    for row in grouped_rows:
        if row.get("kind") == "rule":
            children_by_group[row.get("parent_group_id") or ""].append(row)

    paginator = EnhancedPaginator(group_headers, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)

    page_rows: list[dict] = []
    for header in page_obj.object_list:
        page_rows.append(header)
        for child in children_by_group.get(header.get("group_id") or "", []):
            page_rows.append(child)
    return page_rows, paginator, page_obj


def _order_grouped_flat_columns(columns: list[dict]) -> list[dict]:
    """Rule-Group first, Index second, actions last."""
    rule_group = [c for c in columns if c.get("col_id") == RULE_GROUP_COLUMN_ID]
    index_cols = [c for c in columns if c.get("col_id") == "index"]
    action_cols = [c for c in columns if c.get("kind") == "actions"]
    rest = [
        c
        for c in columns
        if c not in rule_group and c not in index_cols and c not in action_cols
    ]
    return [*rule_group, *index_cols, *rest, *action_cols]


def _order_grouped_column_defs(column_defs: list[dict]) -> list[dict]:
    """Rule-Group header first, Index second, actions last."""
    rule_group = [c for c in column_defs if c.get("colId") == RULE_GROUP_COLUMN_ID]
    index_cols = [c for c in column_defs if c.get("colId") == "index"]
    action_cols = [c for c in column_defs if c.get("colId") == "_actions"]
    rest = [
        c
        for c in column_defs
        if c not in rule_group and c not in index_cols and c not in action_cols
    ]
    return [*rule_group, *index_cols, *rest, *action_cols]


def _filter_columns_hiding_grouped(
    flat_columns: list[dict],
    column_defs: list[dict],
    group_col_id: str,
) -> tuple[list[dict], list[dict]]:
    visible_flat = [
        col for col in flat_columns if group_col_id not in _column_match_ids(col)
    ]
    visible_defs: list[dict] = []
    for col_def in column_defs or []:
        if col_def.get("colId") == "_actions":
            continue
        children = col_def.get("children")
        if children:
            kept = [
                child
                for child in children
                if group_col_id
                not in {
                    child.get("field") or "",
                    child.get("colId") or "",
                }
            ]
            if not kept:
                continue
            if len(kept) == len(children):
                visible_defs.append(col_def)
            else:
                clone = dict(col_def)
                clone["children"] = kept
                visible_defs.append(clone)
            continue
        col_id = col_def.get("colId") or ""
        field = col_def.get("field") or ""
        if col_id == group_col_id or field == group_col_id:
            continue
        visible_defs.append(col_def)
    return visible_flat, visible_defs


def _assign_column_positions(flat_columns: list[dict]) -> None:
    position = 0
    for col in flat_columns:
        if col.get("col_id") == "_actions":
            continue
        position += 1
        col["col_position"] = position


def prepare_row_grouping_tab_columns(
    flat_columns: list[dict],
    column_defs: list[dict],
    group_col_id: str,
    *,
    group_column: dict | None = None,
) -> tuple[list[dict], list[dict], dict]:
    """Tab-based navigation; grouped column stays visible in the table."""
    if group_column is None:
        group_column = find_row_group_column(flat_columns, group_col_id)
    if group_column is None:
        raise ValueError(f"Unknown row_group_by column: {group_col_id}")

    visible_flat = list(flat_columns)
    visible_defs = list(column_defs or [])
    _assign_column_positions(visible_flat)
    return visible_flat, visible_defs, group_column


def prepare_row_grouping_columns(
    flat_columns: list[dict],
    column_defs: list[dict],
    group_col_id: str,
) -> tuple[list[dict], list[dict], dict]:
    """Hide grouped column; prepend Rule-Group column (Index becomes second)."""
    group_column = find_row_group_column(flat_columns, group_col_id)
    if group_column is None:
        raise ValueError(f"Unknown row_group_by column: {group_col_id}")

    visible_flat, visible_defs = _filter_columns_hiding_grouped(
        flat_columns, column_defs, group_col_id
    )
    rule_group_col = build_rule_group_column_def()
    visible_flat = _order_grouped_flat_columns([rule_group_col, *visible_flat])

    visible_defs = [
        {
            "colId": RULE_GROUP_COLUMN_ID,
            "headerName": rule_group_col["label"],
            "display_label": rule_group_col["label"],
            "header_title": rule_group_col["label"],
            "rules_column_kind": "rule_group",
            "rules_meta": {},
        },
        *visible_defs,
    ]
    visible_defs = _order_grouped_column_defs(visible_defs)
    _assign_column_positions(visible_flat)

    return visible_flat, visible_defs, group_column
