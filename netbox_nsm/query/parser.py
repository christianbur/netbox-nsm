"""
NSM Query Parser

Parses query strings like:
    Source.Labels = Web
    Source.Labels = Web AND Destination.Labels = Database
    Service.Name in (HTTP, HTTPS)
    Action != Deny
    Owner exists
    Description contains SAP

Grammar:
    query     = condition (AND condition)*
    condition = field_path operator value
              | field_path exists_op
    field_path = WORD | WORD "." WORD | WORD "." WORD "." WORD
    (three-part paths: section.type.property, e.g. source.zones.name)
    operator  = "=" | "!=" | "contains"
    exists_op = "exists" | "!exists"
    in_op     = "in" "(" value_list ")" | "notin" "(" value_list ")"
    value     = literal (unquoted or quoted)
    value_list = literal ("," literal)*
"""

import re
from dataclasses import dataclass, field as dc_field
from typing import Optional, List, Union


@dataclass
class Condition:
    field: str  # e.g. "Source", "Action", "Name"  (x: section)
    type_segment: Optional[str] = (
        None  # e.g. "Zones", "Services"  (y: sub-column / type)
    )
    sub_field: Optional[str] = (
        None  # e.g. "name", "prefix", "port"  (z: object property)
    )
    operator: str = "="  # "=", "!=", "contains", "exists", "!exists", "in", "notin"
    value: Union[str, List[str], None] = None  # None for exists/!exists

    def field_path(self) -> str:
        parts = [self.field]
        if self.type_segment:
            parts.append(self.type_segment)
        if self.sub_field:
            parts.append(self.sub_field)
        return ".".join(parts)

    def to_string(self) -> str:
        field_path = self.field_path()
        if self.operator in ("exists", "!exists"):
            return f"{field_path} {self.operator}"
        if self.operator in ("in", "notin"):
            vals = ", ".join(self.value) if self.value else ""
            return f"{field_path} {self.operator} ({vals})"
        # Always quote the value so spaces/special chars are safe
        val = self.value if self.value is not None else ""
        if not (val.startswith('"') and val.endswith('"')):
            val = f'"{val}"'
        # Use == as canonical equality operator
        op = "==" if self.operator == "=" else self.operator
        return f"{field_path} {op} {val}"


@dataclass
class Query:
    conditions: List[Condition]
    or_groups: List[List[Condition]] = dc_field(default_factory=list)
    raw: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.parse_error is None

    @property
    def is_empty(self) -> bool:
        if self.or_groups:
            return not any(self.or_groups)
        return len(self.conditions) == 0

    @property
    def is_active(self) -> bool:
        return self.is_valid and not self.is_empty

    def to_string(self) -> str:
        if self.or_groups:
            return " OR ".join(
                " AND ".join(c.to_string() for c in group)
                for group in self.or_groups
                if group
            )
        return "\nAND\n".join(c.to_string() for c in self.conditions)

    def add_condition(self, condition: "Condition") -> "Query":
        """Return a new Query with the condition appended (AND)."""
        return Query(
            conditions=self.conditions + [condition],
            raw="",
        )

    def remove_condition_index(self, index: int) -> "Query":
        """Return a new Query with the condition at `index` removed."""
        conds = list(self.conditions)
        if 0 <= index < len(conds):
            conds.pop(index)
        return Query(conditions=conds, raw="")


def _parse_and_group(text: str) -> Query:
    """Parse a single AND-group (no OR) into a Query."""
    text = re.sub(r"\s*&&\s*", " AND ", text.strip())
    parts = re.split(r"(?i)\s+AND\s+", text)

    conditions = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        cond = _parse_condition(part)
        if cond is None:
            return Query(
                conditions=[],
                raw=text,
                parse_error=f"Cannot parse: {part!r}",
            )
        conditions.append(cond)

    return Query(conditions=conditions, raw=text)


def parse(raw: str) -> Query:
    """Parse a query string into a Query object."""
    raw_stripped = (raw or "").strip()
    if not raw_stripped:
        return Query(conditions=[], raw=raw_stripped)

    text = re.sub(r"\s*&&\s*", " AND ", raw_stripped)
    or_parts = re.split(r"(?i)\s+OR\s+", text)

    if len(or_parts) == 1:
        group = _parse_and_group(or_parts[0])
        if group.parse_error:
            return Query(
                conditions=[],
                raw=raw_stripped,
                parse_error=group.parse_error,
            )
        return Query(conditions=group.conditions, raw=raw_stripped)

    or_groups = []
    for part in or_parts:
        part = part.strip()
        if not part:
            continue
        group = _parse_and_group(part)
        if group.parse_error:
            return Query(
                conditions=[],
                raw=raw_stripped,
                parse_error=group.parse_error,
            )
        if group.conditions:
            or_groups.append(group.conditions)

    if not or_groups:
        return Query(conditions=[], raw=raw_stripped)

    return Query(conditions=[], or_groups=or_groups, raw=raw_stripped)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FIELD_RE = r"[\w\-]+"  # allow hyphens in field names too
