"""Security tab visibility based on ``nsm_object_link`` Object A/B eligibility."""

from __future__ import annotations

from functools import lru_cache

from django.contrib.contenttypes.models import ContentType

__all__ = (
    "clear_object_link_eligibility_cache",
    "get_object_link_allowed_content_type_ids",
    "is_security_tab_eligible",
)


def _field_related_content_type_ids(field) -> set[int]:
    ids: set[int] = set()
    related = getattr(field, "related_object_type", None)
    if related is not None and getattr(related, "pk", None):
        ids.add(related.pk)
    try:
        for ct in field.related_object_types.all():
            if getattr(ct, "pk", None):
                ids.add(ct.pk)
    except Exception:
        pass
    return ids


@lru_cache(maxsize=1)
def get_object_link_allowed_content_type_ids() -> tuple[frozenset[int], frozenset[int]]:
    """Return ``(host_ct_ids, security_ct_ids)`` from the deployed link-table schema."""
    from netbox_nsm.security.links.cot_link_schema import (
        get_object_link_schema,
        object_fields_for_cot,
    )

    schema = get_object_link_schema()
    if schema is None:
        return frozenset(), frozenset()

    host_ids: set[int] = set()
    security_ids: set[int] = set()
    for field in object_fields_for_cot(schema.cot):
        ct_ids = _field_related_content_type_ids(field)
        if field.name == schema.host_field:
            host_ids.update(ct_ids)
        elif field.name == schema.security_field:
            security_ids.update(ct_ids)
    return frozenset(host_ids), frozenset(security_ids)


def clear_object_link_eligibility_cache() -> None:
    get_object_link_allowed_content_type_ids.cache_clear()


def is_security_tab_eligible(obj) -> bool:
    """True when *obj* can appear as Object A or Object B on ``nsm_object_link``."""
    if obj is None:
        return False
    try:
        ct = ContentType.objects.get_for_model(obj)
    except Exception:
        return False
    host_ids, security_ids = get_object_link_allowed_content_type_ids()
    if not host_ids and not security_ids:
        return False
    return ct.pk in host_ids or ct.pk in security_ids
