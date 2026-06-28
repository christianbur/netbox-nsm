"""Reasons a deployed COT rulebook cannot be deleted yet."""

from __future__ import annotations

from django.utils.translation import ngettext, gettext_lazy as _

from netbox_nsm.rulebooks.cot_hierarchy import load_cot_parent_map
from netbox_nsm.rulebooks.registry import cot_rulebook_instance_count, get_deployed_cot_rulebook
from netbox_nsm.objects.object_link_service import iter_enforcement_point_links_for_slug

__all__ = ("deployed_rulebook_delete_blockers",)


def deployed_rulebook_delete_blockers(cot, *, rule_count: int | None = None) -> list[str]:
    """Human-readable blockers; empty list means delete may proceed."""
    if rule_count is None:
        rule_count = cot_rulebook_instance_count(cot)

    blockers: list[str] = []
    if rule_count:
        blockers.append(
            ngettext(
                "This rulebook contains %(count)s rule. Delete all rules first.",
                "This rulebook contains %(count)s rules. Delete all rules first.",
                rule_count,
            )
            % {"count": rule_count}
        )

    parent_map = load_cot_parent_map()
    child_slugs = [
        child_slug
        for child_slug, parent_slug in parent_map.items()
        if parent_slug == cot.slug
    ]
    if child_slugs:
        labels = []
        for child_slug in child_slugs:
            child = get_deployed_cot_rulebook(child_slug)
            labels.append(child.verbose_name if child else child_slug)
        blockers.append(
            _("Child rulebooks must be deleted or reassigned first: %(names)s")
            % {"names": ", ".join(labels)}
        )

    assignment_count = sum(
        1 for _ in iter_enforcement_point_links_for_slug(cot.slug)
    )
    if assignment_count:
        blockers.append(
            ngettext(
                "This rulebook is assigned to %(count)s enforcement target. Remove the assignment first.",
                "This rulebook is assigned to %(count)s enforcement targets. Remove the assignments first.",
                assignment_count,
            )
            % {"count": assignment_count}
        )

    return blockers
