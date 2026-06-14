from __future__ import annotations

import re

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
_SYSTEM_FILTER_COLUMNS: dict[str, str] = {
    "name": "name",
    "index": "index",
    "description": "description",
    "status": "enabled",
    "enabled": "enabled",
}
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
_VIEW_DIRECTIVE_PART_RE = re.compile(
    r"^view\s*\(\s*(matrix|group|table)\s*\)\s*$",
    re.IGNORECASE,
)

VIEW_DIRECTIVE_MULTIPLE_ERROR = (
    "Only one view() directive allowed; use view(table), view(group), or view(matrix)"
)
RULES_ROW_HEIGHT = 42
RULES_ROW_ITEM_HEIGHT = 24
RULES_ROW_CELL_PADDING = 20
