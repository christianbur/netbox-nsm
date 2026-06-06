"""Map Rules grid filter models to matrix axis filter queries."""

from __future__ import annotations

__all__ = (
    "ag_grid_col_filter_to_axis_query",
    "extract_matrix_axis_queries",
    "matrix_value_to_column_key",
)

_AG_TEXT_FILTER_TYPES = frozenset({"contains", "equals", "startswith", "endswith"})


def matrix_value_to_column_key(value: str) -> str | None:
    """``col:source::ct_10`` → ``source::ct_10``."""
    value = (value or "").strip()
    if value.startswith("col:"):
        return value[4:]
    return None


def ag_grid_col_filter_to_axis_query(col_filter: dict | None) -> str:
    """Convert an AG Grid column filter to matrix axis OR/AND query text."""
    if not col_filter or not isinstance(col_filter, dict):
        return ""
    nested = col_filter.get("conditions") or []
    if nested:
        join_op = (col_filter.get("operator") or "AND").upper()
        if join_op not in ("AND", "OR"):
            join_op = "AND"
        parts: list[str] = []
        for condition in nested:
            if not isinstance(condition, dict):
                continue
            filter_type = (condition.get("type") or "contains").lower()
            if filter_type not in _AG_TEXT_FILTER_TYPES:
                continue
            raw = condition.get("filter")
            if raw is not None and str(raw).strip():
                parts.append(str(raw).strip())
        if not parts:
            return ""
        if len(parts) == 1:
            return parts[0]
        return f" {join_op} ".join(parts)
    filter_type = (col_filter.get("type") or "contains").lower()
    if filter_type not in _AG_TEXT_FILTER_TYPES:
        return ""
    raw = col_filter.get("filter")
    return str(raw).strip() if raw is not None else ""


def extract_matrix_axis_queries(
    filter_model: dict | None,
    row_matrix_value: str,
    col_matrix_value: str,
) -> tuple[str, str]:
    """Return (src_q, dst_q) for the matrix row/column fields."""
    row_key = matrix_value_to_column_key(row_matrix_value)
    col_key = matrix_value_to_column_key(col_matrix_value)
    src_q = ""
    dst_q = ""
    if filter_model and row_key:
        src_q = ag_grid_col_filter_to_axis_query(filter_model.get(row_key))
    if filter_model and col_key:
        dst_q = ag_grid_col_filter_to_axis_query(filter_model.get(col_key))
    return src_q, dst_q
