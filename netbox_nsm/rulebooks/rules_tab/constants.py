from __future__ import annotations

RULES_HTML_ROW_LIMIT = 25
RULES_FILTER_PREFIX = "f_"
RULES_CELL_MODE_QUERY_PARAM = "cell_mode"
RULES_COLUMN_MODE_QUERY_PARAM = "col_mode"
COLUMN_MODE_EXPANDED = "expanded"
COLUMN_MODE_COLLAPSED = "collapsed"
COLUMN_MODE_DEFAULT = COLUMN_MODE_COLLAPSED
COLUMN_MODES = frozenset({COLUMN_MODE_EXPANDED, COLUMN_MODE_COLLAPSED})
RULES_DEFAULT_SORT = ("index", "asc")
RULES_SYSTEM_FIELDS = frozenset({"rulebook", "index", "name", "enabled", "description"})
