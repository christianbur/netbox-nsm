"""Rulebook parent/child hierarchy helpers."""

from __future__ import annotations

from django.utils.html import format_html
from django.utils.safestring import mark_safe

__all__ = (
    "collect_descendant_pks",
    "cot_rulebook_tree_order",
    "hierarchy_depth",
    "invalid_parent_pks",
    "rulebook_list_depth",
    "render_hierarchy_marker",
    "rulebook_tree_order",
    "validate_parent_choice",
)


def hierarchy_depth(rulebook, *, _cache: dict | None = None) -> int:
    """Number of ancestors (0 = root)."""
    if rulebook is None:
        return 0
    if _cache is not None and rulebook.pk in _cache:
        return _cache[rulebook.pk]

    depth = 0
    seen: set[int] = set()
    node = rulebook.parent
    while node is not None and node.pk not in seen:
        seen.add(node.pk)
        depth += 1
        node = node.parent

    if _cache is not None:
        _cache[rulebook.pk] = depth
    return depth


def collect_descendant_pks(rulebook) -> set[int]:
    """All descendant rulebook PKs (not including self)."""
    if rulebook is None or not rulebook.pk:
        return set()
    seen: set[int] = set()
    stack = list(
        rulebook.__class__.objects.filter(parent_id=rulebook.pk).values_list(
            "pk", flat=True
        )
    )
    while stack:
        pk = stack.pop()
        if pk in seen:
            continue
        seen.add(pk)
        stack.extend(
            rulebook.__class__.objects.filter(parent_id=pk).values_list("pk", flat=True)
        )
    return seen


def invalid_parent_pks(rulebook) -> set[int]:
    """PKs that must not be selectable as parent (self and descendants)."""
    if rulebook is None or not rulebook.pk:
        return set()
    return {rulebook.pk} | collect_descendant_pks(rulebook)


def validate_parent_choice(rulebook, parent) -> str | None:
    """Return an error message if parent is invalid, else None."""
    if parent is None:
        return None
    if rulebook is not None and rulebook.pk and parent.pk == rulebook.pk:
        return "A rulebook cannot be its own parent."
    if (
        rulebook is not None
        and rulebook.pk
        and parent.pk in collect_descendant_pks(rulebook)
    ):
        return "Parent cannot be a descendant of this rulebook (cycle)."
    node = parent
    seen: set[int] = set()
    while node is not None:
        if node.pk in seen:
            return "Invalid parent chain (cycle)."
        seen.add(node.pk)
        node = node.parent
    return None


def rulebook_list_depth(rulebook) -> int:
    """Depth for the rulebook list (uses cache, parent walk, or parent_id fallback)."""
    if rulebook is None:
        return 0
    cached = getattr(rulebook, "nsm_list_depth", None)
    if cached is not None:
        return cached
    depth = hierarchy_depth(rulebook)
    if depth == 0 and getattr(rulebook, "parent_id", None):
        return 1
    return depth


def render_hierarchy_marker(depth: int) -> str:
    """
    Visual depth marker for the rulebook list (NetBox prefix list style).

    One bullet per hierarchy level (child = one dot, grandchild = two, …).
    """
    if depth <= 0:
        return ""

    dots = mark_safe("".join("<span>•</span>" for _ in range(depth)))
    return format_html(
        '<div class="record-depth" aria-hidden="true">{}</div>',
        dots,
    )


def rulebook_tree_order(rulebooks) -> list[int]:
    """Depth-first PK order: parent before children, siblings by name."""
    from collections import defaultdict

    by_parent: dict[int | None, list] = defaultdict(list)
    for rb in rulebooks:
        parent_id = getattr(rb, "parent_id", None)
        if parent_id is None and getattr(rb, "parent", None) is not None:
            parent_id = rb.parent.pk
        by_parent[parent_id].append(rb)
    for children in by_parent.values():
        children.sort(key=lambda r: (r.name or "").lower())

    ordered: list[int] = []

    def walk(parent_id: int | None) -> None:
        for rb in by_parent.get(parent_id, []):
            ordered.append(rb.pk)
            walk(rb.pk)

    walk(None)
    known = {rb.pk for rb in rulebooks}
    for rb in sorted(rulebooks, key=lambda r: (r.name or "").lower()):
        if rb.pk not in ordered:
            ordered.append(rb.pk)
    return [pk for pk in ordered if pk in known]


def cot_rulebook_tree_order(rulebooks) -> list:
    """Depth-first order for COT virtual rows (uses ``slug`` / ``parent_slug``)."""
    from collections import defaultdict

    by_parent: dict[str | None, list] = defaultdict(list)
    for rb in rulebooks:
        parent_slug = getattr(rb, "parent_slug", None) or None
        if parent_slug == "":
            parent_slug = None
        if parent_slug is None:
            parent_id = getattr(rb, "parent_id", None)
            if parent_id:
                parent_slug = parent_id
            elif getattr(rb, "parent", None) is not None:
                parent_slug = getattr(rb.parent, "slug", None)
        by_parent[parent_slug].append(rb)
    for children in by_parent.values():
        children.sort(key=lambda r: (r.name or "").lower())

    ordered: list = []

    def walk(parent_slug: str | None) -> None:
        for rb in by_parent.get(parent_slug, []):
            ordered.append(rb)
            walk(rb.slug)

    walk(None)
    known = {rb.slug for rb in rulebooks}
    seen = {rb.slug for rb in ordered}
    for rb in sorted(rulebooks, key=lambda r: (r.name or "").lower()):
        if rb.slug not in seen:
            ordered.append(rb)
    return [rb for rb in ordered if rb.slug in known]
