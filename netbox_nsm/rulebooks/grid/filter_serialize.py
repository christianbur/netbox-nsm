from __future__ import annotations

import re

from netbox_nsm.rulebooks.grid.constants import (
    BARE_NAME_FILTER_SHORTHAND,
    _RULES_FILTER_QUERY_OPS,
    _UNQUOTED_VALUE_RE,
)
from netbox_nsm.rulebooks.grid.filter_mapping import (
    build_filter_column_shorthand_names,
    field_path_to_shorthand,
)

def _quote_nsm_query_value(value: str) -> str:
    text = str(value or "").strip()
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _ag_grid_type_to_query_op(ag_type: str) -> str:
    if ag_type in ("notEqual", "notContains"):
        return "!="
    return "="


def _unquote_filter_value(raw: str) -> str:
    text = (raw or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        return text[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return text


def _format_shorthand_value(value: str, operator: str = "=") -> str:
    text = str(value or "").strip()
    formatted = (
        text if _UNQUOTED_VALUE_RE.fullmatch(text) else _quote_nsm_query_value(text)
    )
    if operator == "!=":
        return f"!= {formatted}"
    return formatted


def condition_to_shorthand_filter_clause(condition) -> str:
    """Map one NSM Condition to ``Field(value)`` filter-query syntax."""
    val = _condition_filter_value(condition)
    op = (condition.operator or "=").lower()
    if op not in _RULES_FILTER_QUERY_OPS:
        op = "="
    inner = _format_shorthand_value(val, op)
    if condition.type_segment:
        label = f"{condition.field}.{condition.type_segment}"
    elif condition.sub_field and condition.sub_field.lower() not in ("name",):
        label = f"{condition.field}.{condition.sub_field}"
    else:
        label = condition.field
    return f"{label}({inner})"


def conditions_to_filter_query(conditions) -> str:
    """Serialize NSM conditions to the Rules grid filter-query bar syntax."""
    return " AND ".join(
        condition_to_shorthand_filter_clause(c) for c in (conditions or []) if c
    )


def _ag_filter_condition_to_shorthand(condition: dict) -> str | None:
    raw = condition.get("filter")
    if raw is None or str(raw).strip() == "":
        return None
    value = str(raw).strip()
    op = _ag_grid_type_to_query_op(condition.get("type") or "equals")
    return _format_shorthand_value(value, op)


def _serialize_column_filter_shorthand(
    shorthand_name: str,
    col_filter: dict,
) -> str | None:
    if not col_filter or not shorthand_name:
        return None
    nested = col_filter.get("conditions") or []
    if nested:
        join_op = (col_filter.get("operator") or "AND").upper()
        parts = [
            s for c in nested if (s := _ag_filter_condition_to_shorthand(c)) is not None
        ]
    else:
        join_op = "AND"
        single = _ag_filter_condition_to_shorthand(col_filter)
        parts = [single] if single else []
    if not parts:
        return None
    inner = parts[0] if len(parts) == 1 else f" {join_op} ".join(parts)
    if shorthand_name == BARE_NAME_FILTER_SHORTHAND:
        return f"({inner})"
    return f"{shorthand_name}({inner})"


def _sorted_filter_model_col_ids(
    filter_model: dict,
    *,
    column_order: list[str] | None = None,
) -> list[str]:
    col_ids = list(filter_model.keys())
    if not column_order:
        return sorted(col_ids)
    priority = {col_id: idx for idx, col_id in enumerate(column_order)}
    return sorted(
        col_ids, key=lambda col_id: (priority.get(col_id, len(priority)), col_id)
    )


def serialize_ag_grid_filter_to_nsm_q(
    filter_model: dict | None,
    column_map: dict[str, str],
    *,
    shorthand_names: dict[str, str] | None = None,
    column_order: list[str] | None = None,
) -> str:
    """Serialize rules table filter model to shorthand NSM filter query text."""
    if not filter_model or not column_map:
        return ""
    if shorthand_names is None:
        shorthand_names = build_filter_column_shorthand_names(column_map, [])
    clauses: list[str] = []
    for col_id in _sorted_filter_model_col_ids(filter_model, column_order=column_order):
        field_path = column_map.get(col_id)
        if not field_path:
            continue
        if col_id in shorthand_names:
            shorthand = shorthand_names[col_id]
        else:
            shorthand = field_path_to_shorthand(field_path)
        clause = _serialize_column_filter_shorthand(shorthand, filter_model[col_id])
        if clause:
            clauses.append(clause)
    return " AND ".join(clauses)
