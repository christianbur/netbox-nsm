"""Column key helpers for COT rulebook rules grids."""

from __future__ import annotations

__all__ = ("parse_rules_column_key",)


def parse_rules_column_key(column_key: str) -> tuple[str, str]:
    """Split ``{field_slug}::{type_key}`` (e.g. ``source::ct_12``)."""
    area_slug, type_key = column_key.split("::", 1)
    return area_slug, type_key
