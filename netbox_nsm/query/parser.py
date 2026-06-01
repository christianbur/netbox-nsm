"""
NSM Query Parser

Parses query strings like:
    Source.Labels = Web
    Source.Labels = Web AND Destination.Labels = Database
    Source.zone = prod OR Source.zone = trust
    Service.Name in (HTTP, HTTPS)
    Action != Deny
    Owner exists
    Description contains SAP

Grammar:
    query      = and_group (OR and_group)*
    and_group  = condition (AND condition)*
    condition  = field_path operator value
               | field_path exists_op
    field_path = WORD | WORD "." WORD | WORD "." WORD "." WORD
    operator   = "=" | "!=" | "contains"
    exists_op  = "exists" | "!exists"
    in_op      = "in" "(" value_list ")" | "notin" "(" value_list ")"
    value      = literal (unquoted or quoted)
    value_list = literal ("," literal)*

Precedence: AND binds tighter than OR (standard).
"""

import re
from dataclasses import dataclass, field as dc_field
from typing import Optional, List, Union


@dataclass
class Condition:
    field: str  # e.g. "Source", "Action", "Name"
    sub_field: Optional[str]  # e.g. "Labels", "Name", None
    operator: str  # "=", "!=", "contains", "exists", "!exists", "in", "notin"
    value: Union[str, List[str], None]  # None for exists/!exists

    def to_string(self) -> str:
        field_path = f"{self.field}.{self.sub_field}" if self.sub_field else self.field
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
    conditions: List[Condition]  # first AND-group (backwards compat)
    raw: str = ""
    parse_error: Optional[str] = None
    # OR-groups: each group is a list of AND-conditions.
    # If len(groups) == 1 it is a pure AND-query (default).
    groups: List[List[Condition]] = dc_field(default_factory=list)

    def __post_init__(self):
        # Ensure groups mirrors conditions for single-group queries
        if not self.groups and self.conditions:
            self.groups = [self.conditions]

    @property
    def is_valid(self) -> bool:
        return self.parse_error is None

    @property
    def is_empty(self) -> bool:
        return not any(self.groups)

    @property
    def is_active(self) -> bool:
        return self.is_valid and not self.is_empty

    def to_string(self) -> str:
        or_parts = []
        for group in (self.groups or [self.conditions]):
            or_parts.append(" AND ".join(c.to_string() for c in group))
        return " OR ".join(or_parts)

    def add_condition(self, condition: "Condition") -> "Query":
        """Return a new Query with the condition appended (AND) to the first group."""
        new_conditions = self.conditions + [condition]
        return Query(
            conditions=new_conditions,
            raw="",
            groups=[new_conditions] + (self.groups[1:] if len(self.groups) > 1 else []),
        )

    def remove_condition_index(self, index: int) -> "Query":
        """Return a new Query with the condition at `index` removed from the first group."""
        conds = list(self.conditions)
        if 0 <= index < len(conds):
            conds.pop(index)
        return Query(
            conditions=conds,
            raw="",
            groups=[conds] + (self.groups[1:] if len(self.groups) > 1 else []),
        )


def parse(raw: str) -> Query:
    """Parse a query string into a Query object."""
    raw_stripped = (raw or "").strip()
    if not raw_stripped:
        return Query(conditions=[], raw=raw_stripped, groups=[])

    # Normalize && → AND, || → OR
    text = raw_stripped
    text = re.sub(r"\s*&&\s*", " AND ", text)
    text = re.sub(r"\s*\|\|\s*", " OR ", text)

    # Split by OR first (lowest precedence)
    or_parts = re.split(r"(?i)\s+OR\s+", text)

    groups: List[List[Condition]] = []
    for or_part in or_parts:
        # Within each OR-group, split by AND
        and_parts = re.split(r"(?i)\s+AND\s+", or_part)
        conditions: List[Condition] = []
        for part in and_parts:
            part = part.strip()
            if not part:
                continue
            cond = _parse_condition(part)
            if cond is None:
                return Query(
                    conditions=[],
                    raw=raw_stripped,
                    parse_error=f"Cannot parse: {part!r}",
                    groups=[],
                )
            conditions.append(cond)
        if conditions:
            groups.append(conditions)

    first_group = groups[0] if groups else []
    return Query(conditions=first_group, raw=raw_stripped, groups=groups)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FIELD_RE = r"[\w\-]+"  # allow hyphens in field names too


def _parse_condition(text: str) -> Optional[Condition]:
    """Parse a single condition clause."""
    text = text.strip()

    # field path: x  |  x.y  |  x.y.z  (x=column, y=type-hint, z=object-property)
    _FP_RE = rf"{_FIELD_RE}(?:\.{_FIELD_RE})*"

    # exists / !exists  (no value)
    m = re.fullmatch(
        rf"({_FP_RE})\s+(!exists|exists)",
        text,
        re.IGNORECASE,
    )
    if m:
        field, sub_field = _split_field(m.group(1))
        return Condition(
            field=field, sub_field=sub_field, operator=m.group(2).lower(), value=None
        )

    # in / notin  with parentheses
    m = re.fullmatch(
        rf"({_FP_RE})\s+(in|notin)\s+\(([^)]*)\)",
        text,
        re.IGNORECASE,
    )
    if m:
        field, sub_field = _split_field(m.group(1))
        raw_values = [v.strip() for v in m.group(3).split(",") if v.strip()]
        # Strip surrounding quotes from each value (e.g. "prod" → prod)
        values = [
            v[1:-1] if len(v) >= 2 and v[0] in ('"', "'") and v[0] == v[-1] else v
            for v in raw_values
        ]
        return Condition(
            field=field,
            sub_field=sub_field,
            operator=m.group(2).lower(),
            value=values,
        )

    # = | == | != | contains  with a value (remainder of string)
    m = re.match(
        rf"^({_FP_RE})\s*(!=|==|=|contains)\s*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m:
        field, sub_field = _split_field(m.group(1))
        op = m.group(2).lower()
        if op == "==":
            op = "="
        value = m.group(3).strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] in ('"', "'") and value[0] == value[-1]:
            value = value[1:-1]
        return Condition(field=field, sub_field=sub_field, operator=op, value=value)

    return None


def _split_field(field_path: str):
    """'Source.Labels' → ('Source', 'Labels'),  'Action' → ('Action', None)."""
    if "." in field_path:
        head, tail = field_path.split(".", 1)
        return head, tail
    return field_path, None


def conditions_to_string(conditions: List[Condition]) -> str:
    """Serialize a list of conditions back to a human-readable query string."""
    return "\nAND\n".join(c.to_string() for c in conditions)
