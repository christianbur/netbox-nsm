"""Lookup helpers for deployed COT rulebooks (``nsm_rb_<name>``)."""

from __future__ import annotations

__all__ = (
    "cot_rulebook_instance_count",
    "get_deployed_cot_rulebook",
    "iter_deployed_cot_rulebooks",
)

from netbox_nsm.rulebooks.templates import (
    RULEBOOK_GROUP,
    get_rulebook_template_slugs,
    is_deployed_rulebook_slug,
)


def iter_deployed_cot_rulebooks():
    """Yield ``CustomObjectType`` rows for concrete rulebooks."""
    from netbox_custom_objects.models import CustomObjectType

    qs = (
        CustomObjectType.objects.filter(group_name=RULEBOOK_GROUP)
        .order_by("name", "slug")
    )
    for cot in qs:
        if is_deployed_rulebook_slug(cot.slug):
            yield cot
    # Also include slugs that match the pattern but use a different group_name.
    template_slugs = set(get_rulebook_template_slugs())
    extra = (
        CustomObjectType.objects.filter(slug__startswith="nsm_rb_")
        .exclude(slug__in=template_slugs)
        .exclude(pk__in=qs.values_list("pk", flat=True))
        .order_by("name", "slug")
    )
    yield from extra


def get_deployed_cot_rulebook(slug: str):
    from netbox_custom_objects.models import CustomObjectType

    if not is_deployed_rulebook_slug(slug):
        return None
    return CustomObjectType.objects.filter(slug=slug).first()


def cot_rulebook_instance_count(cot) -> int:
    try:
        model = cot.get_model()
    except Exception:
        return 0
    return model.objects.count()
