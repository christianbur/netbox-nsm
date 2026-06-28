"""Lookup helpers for deployed COT rulebooks (``role: rulebook`` metadata)."""

from __future__ import annotations

__all__ = (
    "cot_rulebook_instance_count",
    "get_deployed_cot_rulebook",
    "is_deployed_rulebook_cot",
    "iter_deployed_cot_rulebooks",
)


def is_deployed_rulebook_cot(cot) -> bool:
    from netbox_nsm.rulebooks.templates import is_rulebook_template_slug
    from netbox_nsm.type_metadata.roles import resolve_role_for_cot

    if cot is None:
        return False
    if is_rulebook_template_slug(getattr(cot, "slug", "") or ""):
        return False
    return resolve_role_for_cot(cot) == "rulebook"


def iter_deployed_cot_rulebooks():
    """Yield ``CustomObjectType`` rows whose metadata role is ``rulebook``."""
    from netbox_custom_objects.models import CustomObjectType

    for cot in CustomObjectType.objects.order_by("name", "slug"):
        if is_deployed_rulebook_cot(cot):
            yield cot


def get_deployed_cot_rulebook(slug: str):
    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is None or not is_deployed_rulebook_cot(cot):
        return None
    return cot


def cot_rulebook_instance_count(cot) -> int:
    try:
        model = cot.get_model()
    except Exception:
        return 0
    return model.objects.count()
