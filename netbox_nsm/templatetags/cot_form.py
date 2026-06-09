"""Template helpers for NSM Custom Object (rulebook) edit forms."""

from django import template

from netbox_nsm.core.poly_subfield_labels import poly_subfield_short_label
from netbox_nsm.rulebooks.rulebook_groups import (
    resolve_group_name_for_display,
    rulebook_group_heading_parts,
)
from netbox_nsm.rulebooks.templates import is_deployed_rulebook_slug

register = template.Library()


@register.filter(name="poly_m2m_tab_label")
def poly_m2m_tab_label(field_label: str) -> str:
    """Return the type suffix from a polymorphic sub-field label."""
    return poly_subfield_short_label(field_label)


@register.filter(name="is_nsm_rulebook_cot_slug")
def is_nsm_rulebook_cot_slug(slug: str) -> bool:
    """True for deployed rulebook COT slugs (``nsm_rb_<name>``), not templates."""
    return is_deployed_rulebook_slug((slug or "").strip())


@register.filter(name="rulebook_group_title")
def rulebook_group_title(raw_group: str, form) -> str:
    """Resolve sort-key ``group_name`` to a form section title."""
    return resolve_group_name_for_display(raw_group)


@register.simple_tag(name="rulebook_group_heading")
def rulebook_group_heading(raw_group: str, form) -> dict[str, str] | None:
    """Return ``index_prefix`` + ``label`` for a rulebook form section heading."""
    return rulebook_group_heading_parts(raw_group)
