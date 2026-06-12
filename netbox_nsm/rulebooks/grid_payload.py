"""Serialize grouped policy table data and filter models for the Rules tab."""

from __future__ import annotations

import re
from collections import defaultdict

from django.utils.html import escape
from django.utils.translation import gettext as _

from netbox_nsm.core.type_kind import column_is_address
from netbox_nsm.query.engine import RulebookContext
from netbox_nsm.query.parser import Query
from netbox_nsm.rulebooks.cell_html import rules_filter_target_html

# System layout slug -> row field + rules table column options
_SYSTEM_COLUMN_DEFS: dict[str, dict] = {
    "rulebook": {
        "field": "rulebook",
        "cellRenderer": "nameLinkCell",
        "minWidth": 140,
        "width": 160,
    },
    "status": {
        "field": "enabled",
        "cellRenderer": "statusCell",
        "minWidth": 88,
        "width": 108,
    },
    "name": {
        "field": "name",
        "cellRenderer": "nameLinkCell",
        "minWidth": 160,
        "width": 190,
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
    """Translated On/Off labels for rules table status cells."""
    return {"on": _("On"), "off": _("Off")}


def _enabled_filter_text(enabled: bool) -> str:
    """Search tokens for rules table text filter (locale label + DE/EN synonyms)."""
    labels = enabled_status_labels()
    if enabled:
        return f"{labels['on']} on enabled aktiv ein 1"
    return f"{labels['off']} off disabled inaktiv aus 0"


def _description_cell_html(system: dict) -> str:
    desc = system.get("description") or ""
    if desc == "-":
        desc = ""
    if not desc:
        return '<span class="nsm-cell-empty">-</span>'
    parts = re.split(r"\s→\s", desc)
    if len(parts) >= 2:
        lines = "".join(
            rules_filter_target_html(
                f'<span class="nsm-ag-description-part">{escape(part.strip())}</span>',
                part.strip(),
            )
            for part in parts
            if part.strip()
        )
        return f'<div class="nsm-ag-description-lines">{lines}</div>'
    return rules_filter_target_html(
        f'<span class="nsm-ag-description-text">{escape(desc)}</span>',
        desc,
    )


def _description_line_count(desc_raw: str) -> int:
    text = (desc_raw or "").strip()
    if not text or text == "-":
        return 0
    parts = re.split(r"\s→\s", text)
    return len(parts) if len(parts) >= 2 else 1


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


_SYSTEM_FILTER_COLUMNS: dict[str, str] = {
    "name": "name",
    "index": "index",
    "description": "description",
    "status": "enabled",
    "enabled": "enabled",
}


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


def build_filter_column_query_map(
    rules_layout: list,
    context: RulebookContext,
) -> dict[str, str]:
    """Map rules table column ids to NSM query field paths (for filter export)."""
    mapping: dict[str, str] = {
        "index": "Index",
        "name": "Name",
        "description": "Description",
        "enabled": "Status",
    }
    for col in _layout_object_columns(rules_layout):
        rb_field = context.get_field(col["area_slug"])
        if rb_field is None:
            continue
        field_name = rb_field.name
        label = (col.get("label") or "").strip()
        if label:
            mapping[col["key"]] = f"{field_name}.{label}.Name"
        else:
            mapping[col["key"]] = f"{field_name}.Name"
    return mapping


def field_path_to_shorthand(field_path: str) -> str:
    """Short display name for a filter column path (e.g. Source.Zones.Name -> Source.Zones)."""
    if field_path == "Rulebook.Name":
        return "Rulebook"
    if field_path in ("Index", "Name", "Description", "Status"):
        return field_path
    if field_path.endswith(".Name") and field_path.count(".") >= 2:
        return field_path.rsplit(".", 1)[0]
    return field_path


def build_filter_column_shorthand_names(
    column_map: dict[str, str],
    rules_layout: list,
) -> dict[str, str]:
    """Map rules table column ids to shorthand names used in filter query export."""
    del rules_layout  # reserved for future label overrides
    return {
        col_id: field_path_to_shorthand(path) for col_id, path in column_map.items()
    }


def build_filter_column_aliases(
    column_map: dict[str, str],
    rules_layout: list,
) -> dict[str, str]:
    """Map lowercase shorthand tokens to full NSM field paths."""
    aliases: dict[str, str] = {}
    ambiguous: set[str] = set()

    def add(name: str, path: str) -> None:
        key = (name or "").strip().lower()
        if not key or key in ambiguous:
            return
        existing = aliases.get(key)
        if existing is not None and existing != path:
            ambiguous.add(key)
            aliases.pop(key, None)
        elif existing is None:
            aliases[key] = path

    for path in column_map.values():
        add(path, path)
        add(field_path_to_shorthand(path), path)

    for col in _layout_object_columns(rules_layout):
        label = (col.get("label") or "").strip()
        path = column_map.get(col["key"])
        if label and path:
            add(label, path)

    return aliases


RULES_FILTER_QUERY_MAX_CONDITIONS = 10
_RULES_FILTER_QUERY_OPS = frozenset({"=", "!="})
_UNQUOTED_VALUE_RE = re.compile(r"^[\w\-:.]+$")

SCOPED_FILTER_QUERY_FORMAT = '"Rulebook Name": Name(x) AND ...'
ALL_RULES_FILTER_QUERY_FORMAT = (
    'Rulebook("Prod FW" OR Lab) AND (web-server OR db) AND LABEL(prod)'
)
ALL_RULES_FILTER_QUERY_CANONICAL_EXAMPLE = ALL_RULES_FILTER_QUERY_FORMAT
BARE_NAME_FILTER_SHORTHAND = "__bare_name__"
SCOPED_FILTER_FORMAT_ERROR = f"Invalid scoped filter: use {SCOPED_FILTER_QUERY_FORMAT}"


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


def split_top_level(text: str, keyword: str) -> list[str]:
    """Split *text* by *keyword* at parenthesis depth zero."""
    text = text or ""
    kw = keyword.upper()
    kw_len = len(kw)
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
            buf.append(ch)
            i += 1
            continue
        if ch == ")":
            depth -= 1
            buf.append(ch)
            i += 1
            continue
        if depth == 0 and text[i : i + kw_len].upper() == kw:
            before = text[i - 1] if i > 0 else " "
            after = text[i + kw_len] if i + kw_len < len(text) else " "
            if (before.isspace() or before in "(,") and (
                after.isspace() or after in "(,"
            ):
                segment = "".join(buf).strip()
                if segment:
                    parts.append(segment)
                buf = []
                i += kw_len
                continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _strip_matching_outer_parens(text: str) -> str:
    text = (text or "").strip()
    if not text.startswith("("):
        return text
    depth = 0
    for idx, ch in enumerate(text):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and idx == len(text) - 1:
                return text[1:-1].strip()
            if depth == 0:
                break
    return text


def condition_to_filter_query_path(condition) -> str:
    """Map a parsed Condition to the filterColumnMap path string."""
    parts = [condition.field]
    if condition.type_segment:
        parts.append(condition.type_segment)
    if condition.sub_field:
        parts.append(condition.sub_field)
    elif condition.type_segment:
        parts.append("Name")
    return ".".join(parts)


def _expand_in_condition(condition):
    return [condition]


def _validate_filter_query_condition(cond) -> str | None:
    op = (cond.operator or "").lower()
    if op in ("exists", "!exists", "in", "notin", "contains"):
        return f"Unsupported operator {cond.operator!r}; use = or !="
    if op not in _RULES_FILTER_QUERY_OPS:
        return f"Unsupported operator {cond.operator!r}; use = or !="
    return None


def _parse_column_filter_part(
    part: str,
) -> tuple[str | None, str | None, list | None, str | None]:
    """
    Parse one top-level AND segment into a single column filter group.

    Returns (path, join_operator, conditions, error).
    """
    from netbox_nsm.query.parser import parse_condition

    part = (part or "").strip()
    if not part:
        return None, None, None, "Empty filter segment"
    if not part.startswith("("):
        return (
            None,
            None,
            None,
            "Each column filter must be wrapped in parentheses",
        )

    inner = _strip_matching_outer_parens(part)
    if inner == part.strip():
        return (
            None,
            None,
            None,
            "Each column filter must be wrapped in parentheses",
        )

    or_segments = split_top_level(inner, "OR")
    and_segments = split_top_level(inner, "AND")
    has_or = len(or_segments) > 1
    has_and = len(and_segments) > 1

    if has_or and has_and:
        return (
            None,
            None,
            None,
            "Mixed AND/OR in one column; use only OR or only AND per column",
        )

    if has_or:
        segments = or_segments
        join = "OR"
    elif has_and:
        segments = and_segments
        join = "AND"
    else:
        segments = [inner]
        join = "AND"

    conditions = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        cond = parse_condition(segment)
        if cond is None:
            return None, None, None, f"Cannot parse: {segment!r}"
        op_err = _validate_filter_query_condition(cond)
        if op_err:
            return None, None, None, op_err
        conditions.append(cond)

    if not conditions:
        return None, None, None, f"Cannot parse: {part!r}"

    if len(conditions) > RULES_FILTER_QUERY_MAX_CONDITIONS:
        return (
            None,
            None,
            None,
            f"At most {RULES_FILTER_QUERY_MAX_CONDITIONS} conditions per column",
        )

    path = condition_to_filter_query_path(conditions[0])
    for cond in conditions[1:]:
        if condition_to_filter_query_path(cond).lower() != path.lower():
            return (
                None,
                None,
                None,
                f"Conditions in one column group must use the same field ({path})",
            )

    if len(conditions) == 1:
        join = "AND"

    return path, join, conditions, None


def _parse_bare_value_column_part(
    part: str,
    field_path: str,
) -> tuple[str | None, str | None, list | None, str | None]:
    """
    Parse ``(value OR value)`` shorthand without a field prefix.

    Used for the all-rules canonical Name filter: ``(test AND dd AND d)``.
    """
    from netbox_nsm.query.parser import parse_condition

    part = (part or "").strip()
    if not part.startswith("("):
        return None, None, None, "Each column filter must be wrapped in parentheses"

    inner = _strip_matching_outer_parens(part)
    if inner == part.strip():
        return (
            None,
            None,
            None,
            "Each column filter must be wrapped in parentheses",
        )

    or_segments = split_top_level(inner, "OR")
    and_segments = split_top_level(inner, "AND")
    has_or = len(or_segments) > 1
    has_and = len(and_segments) > 1
    if has_or and has_and:
        return (
            None,
            None,
            None,
            "Mixed AND/OR in one column; use only OR or only AND per column",
        )

    if has_or:
        segments = or_segments
        join = "OR"
    elif has_and:
        segments = and_segments
        join = "AND"
    else:
        segments = [inner]
        join = "AND"

    conditions = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        if parse_condition(segment) is not None:
            return None, None, None, f"Cannot parse: {part!r}"
        try:
            op, value = _parse_shorthand_value_token(segment)
        except ValueError:
            return None, None, None, f"Cannot parse: {segment!r}"
        if op not in _RULES_FILTER_QUERY_OPS:
            return None, None, None, f"Unsupported operator {op!r}; use = or !="
        conditions.append(_condition_from_filter_path(field_path, op, value))

    if not conditions:
        return None, None, None, f"Cannot parse: {part!r}"

    if len(conditions) > RULES_FILTER_QUERY_MAX_CONDITIONS:
        return (
            None,
            None,
            None,
            f"At most {RULES_FILTER_QUERY_MAX_CONDITIONS} conditions per column",
        )

    if len(conditions) == 1:
        join = "AND"

    return field_path, join, conditions, None


def _condition_from_filter_path(path: str, operator: str, value: str):
    from netbox_nsm.query.parser import Condition

    parts = path.split(".")
    if len(parts) == 1:
        return Condition(field=parts[0], operator=operator, value=value)
    if len(parts) == 2:
        return Condition(
            field=parts[0], sub_field=parts[1], operator=operator, value=value
        )
    return Condition(
        field=parts[0],
        type_segment=parts[1],
        sub_field=parts[2],
        operator=operator,
        value=value,
    )


def _parse_shorthand_value_token(token: str) -> tuple[str, str]:
    token = (token or "").strip()
    if not token:
        raise ValueError("empty value")
    op = "="
    if token.startswith("!="):
        op = "!="
        token = token[2:].strip()
    elif token.startswith("="):
        token = token[1:].strip()
    return op, _unquote_filter_value(token)


def _parse_shorthand_column_part(
    part: str,
    aliases: dict[str, str],
) -> tuple[str | None, str | None, list | None, str | None]:
    """
    Parse ``Field(value OR value)`` shorthand into a column filter group.

    Returns (path, join_operator, conditions, error).
    """
    part = (part or "").strip()
    open_idx = part.find("(")
    if open_idx <= 0 or not part.endswith(")"):
        return None, None, None, f"Cannot parse filter segment: {part!r}"

    field_key = part[:open_idx].strip()
    inner = part[open_idx + 1 : -1].strip()
    if not field_key:
        return None, None, None, "Missing field name before parentheses"

    path = aliases.get(field_key.lower())
    if not path:
        return None, None, None, f"Unknown field: {field_key}"

    or_segments = split_top_level(inner, "OR")
    and_segments = split_top_level(inner, "AND")
    has_or = len(or_segments) > 1
    has_and = len(and_segments) > 1
    if has_or and has_and:
        return (
            None,
            None,
            None,
            "Mixed AND/OR in one column; use only OR or only AND per column",
        )

    if has_or:
        segments = or_segments
        join = "OR"
    elif has_and:
        segments = and_segments
        join = "AND"
    else:
        segments = [inner]
        join = "AND"

    conditions = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        try:
            op, value = _parse_shorthand_value_token(segment)
        except ValueError:
            return None, None, None, f"Cannot parse: {segment!r}"
        if op not in _RULES_FILTER_QUERY_OPS:
            return None, None, None, f"Unsupported operator {op!r}; use = or !="
        conditions.append(_condition_from_filter_path(path, op, value))

    if not conditions:
        return None, None, None, f"Cannot parse: {part!r}"

    if len(conditions) > RULES_FILTER_QUERY_MAX_CONDITIONS:
        return (
            None,
            None,
            None,
            f"At most {RULES_FILTER_QUERY_MAX_CONDITIONS} conditions per column",
        )

    if len(conditions) == 1:
        join = "AND"

    return path, join, conditions, None


def parse_scoped_grid_filter_query(
    raw: str,
) -> tuple[str | None, str, str | None]:
    """
    Parse optional rulebook scope for the all-rules filter query bar.

    Scoped form (only)::

        "Rulebook Name": Name(x OR y) AND ...

    Unscoped form::

        Name(x OR y) AND ...
    """
    text = (raw or "").strip()
    if not text:
        return None, "", None

    if text.startswith("["):
        return None, text, SCOPED_FILTER_FORMAT_ERROR

    if text.startswith('"'):
        match = re.match(r'^"((?:[^"\\]|\\.)*)"\s*:\s*(.*)$', text, re.DOTALL)
        if not match:
            return None, text, SCOPED_FILTER_FORMAT_ERROR
        rb_name = match.group(1).replace('\\"', '"').replace("\\\\", "\\")
        return rb_name, match.group(2).strip(), None

    return None, text, None


def format_scoped_filter_query(rulebook_name: str | None, filter_query: str) -> str:
    """Serialize filter query text with optional rulebook scope."""
    body = (filter_query or "").strip()
    if not rulebook_name:
        return body
    escaped = str(rulebook_name).replace("\\", "\\\\").replace('"', '\\"')
    if body:
        return f'"{escaped}": {body}'
    return f'"{escaped}":'


_VIEW_DIRECTIVE_PART_RE = re.compile(
    r"^view\s*\(\s*(matrix|group|table)\s*\)\s*$",
    re.IGNORECASE,
)

VIEW_DIRECTIVE_MULTIPLE_ERROR = (
    "Only one view() directive allowed; use view(table), view(group), or view(matrix)"
)


def count_view_directives(raw: str) -> int:
    """Return how many top-level ``view(...)`` clauses appear in *raw*."""
    text = (raw or "").strip()
    if not text:
        return 0
    count = 0
    for part in split_top_level(text, "AND"):
        part = part.strip()
        if part and _VIEW_DIRECTIVE_PART_RE.match(part):
            count += 1
    return count


def validate_view_directive_count(raw: str) -> str | None:
    """Return an error when more than one ``view()`` clause is present."""
    if count_view_directives(raw) > 1:
        return VIEW_DIRECTIVE_MULTIPLE_ERROR
    return None


def parse_view_directive(raw: str) -> tuple[str | None, str, str | None]:
    """
    Extract ``view(matrix)`` / ``view(group)`` / ``view(table)`` from filter text.

    Returns ``(view, filter_without_view, error)`` where *view* is ``matrix``,
    ``group``, ``table``, or ``None`` (implicit flat table — default).

    When multiple ``view()`` clauses are present, the last one wins and all are
    stripped from the returned filter body (silent normalization).
    """
    text = (raw or "").strip()
    if not text:
        return None, "", None

    view_modes: list[str] = []
    filter_parts: list[str] = []
    for part in split_top_level(text, "AND"):
        part = part.strip()
        if not part:
            continue
        match = _VIEW_DIRECTIVE_PART_RE.match(part)
        if match:
            view_modes.append(match.group(1).lower())
            continue
        filter_parts.append(part)

    view = view_modes[-1] if view_modes else None
    filter_without = " AND ".join(filter_parts).strip()
    return view, filter_without, None


def normalize_filter_query_view(raw: str) -> str:
    """Serialize *raw* with at most one ``view()`` clause (last wins)."""
    view, body, _ = parse_view_directive(raw)
    return format_filter_query_with_view(body, view)


def format_filter_query_with_view(filter_body: str, view: str | None) -> str:
    """Append a single view directive to serialized filter query text."""
    _ignored, body, _ = parse_view_directive(filter_body)
    body = (body or "").strip()
    if not view or view.lower() == "table":
        return body
    directive = f"view({view.lower()})"
    if not body:
        return directive
    return f"{body} AND {directive}"


def _merge_column_groups(groups: list[dict]) -> tuple[list[dict] | None, str | None]:
    merged: dict[str, dict] = {}
    for group in groups:
        key = group["path"].lower()
        if key not in merged:
            merged[key] = group
            continue
        existing = merged[key]
        if existing["join"] != group["join"]:
            return None, (
                f"Mixed AND/OR for field {existing['path']}; "
                "use only OR or only AND per column"
            )
        existing["conditions"].extend(group["conditions"])
    for group in merged.values():
        if len(group["conditions"]) > RULES_FILTER_QUERY_MAX_CONDITIONS:
            return (
                None,
                f"At most {RULES_FILTER_QUERY_MAX_CONDITIONS} conditions per column",
            )
    return list(merged.values()), None


def parse_grid_filter_query(
    raw: str,
    *,
    column_map: dict[str, str] | None = None,
    rules_layout: list | None = None,
    extra_aliases: dict[str, str] | None = None,
) -> tuple[list[dict] | None, str | None]:
    """
    Parse filter query text into per-column groups for rules table filter model.

    Top level: AND between columns. Shorthand: ``Name(a OR b)``; legacy verbose
    ``(Name = "a" OR Name = "b")`` is still accepted. All-rules also accepts
    bare Name groups ``(a AND b)``.
    """
    text = (raw or "").strip()
    if not text:
        return [], None

    aliases = (
        build_filter_column_aliases(column_map, rules_layout or [])
        if column_map
        else {}
    )
    if extra_aliases:
        for key, alias_path in extra_aliases.items():
            aliases[(key or "").strip().lower()] = alias_path

    default_name_path = aliases.get("name", "Name")

    column_groups: list[dict] = []
    for part in split_top_level(text, "AND"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("("):
            path, join, conditions, err = _parse_column_filter_part(part)
            if err:
                path, join, conditions, err = _parse_bare_value_column_part(
                    part, default_name_path
                )
        else:
            path, join, conditions, err = _parse_shorthand_column_part(part, aliases)
        if err:
            return None, err
        column_groups.append(
            {
                "path": path,
                "join": join,
                "conditions": conditions,
            }
        )

    return _merge_column_groups(column_groups)


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


def _object_column_def(col: dict) -> dict:
    return {
        "colId": col["key"],
        "field": col["key"],
        "headerName": col["label"],
        "cellRenderer": "objectCell",
        "minWidth": 220,
        "width": 260,
        "cellRendererParams": {
            "maxPills": col.get("max_visible_pills", 5),
            "colored": col.get("show_colored_pills", True),
            "addressColumn": column_is_address(col),
        },
    }


def build_rulebook_rules_group_column_def(*, header_name: str | None = None) -> dict:
    """Pinned Group column for custom grouping in Group view."""
    label = header_name if header_name is not None else str(_("Group"))
    return {
        "colId": "_group",
        "field": "_groupLabel",
        "headerName": label,
        "pinned": "left",
        "lockPosition": "left",
        "cellRenderer": "rulesGroupCell",
        "width": 280,
        "minWidth": 160,
        "maxWidth": 480,
        "sortable": False,
        "filter": False,
        "floatingFilter": False,
        "resizable": True,
        "suppressHeaderMenuButton": True,
        "suppressColumnsToolPanel": True,
        "suppressFiltersToolPanel": True,
        "suppressMovable": True,
        "cellClass": "nsm-rules-group-cell",
    }


def apply_suppress_movable(column_defs: list[dict]) -> list[dict]:
    """Every leaf column must be non-movable or other columns can shift around it."""
    out: list[dict] = []
    for col in column_defs:
        next_col = dict(col)
        children = next_col.get("children")
        if children:
            next_col["children"] = apply_suppress_movable(children)
        else:
            next_col["suppressMovable"] = True
        out.append(next_col)
    return out


def _ensure_description_column_last(column_defs: list[dict]) -> list[dict]:
    """Description follows field config (sort_order 100): last data column before _actions."""
    desc_col = None
    rest: list[dict] = []
    for col in column_defs:
        if col.get("colId") == "description":
            desc_col = col
        else:
            rest.append(col)
    if desc_col is None:
        return column_defs
    insert_at = len(rest)
    for idx, col in enumerate(rest):
        if col.get("colId") == "_actions":
            insert_at = idx
            break
    rest.insert(insert_at, desc_col)
    return rest


def build_rulebook_rules_grid_column_defs(grouped: dict) -> dict:
    """Column definitions only (no row data)."""
    rules_layout = grouped.get("rules_layout") or []
    column_defs: list[dict] = []

    for entry in rules_layout:
        if entry.get("kind") == "system":
            slug = entry["slug"]
            spec = _SYSTEM_COLUMN_DEFS.get(slug)
            if not spec:
                continue
            column_defs.append({"colId": slug, "headerName": entry["label"], **spec})
            continue

        group = entry.get("group") or {}
        children = [_object_column_def(col) for col in (group.get("columns") or [])]
        if not children:
            continue
        column_defs.append(
            {
                "headerName": entry.get("label") or group.get("label") or "",
                "field_label": entry.get("field_label") or group.get("field_label") or "",
                "field_group": entry.get("field_group") or group.get("field_group") or "",
                "is_polymorphic": entry.get("is_polymorphic", group.get("is_polymorphic")),
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
            "floatingFilter": False,
            "suppressHeaderMenuButton": True,
            "suppressColumnsToolPanel": True,
            "suppressFiltersToolPanel": True,
        }
    )
    return {"columnDefs": column_defs}


RULES_ROW_HEIGHT = 42
RULES_ROW_ITEM_HEIGHT = 24
RULES_ROW_CELL_PADDING = 20


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
