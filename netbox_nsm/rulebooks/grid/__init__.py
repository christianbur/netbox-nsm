"""Rules grid serialization: column defs, filter models, row payloads.

Submodules by concern:
  - ``cells`` — status/description cell helpers
  - ``column_defs`` — AG-grid column definitions
  - ``constants`` — shared constants and system column specs
  - ``filter_mapping`` — column id ↔ NSM query path maps
  - ``filter_model`` — AG-grid filter model builders
  - ``filter_parse`` — filter query text parsing and view directives
  - ``filter_serialize`` — filter query shorthand serialization
  - ``layout`` — rules_layout object column extraction
  - ``rows`` — row records, quick filters, server-side row filtering
"""

from netbox_nsm.rulebooks.grid.cells import (
    _description_cell_html,
    _description_line_count,
    enabled_status_labels,
)
from netbox_nsm.rulebooks.grid.column_defs import (
    apply_suppress_movable,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_group_column_def,
)
from netbox_nsm.rulebooks.grid.constants import (
    ALL_RULES_FILTER_QUERY_CANONICAL_EXAMPLE,
    ALL_RULES_FILTER_QUERY_FORMAT,
    BARE_NAME_FILTER_SHORTHAND,
    RULES_FILTER_QUERY_MAX_CONDITIONS,
    SCOPED_FILTER_FORMAT_ERROR,
    SCOPED_FILTER_QUERY_FORMAT,
    VIEW_DIRECTIVE_MULTIPLE_ERROR,
)
from netbox_nsm.rulebooks.grid.filter_mapping import (
    build_filter_column_aliases,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    field_path_to_shorthand,
)
from netbox_nsm.rulebooks.grid.filter_model import (
    build_ag_grid_filter_model,
    build_ag_grid_filter_model_from_column_map,
    build_ag_grid_filter_model_from_query_text,
    filter_spec_to_column_quick_value,
)
from netbox_nsm.rulebooks.grid.filter_parse import (
    count_view_directives,
    format_filter_query_with_view,
    format_scoped_filter_query,
    normalize_filter_query_view,
    parse_grid_filter_query,
    parse_scoped_grid_filter_query,
    parse_view_directive,
    split_top_level,
    validate_view_directive_count,
)
from netbox_nsm.rulebooks.grid.filter_serialize import (
    condition_to_shorthand_filter_clause,
    conditions_to_filter_query,
    serialize_ag_grid_filter_to_nsm_q,
)
from netbox_nsm.rulebooks.grid.rows import (
    _record_field_filter_text,
    apply_ag_grid_row_filter,
    build_column_quick_filter_spec,
    build_rulebook_rules_grid_row,
    rules_row_height_for_object_lines,
)

__all__ = (
    "ALL_RULES_FILTER_QUERY_CANONICAL_EXAMPLE",
    "ALL_RULES_FILTER_QUERY_FORMAT",
    "BARE_NAME_FILTER_SHORTHAND",
    "RULES_FILTER_QUERY_MAX_CONDITIONS",
    "SCOPED_FILTER_FORMAT_ERROR",
    "SCOPED_FILTER_QUERY_FORMAT",
    "VIEW_DIRECTIVE_MULTIPLE_ERROR",
    "_description_cell_html",
    "_description_line_count",
    "_record_field_filter_text",
    "apply_ag_grid_row_filter",
    "apply_suppress_movable",
    "build_ag_grid_filter_model",
    "build_ag_grid_filter_model_from_column_map",
    "build_ag_grid_filter_model_from_query_text",
    "build_column_quick_filter_spec",
    "build_filter_column_aliases",
    "build_filter_column_query_map",
    "build_filter_column_shorthand_names",
    "build_rulebook_rules_grid_column_defs",
    "build_rulebook_rules_grid_row",
    "build_rulebook_rules_group_column_def",
    "condition_to_shorthand_filter_clause",
    "conditions_to_filter_query",
    "count_view_directives",
    "enabled_status_labels",
    "field_path_to_shorthand",
    "filter_spec_to_column_quick_value",
    "format_filter_query_with_view",
    "format_scoped_filter_query",
    "normalize_filter_query_view",
    "parse_grid_filter_query",
    "parse_scoped_grid_filter_query",
    "parse_view_directive",
    "rules_row_height_for_object_lines",
    "serialize_ag_grid_filter_to_nsm_q",
    "split_top_level",
    "validate_view_directive_count",
)
