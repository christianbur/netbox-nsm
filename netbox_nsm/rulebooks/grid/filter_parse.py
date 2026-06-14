from __future__ import annotations

import re

from netbox_nsm.rulebooks.grid.constants import (
    BARE_NAME_FILTER_SHORTHAND,
    RULES_FILTER_QUERY_MAX_CONDITIONS,
    SCOPED_FILTER_FORMAT_ERROR,
    VIEW_DIRECTIVE_MULTIPLE_ERROR,
    _RULES_FILTER_QUERY_OPS,
    _VIEW_DIRECTIVE_PART_RE,
)
from netbox_nsm.rulebooks.grid.filter_mapping import build_filter_column_aliases
from netbox_nsm.rulebooks.grid.filter_serialize import (
    _format_shorthand_value,
    _unquote_filter_value,
)

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
