from __future__ import annotations

from netbox_nsm.rulebooks.rules_tab.constants import (
    COLUMN_MODE_COLLAPSED,
    COLUMN_MODE_DEFAULT,
    COLUMN_MODE_EXPANDED,
    COLUMN_MODES,
    RULES_CELL_MODE_QUERY_PARAM,
    RULES_COLUMN_MODE_QUERY_PARAM,
)
from netbox_nsm.rulebooks.cell_html import (
    CELL_MODE_COMPACT,
    CELL_MODE_DEFAULT,
    CELL_MODE_INLINE,
    CELL_MODE_PILL_MORE,
    normalize_rules_cell_mode,
)

def normalize_rules_column_mode(raw: str | None) -> str:
    """Return supported rules-table column layout mode (expanded or collapsed)."""
    mode = (raw or "").strip().lower()
    if mode in COLUMN_MODES:
        return mode
    return COLUMN_MODE_DEFAULT


def parse_rules_column_mode(request) -> str:
    """Column layout mode from the query string (expanded / collapsed)."""
    return normalize_rules_column_mode(request.GET.get(RULES_COLUMN_MODE_QUERY_PARAM))


def parse_rules_cell_mode(request) -> str:
    """Object-cell display mode from the query string (inline / stack / compact)."""
    return normalize_rules_cell_mode(request.GET.get(RULES_CELL_MODE_QUERY_PARAM))
