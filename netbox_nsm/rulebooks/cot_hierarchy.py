"""Hierarchy helpers for deployed COT rulebooks (``nsm_rb_*``)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.hierarchy import cot_rulebook_tree_order, hierarchy_depth
from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook, iter_deployed_cot_rulebooks
from netbox_nsm.rulebooks.templates import is_deployed_rulebook_slug
from netbox_nsm.rulebooks.virtual_cot import VirtualCotRulebook, build_virtual_cot_rulebook_row

__all__ = (
    "apply_cot_rulebook_hierarchy",
    "build_cot_rulebook_list_rows",
    "collect_descendant_slugs",
    "deployed_rulebook_parent_choices",
    "get_cot_matrix_tab_enabled",
    "get_cot_parent_slug",
    "get_cot_row_group_by_col_id",
    "invalid_parent_slugs",
    "load_cot_parent_map",
    "validate_cot_parent_slug",
)


def load_cot_parent_map() -> dict[str, str]:
    from netbox_nsm.type_metadata.rulebook import load_rulebook_parent_map

    return load_rulebook_parent_map()


def get_cot_parent_slug(slug: str) -> str:
    from netbox_nsm.type_metadata.rulebook import resolve_rulebook_config_for_slug

    return resolve_rulebook_config_for_slug(slug).get("parent_slug") or ""


def get_cot_matrix_tab_enabled(slug: str) -> bool:
    """Return whether the Matrix tab is enabled; defaults to True."""
    from netbox_nsm.type_metadata.rulebook import resolve_rulebook_config_for_slug

    return resolve_rulebook_config_for_slug(slug)["matrix_tab_enabled"]


def get_cot_row_group_by_col_id(slug: str) -> str:
    """Return configured rules-tab row group column id, or empty string."""
    from netbox_nsm.type_metadata.rulebook import resolve_rulebook_config_for_slug

    return resolve_rulebook_config_for_slug(slug).get("row_group_by_col_id") or ""


def collect_descendant_slugs(slug: str, *, parent_map: dict[str, str] | None = None) -> set[str]:
    """All descendant rulebook slugs (excluding ``slug``)."""
    if not slug:
        return set()
    if parent_map is None:
        parent_map = load_cot_parent_map()

    children_by_parent: dict[str, list[str]] = {}
    for child_slug, parent_slug in parent_map.items():
        children_by_parent.setdefault(parent_slug, []).append(child_slug)

    seen: set[str] = set()
    stack = list(children_by_parent.get(slug, []))
    while stack:
        child = stack.pop()
        if child in seen:
            continue
        seen.add(child)
        stack.extend(children_by_parent.get(child, []))
    return seen


def invalid_parent_slugs(slug: str, *, parent_map: dict[str, str] | None = None) -> set[str]:
    if not slug:
        return set()
    return {slug} | collect_descendant_slugs(slug, parent_map=parent_map)


def validate_cot_parent_slug(
    slug: str | None,
    parent_slug: str | None,
    *,
    parent_map: dict[str, str] | None = None,
) -> str | None:
    """Return an error message if ``parent_slug`` is invalid for ``slug``."""
    parent_slug = (parent_slug or "").strip() or None
    if parent_slug is None:
        return None
    if not is_deployed_rulebook_slug(parent_slug):
        return "Parent must be an existing deployed rulebook."
    if get_deployed_cot_rulebook(parent_slug) is None:
        return "Parent must be an existing deployed rulebook."
    if slug and parent_slug == slug:
        return "A rulebook cannot be its own parent."
    if slug and parent_slug in collect_descendant_slugs(slug, parent_map=parent_map):
        return "Parent cannot be a descendant of this rulebook (cycle)."
    if parent_map is None:
        parent_map = load_cot_parent_map()

    node = parent_slug
    seen: set[str] = set()
    while node:
        if node in seen:
            return "Invalid parent chain (cycle)."
        seen.add(node)
        node = parent_map.get(node) or None
    return None


def deployed_rulebook_parent_choices(*, exclude_slugs: set[str] | None = None) -> list[tuple[str, str]]:
    exclude = exclude_slugs or set()
    choices: list[tuple[str, str]] = [("", str(_("None")))]
    for cot in iter_deployed_cot_rulebooks():
        if cot.slug in exclude:
            continue
        label = cot.verbose_name or cot.name
        choices.append((cot.slug, label))
    return choices


def apply_cot_rulebook_hierarchy(rows: list[VirtualCotRulebook]) -> list[VirtualCotRulebook]:
    """Wire parent links, depth, and tree order on virtual COT rulebook rows."""
    if not rows:
        return rows

    parent_map = load_cot_parent_map()
    rows_by_slug = {row.slug: row for row in rows}

    for row in rows:
        parent_slug = parent_map.get(row.slug, "") or ""
        row.parent_slug = parent_slug
        parent_row = rows_by_slug.get(parent_slug) if parent_slug else None
        row.parent = parent_row
        row.parent_id = parent_slug or None

    depth_cache: dict = {}
    for row in rows:
        row.nsm_list_depth = hierarchy_depth(row, _cache=depth_cache)

    return cot_rulebook_tree_order(rows)


def build_cot_rulebook_list_rows():
    rows = [
        build_virtual_cot_rulebook_row(cot)
        for cot in iter_deployed_cot_rulebooks()
    ]
    return apply_cot_rulebook_hierarchy(rows)


def build_virtual_cot_rulebook_with_hierarchy(
    cot, *, rule_count: int | None = None
) -> VirtualCotRulebook:
    row = build_virtual_cot_rulebook_row(cot, rule_count=rule_count)
    parent_slug = get_cot_parent_slug(cot.slug)
    row.parent_slug = parent_slug
    if parent_slug:
        parent_cot = get_deployed_cot_rulebook(parent_slug)
        row.parent = build_virtual_cot_rulebook_row(parent_cot) if parent_cot else None
        row.parent_id = parent_slug
    else:
        row.parent = None
        row.parent_id = None
    row.nsm_list_depth = hierarchy_depth(row)
    return row