_FIELD_PATH = rf"{_FIELD_RE}(?:\.{_FIELD_RE}){{0,2}}"


def _parse_condition(text: str) -> Optional[Condition]:
    """Parse a single condition clause."""
    text = text.strip()

    # exists / !exists  (no value)
    m = re.fullmatch(
        rf"({_FIELD_PATH})\s+(!exists|exists)",
        text,
        re.IGNORECASE,
    )
    if m:
        field, type_segment, sub_field = _split_field_path(m.group(1))
        return Condition(
            field=field,
            type_segment=type_segment,
            sub_field=sub_field,
            operator=m.group(2).lower(),
            value=None,
        )

    # in / notin  with parentheses
    m = re.fullmatch(
        rf"({_FIELD_PATH})\s+(in|notin)\s+\(([^)]*)\)",
        text,
        re.IGNORECASE,
    )
    if m:
        field, type_segment, sub_field = _split_field_path(m.group(1))
        values = [v.strip() for v in m.group(3).split(",") if v.strip()]
        return Condition(
            field=field,
            type_segment=type_segment,
            sub_field=sub_field,
            operator=m.group(2).lower(),
            value=values,
        )

    # = | == | != | contains  with a value (remainder of string)
    m = re.match(
        rf"^({_FIELD_PATH})\s*(!=|==|=|contains)\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        field, type_segment, sub_field = _split_field_path(m.group(1))
        op = m.group(2).lower()
        if op == "==":
            op = "="
        value = m.group(3).strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
            value = value[1:-1]
        return Condition(
            field=field,
            type_segment=type_segment,
            sub_field=sub_field,
            operator=op,
            value=value,
        )

    return None


def _split_field_path(field_path: str):
    """Split x, x.z, or x.y.z field paths."""
    parts = field_path.split(".")
    if len(parts) == 1:
        return parts[0], None, None
    if len(parts) == 2:
        return parts[0], None, parts[1]
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    return parts[0], ".".join(parts[1:-1]), parts[-1]


def conditions_to_string(conditions: List[Condition]) -> str:
    """Serialize a list of conditions back to a human-readable query string."""
    return "\nAND\n".join(c.to_string() for c in conditions)


def conditions_to_query_param(conditions: List[Condition]) -> str:
    """Serialize conditions for URL query parameters (single-line AND)."""
    return " AND ".join(c.to_string() for c in conditions)


def parse_condition(text: str) -> Optional[Condition]:
    """Parse a single condition clause."""
    return _parse_condition(text)


def condition_matches(a: Condition, b: Condition) -> bool:
    """Return True if two conditions are equivalent."""
    return (
        a.field.lower() == b.field.lower()
        and (a.type_segment or "").lower() == (b.type_segment or "").lower()
        and (a.sub_field or "").lower() == (b.sub_field or "").lower()
        and a.operator.lower() == b.operator.lower()
        and a.value == b.value
    )


def _query_conditions_list(query: Query) -> List[Condition]:
    """Return a flat list of conditions (AND parts only; OR groups flattened)."""
    if query.or_groups:
        conds: List[Condition] = []
        for group in query.or_groups:
            conds.extend(group)
        return conds
    return list(query.conditions)


def query_has_condition(query: Query, condition_text: str) -> bool:
    """Return True if the query already contains an equivalent condition."""
    cond = parse_condition(condition_text)
    if cond is None or not query.is_active:
        return False
    return any(condition_matches(c, cond) for c in _query_conditions_list(query))


def query_and_condition(query: Query, condition_text: str) -> str:
    """Append a condition with AND; skip duplicates."""
    cond = parse_condition(condition_text)
    if cond is None:
        return query.raw or condition_text
    if not query.is_active:
        return cond.to_string()
    existing = _query_conditions_list(query)
    if any(condition_matches(c, cond) for c in existing):
        return conditions_to_query_param(existing)
    return conditions_to_query_param(existing + [cond])


def query_replace_all(condition_text: str) -> str:
    """Replace the entire active query with a single condition."""
    cond = parse_condition(condition_text)
    if cond is None:
        return condition_text.strip()
    return cond.to_string()


def query_replace_field(query: Query, field: str, condition_text: str) -> str:
    """Replace all conditions for `field` with a new condition; keep others."""
    cond = parse_condition(condition_text)
    if cond is None:
        return query.raw or condition_text
    if not query.is_active:
        return cond.to_string()
    kept = [c for c in query.conditions if c.field.lower() != field.lower()]
    return conditions_to_query_param(kept + [cond])
