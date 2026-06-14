"""Server-rendered Rules tab: badges, columns, filters, sort, HTML cells, COT context."""

from __future__ import annotations

from typing import Any

from netbox_nsm.rulebooks.rules_tab.badge import (
    format_rules_tab_badge,
    rules_tab_badge_for_object,
)
from netbox_nsm.rulebooks.rules_tab.cells import (
    _attach_rules_cells,
    _build_rules_cell_html,
    _inject_rules_cell_context_attrs,
    _render_actions_cell_html,
    _rules_row_is_multiline,
)
from netbox_nsm.rulebooks.rules_tab.column_defs import (
    attach_rules_column_defs_meta,
    build_rules_page_url,
    collapse_rules_column_defs,
    flatten_rules_column_defs,
    prepare_rules_column_defs,
)
from netbox_nsm.rulebooks.rules_tab.constants import (
    COLUMN_MODE_COLLAPSED,
    COLUMN_MODE_DEFAULT,
    COLUMN_MODE_EXPANDED,
    COLUMN_MODES,
    RULES_CELL_MODE_QUERY_PARAM,
    RULES_COLUMN_MODE_QUERY_PARAM,
    RULES_DEFAULT_SORT,
    RULES_FILTER_PREFIX,
    RULES_HTML_ROW_LIMIT,
    RULES_SYSTEM_FIELDS,
)
from netbox_nsm.rulebooks.rules_tab.filter_params import (
    _rules_param_token,
    _sync_column_filter_values_from_model,
    parse_rules_filter_model,
)
from netbox_nsm.rulebooks.rules_tab.filter_resolve import _resolve_rules_filter_model
from netbox_nsm.rulebooks.rules_tab.headers import (
    rules_field_display_label,
    rules_object_column_accessible_label,
    rules_object_column_display_label,
    rules_object_column_header_parts,
)
from netbox_nsm.rulebooks.rules_tab.modes import (
    normalize_rules_column_mode,
    parse_rules_cell_mode,
    parse_rules_column_mode,
)
from netbox_nsm.rulebooks.rules_tab.sort import (
    _annotate_rules_columns,
    _rules_clamp_page,
    _rules_filter_needs_full_scan,
    _sort_rules_records,
    build_rules_sort_url,
    build_rules_sort_url_for_order,
    parse_rules_sort,
)

_CONTEXT_EXPORTS = frozenset({
    "build_cot_rulebook_rules_tab_context",
    "_cot_rules_page",
    "_cot_rules_row_group_page",
})

__all__ = (
    "COLUMN_MODE_COLLAPSED",
    "COLUMN_MODE_DEFAULT",
    "COLUMN_MODE_EXPANDED",
    "COLUMN_MODES",
    "RULES_CELL_MODE_QUERY_PARAM",
    "RULES_COLUMN_MODE_QUERY_PARAM",
    "RULES_DEFAULT_SORT",
    "RULES_FILTER_PREFIX",
    "RULES_HTML_ROW_LIMIT",
    "RULES_SYSTEM_FIELDS",
    "_annotate_rules_columns",
    "_attach_rules_cells",
    "_build_rules_cell_html",
    "_cot_rules_page",
    "_cot_rules_row_group_page",
    "_inject_rules_cell_context_attrs",
    "_render_actions_cell_html",
    "_resolve_rules_filter_model",
    "_rules_clamp_page",
    "_rules_filter_needs_full_scan",
    "_rules_param_token",
    "_rules_row_is_multiline",
    "_sort_rules_records",
    "_sync_column_filter_values_from_model",
    "attach_rules_column_defs_meta",
    "build_cot_rulebook_rules_tab_context",
    "build_rules_page_url",
    "build_rules_sort_url",
    "build_rules_sort_url_for_order",
    "collapse_rules_column_defs",
    "flatten_rules_column_defs",
    "format_rules_tab_badge",
    "normalize_rules_column_mode",
    "parse_rules_cell_mode",
    "parse_rules_column_mode",
    "parse_rules_filter_model",
    "parse_rules_sort",
    "prepare_rules_column_defs",
    "rules_field_display_label",
    "rules_object_column_accessible_label",
    "rules_object_column_display_label",
    "rules_object_column_header_parts",
    "rules_tab_badge_for_object",
)


def __getattr__(name: str) -> Any:
    """Lazy COT tab context — avoids import cycles with cot_hierarchy / matrix."""
    if name in _CONTEXT_EXPORTS:
        import netbox_nsm.rulebooks.rules_tab.context as context

        return getattr(context, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
