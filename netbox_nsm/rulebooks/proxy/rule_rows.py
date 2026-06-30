"""Proxy operations for rule rows on a COT rulebook (Phase C).

A "rule" is a Custom Object row of a rulebook COT. Adding / editing / deleting
rules reuses the generic NSM custom-object CRUD (``nsm_object_*`` routes);
cloning reuses the rulebook create wizard. This module is the canonical,
firewall-neutral home for those operations so views/templates depend on stable
names rather than reaching into the generic CRUD directly.
"""

from __future__ import annotations

from django.urls import reverse

__all__ = (
    "rule_add_url",
    "rule_edit_url",
    "rule_delete_url",
    "rule_bulk_import_url",
    "rulebook_clone_url",
    "rulebook_clone_initial",
    "can_edit_rules",
)


def rule_add_url(rulebook_slug: str) -> str:
    """URL to add a new rule row to *rulebook_slug*."""
    return reverse(
        "plugins:netbox_nsm:nsm_object_add",
        kwargs={"custom_object_type": rulebook_slug},
    )


def rule_edit_url(rulebook_slug: str, pk: int) -> str:
    """URL to edit rule row *pk* on *rulebook_slug*."""
    return reverse(
        "plugins:netbox_nsm:nsm_object_edit",
        kwargs={"custom_object_type": rulebook_slug, "pk": pk},
    )


def rule_delete_url(rulebook_slug: str, pk: int) -> str:
    """URL to delete rule row *pk* on *rulebook_slug*."""
    return reverse(
        "plugins:netbox_nsm:nsm_object_delete",
        kwargs={"custom_object_type": rulebook_slug, "pk": pk},
    )


def rule_bulk_import_url(rulebook_slug: str) -> str:
    """URL to bulk-import rule rows into *rulebook_slug*."""
    return reverse(
        "plugins:netbox_nsm:nsm_object_bulk_import",
        kwargs={"custom_object_type": rulebook_slug},
    )


def rulebook_clone_url(source_slug: str) -> str:
    """URL to the create wizard pre-seeded to clone *source_slug*."""
    base = reverse("plugins:netbox_nsm:cot_rulebook_add")
    return f"{base}?clone_from={source_slug}"


def rulebook_clone_initial(cot) -> dict:
    """Return create-form initial data for cloning a rulebook COT."""
    from netbox_nsm.rulebooks.create import build_rulebook_clone_form_initial

    return build_rulebook_clone_form_initial(cot)


def can_edit_rules(user, cot) -> bool:
    """True when *user* may add/edit/delete rule rows on *cot*."""
    from netbox_nsm.rulebooks.permissions import can_change_rulebook

    return can_change_rulebook(user, cot)
