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
    field_path = WORD | WORD "." WORD
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
    conditions: List[Condition]
    raw: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.parse_error is None

    @property
    def is_empty(self) -> bool:
        return len(self.conditions) == 0

    @property
    def is_active(self) -> bool:
        return self.is_valid and not self.is_empty

    def to_string(self) -> str:
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


def parse(raw: str) -> Query:
    """Parse a query string into a Query object."""
    raw_stripped = (raw or "").strip()
    if not raw_stripped:
        return Query(conditions=[], raw=raw_stripped)

    # Normalize && → AND, normalize whitespace around AND
    text = raw_stripped
    text = re.sub(r"\s*&&\s*", " AND ", text)
    # Split by AND (case-insensitive, must be surrounded by whitespace)
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
                raw=raw_stripped,
                parse_error=f"Cannot parse: {part!r}",
            )
        conditions.append(cond)

    return Query(conditions=conditions, raw=raw_stripped)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FIELD_RE = r"[\w\-]+"  # allow hyphens in field names too


def _parse_condition(text: str) -> Optional[Condition]:
    """Parse a single condition clause."""
    text = text.strip()

    # exists / !exists  (no value)
    m = re.fullmatch(
        rf"({_FIELD_RE}(?:\.{_FIELD_RE})?)\s+(!exists|exists)",
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
        rf"({_FIELD_RE}(?:\.{_FIELD_RE})?)\s+(in|notin)\s+\(([^)]*)\)",
        text,
        re.IGNORECASE,
    )
    if m:
        field, sub_field = _split_field(m.group(1))
        values = [v.strip() for v in m.group(3).split(",") if v.strip()]
        return Condition(
            field=field,
            sub_field=sub_field,
            operator=m.group(2).lower(),
            value=values,
        )

    # = | == | != | contains  with a value (remainder of string)
    m = re.match(
        rf"^({_FIELD_RE}(?:\.{_FIELD_RE})?)\s*(!=|==|=|contains)\s*(.+)$",
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
