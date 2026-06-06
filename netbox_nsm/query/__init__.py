"""NSM Query Engine — single source of truth for all rule filtering."""

from .parser import parse, Query, Condition, conditions_to_string
from .engine import (
    RulebookContext,
    filter_rules,
    compute_facets,
    build_query_help_sections,
)

__all__ = [
    "parse",
    "Query",
    "Condition",
    "conditions_to_string",
    "RulebookContext",
    "filter_rules",
    "compute_facets",
    "build_query_help_sections",
]
