"""Serialize grouped policy table data for AG Grid Community."""

from __future__ import annotations

import re
from collections import defaultdict

from django.utils.html import escape
from django.utils.translation import gettext as _

from netbox_nsm.query.engine import RulebookContext
from netbox_nsm.query.parser import Query

# System layout slug -> row field + AG Grid column options
_SYSTEM_COLUMN_DEFS: dict[str, dict] = {
    "status": {
        "field": "enabled",
        "cellRenderer": "statusCell",
        "minWidth": 88,
        "width": 108,
    },
    "name": {
        "field": "name",
        "cellRenderer": "nameLinkCell",
        "minWidth": 120,
        "width": 140,
    },
    "index": {
        "field": "index",
        "cellRenderer": "indexLinkCell",
        "minWidth": 72,
        "width": 90,
    },
    "description": {
        "field": "description",
        "cellRenderer": "descriptionCell",
        "minWidth": 100,
        "width": 110,
    },
}


def enabled_status_labels() -> dict[str, str]:
    """Translated On/Off labels for AG Grid status cells."""
    return {"on": _("On"), "off": _("Off")}


def _enabled_filter_text(enabled: bool) -> str:
    """Search tokens for AG Grid text filter (locale label + DE/EN synonyms)."""
    labels = enabled_status_labels()
    if enabled:
        return f"{labels['on']} on enabled aktiv ein 1"
    return f"{labels['off']} off disabled inaktiv aus 0"


def _description_cell_html(system: dict) -> str:
    desc = system.get("description") or ""
    if desc == "-":
        desc = ""
    short = desc if len(desc) <= 21 else desc[:21] + "…"
    return f'<span title="{escape(desc)}">{escape(short)}</span>'


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


def _layout_object_columns(policy_layout: list) -> list[dict]:
    columns: list[dict] = []
    for entry in policy_layout or []:
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
        typed = [
            c for c in candidates if _segment_key(c["label"]) == seg
        ]
        if typed:
            return typed

    zones = [c for c in candidates if "zone" in c["label"].lower()]
    return zones or candidates


_SYSTEM_FILTER_COLUMNS: dict[str, str] = {
    "name": "name",
    "index": "index",
    "description": "description",
    "status": "enabled",
    "enabled": "enabled",
}


def build_ag_grid_filter_model(
    query: Query,
    policy_layout: list,
    context: RulebookContext,
) -> dict | None:
    """
    Map nsm_q conditions to AG Grid floating-filter model (text contains).

    OR groups collapse to multi-value OR filters per field/column so matrix
    bidirectional links still show every matching row in the grid.
    """
    if not query.is_active:
        return None

    groups = query.or_groups if query.or_groups else [query.conditions]
    columns = _layout_object_columns(policy_layout)
    if not columns:
        return None

    values_by_field: dict[str, list[str]] = defaultdict(list)
    operators_by_field: dict[str, str] = {}
    sample_condition_by_field: dict[str, object] = {}

    for group in groups:
        for cond in group:
            if cond.operator in ("exists", "!exists", "in", "notin"):
                continue
            rb_field = context.get_field(cond.field)
            if rb_field is not None:
                from netbox_nsm.query.engine import _resolve_object_condition

                cond = _resolve_object_condition(cond, context, rb_field)
            key = cond.field.lower()
            value = _condition_filter_value(cond)
            if not value:
                continue
            if value not in values_by_field[key]:
                values_by_field[key].append(value)
            operators_by_field[key] = cond.operator
            sample_condition_by_field[key] = cond

    filter_model: dict = {}
    for field_key, values in values_by_field.items():
        ag_type = _ag_text_filter_type(operators_by_field[field_key])
        system_col = _SYSTEM_FILTER_COLUMNS.get(field_key)
        if system_col:
            if len(values) == 1:
                filter_model[system_col] = {
                    "filterType": "text",
                    "type": ag_type,
                    "filter": values[0],
                }
            else:
                filter_model[system_col] = {
                    "filterType": "text",
                    "operator": "OR",
                    "conditions": [
                        {
                            "filterType": "text",
                            "type": "contains",
                            "filter": value,
                        }
                        for value in values
                    ],
                }
            continue
        cond = sample_condition_by_field[field_key]
        targets = _columns_for_condition(cond, columns, context)
        if not targets:
            continue
        for col in targets:
            if len(values) == 1:
                filter_model[col["key"]] = {
                    "filterType": "text",
                    "type": ag_type,
                    "filter": values[0],
                }
            else:
                filter_model[col["key"]] = {
                    "filterType": "text",
                    "operator": "OR",
                    "conditions": [
                        {
                            "filterType": "text",
                            "type": "contains",
                            "filter": value,
                        }
                        for value in values
                    ],
                }

    return filter_model or None


def build_policy_ag_grid_payload(grouped: dict) -> dict:
    """
    Build columnDefs + rowData for AG Grid (Community).
    System columns use raw values; custom renderers/editors are applied in JS.
    """
    policy_layout = grouped.get("policy_layout") or []
    rows = grouped.get("rows") or []

    column_defs: list[dict] = []

    for entry in policy_layout:
        if entry.get("kind") == "system":
            slug = entry["slug"]
            spec = _SYSTEM_COLUMN_DEFS.get(slug)
            if not spec:
                continue
            col_def = {
                "colId": slug,
                "headerName": entry["label"],
                **spec,
            }
            column_defs.append(col_def)
            continue

        group = entry.get("group") or {}
        children = []
        for col in group.get("columns") or []:
            children.append(
                {
                    "colId": col["key"],
                    "field": col["key"],
                    "headerName": col["label"],
                    "cellRenderer": "htmlCell",
                    "minWidth": 120,
                    "width": 140,
                }
            )
        if not children:
            continue
        column_defs.append(
            {
                "headerName": (entry.get("label") or group.get("label") or "").upper(),
                "children": children,
            }
        )

    column_defs.append(
        {
            "colId": "_actions",
            "field": "_actions",
            "headerName": "",
            "cellRenderer": "actionsCell",
            "pinned": "right",
            "width": 72,
            "sortable": False,
            "filter": False,
            "suppressHeaderMenuButton": True,
            "suppressColumnsToolPanel": True,
            "suppressFiltersToolPanel": True,
        }
    )

    row_data = []
    for row in rows:
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
        desc_raw = system.get("description") or row.get("description") or ""
        if desc_raw == "-":
            desc_raw = ""
        record["description"] = desc_raw
        if desc_raw:
            record["description__filter"] = desc_raw

        cells = row.get("cells_ag") or row.get("cells") or {}
        cells_filter = row.get("cells_filter") or {}
        for key, html in cells.items():
            if html:
                record[key] = html
            else:
                record[key] = '<span class="nsm-cell-empty">-</span>'
            filter_text = cells_filter.get(key)
            if filter_text:
                record[key + "__filter"] = filter_text
        row_data.append(record)

    return {
        "columnDefs": column_defs,
        "rowData": row_data,
    }
