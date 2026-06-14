from __future__ import annotations

from collections import defaultdict

from netbox_nsm.query.engine import RulebookContext

from netbox_nsm.rulebooks.grid.constants import _SYSTEM_FILTER_COLUMNS
from netbox_nsm.rulebooks.grid.filter_parse import (
    format_filter_query_with_view,
    parse_grid_filter_query,
    parse_view_directive,
)
from netbox_nsm.rulebooks.grid.filter_serialize import (
    _ag_filter_condition_to_shorthand,
    _ag_grid_type_to_query_op,
)
from netbox_nsm.rulebooks.grid.filter_mapping import (
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    field_path_to_shorthand,
)
from netbox_nsm.rulebooks.grid.layout import (
    _ag_text_filter_type,
    _columns_for_condition,
    _condition_filter_value,
    _layout_object_columns,
)

from netbox_nsm.query.parser import Query


def build_ag_grid_filter_model(
    query: Query,
    rules_layout: list,
    context: RulebookContext,
) -> dict | None:
    """
    Map nsm_q conditions to rules table floating-filter model (text contains).

    OR groups collapse to multi-value OR filters per field/column so matrix
    bidirectional links still show every matching row in the grid.
    """
    if not query.is_active:
        return None

    groups = query.or_groups if query.or_groups else [query.conditions]
    columns = _layout_object_columns(rules_layout)
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
def _nsm_operator_to_ag_type(operator: str) -> str:
    op = (operator or "").lower()
    if op == "!=":
        return "notEqual"
    return "equals"


def build_ag_grid_filter_model_from_column_map(
    raw: str,
    column_map: dict[str, str],
    rules_layout: list | None = None,
    extra_aliases: dict[str, str] | None = None,
) -> tuple[dict | None, str | None]:
    """Parse filter query text into an rules table filter model using a column map."""
    _view, filter_body, view_err = parse_view_directive(raw)
    if view_err:
        return None, view_err
    groups, err = parse_grid_filter_query(
        filter_body,
        column_map=column_map,
        rules_layout=rules_layout or [],
        extra_aliases=extra_aliases,
    )
    if err:
        return None, err
    if not groups:
        return {}, None
    path_to_col = {path.lower(): col_id for col_id, path in column_map.items()}
    filter_model: dict = {}

    for group in groups:
        path = group["path"]
        col_id = path_to_col.get(path.lower())
        if not col_id:
            return None, f"Unknown field: {path}"
        conditions = group["conditions"]
        if len(conditions) == 1:
            cond = conditions[0]
            value = _condition_filter_value(cond)
            if not value and cond.operator not in ("exists", "!exists"):
                return None, f"Missing value for: {path}"
            filter_model[col_id] = {
                "filterType": "text",
                "type": _nsm_operator_to_ag_type(cond.operator),
                "filter": value,
            }
            continue
        join = (group.get("join") or "AND").upper()
        filter_model[col_id] = {
            "filterType": "text",
            "operator": join,
            "conditions": [
                {
                    "filterType": "text",
                    "type": _nsm_operator_to_ag_type(cond.operator),
                    "filter": _condition_filter_value(cond),
                }
                for cond in conditions
            ],
        }
    return filter_model or {}, None


def filter_spec_to_column_quick_value(spec: dict | None) -> str:
    """Serialize an rules table filter spec to per-column quick-search text."""
    if not spec:
        return ""
    nested = spec.get("conditions") or []
    if nested:
        join_op = (spec.get("operator") or "AND").upper()
        parts = [
            s
            for cond in nested
            if (s := _ag_filter_condition_to_shorthand(cond)) is not None
        ]
        return f" {join_op} ".join(parts) if parts else ""
    single = _ag_filter_condition_to_shorthand(spec)
    if single is not None:
        return single
    return str(spec.get("filter") or "").strip()


def build_ag_grid_filter_model_from_query_text(
    raw: str,
    rules_layout: list,
    context: RulebookContext,
) -> tuple[dict | None, str | None]:
    """Parse editable filter query text into an rules table filter model."""
    column_map = build_filter_column_query_map(rules_layout, context)
    filter_model, err = build_ag_grid_filter_model_from_column_map(
        raw, column_map, rules_layout
    )
    if not err:
        return filter_model or {}, None

    from netbox_nsm.query.parser import parse as parse_nsm_query

    query = parse_nsm_query(raw)
    if query.parse_error or not query.is_active:
        return None, err
    nsm_model = build_ag_grid_filter_model(query, rules_layout, context)
    return nsm_model or {}, None

