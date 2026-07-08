"""Structural discovery for link-table COTs (``link_table`` metadata flag)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from extras.choices import CustomFieldTypeChoices
from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag
from netbox_nsm.type_metadata.config import is_linkable_content_type

__all__ = (
    "ObjectLinkSchema",
    "classify_object_link_field_names",
    "get_object_link_cot",
    "get_object_link_cot_slug",
    "get_object_link_schema",
    "is_link_table_cot",
    "object_fields_for_cot",
    "read_link_endpoints",
)


@dataclass(frozen=True)
class ObjectLinkSchema:
    """Resolved link-table COT with discovered object-ref field names."""

    cot: object
    host_field: str
    security_field: str

    @property
    def object_field_names(self) -> tuple[str, str]:
        return (self.host_field, self.security_field)


def object_fields_for_cot(cot) -> list:
    """Return object / multi-object fields defined on *cot*."""
    return list(
        CustomObjectTypeField.objects.filter(
            custom_object_type=cot,
            type__in=[
                CustomFieldTypeChoices.TYPE_OBJECT,
                CustomFieldTypeChoices.TYPE_MULTIOBJECT,
            ],
        )
    )


def _related_content_type_ids(field) -> list[int]:
    ids: list[int] = []
    related = getattr(field, "related_object_type", None)
    if related is not None and getattr(related, "pk", None):
        ids.append(related.pk)
    try:
        for ct in field.related_object_types.all():
            if getattr(ct, "pk", None):
                ids.append(ct.pk)
    except Exception:
        pass
    return ids


def _field_is_policy_side(field) -> bool:
    """True when *field* targets linkable NSM policy object types."""
    ct_ids = _related_content_type_ids(field)
    if not ct_ids:
        return False
    return all(is_linkable_content_type(ct_id) for ct_id in ct_ids)


def classify_object_link_field_names(fields: Sequence) -> tuple[str, str] | None:
    """
    Map two object-ref fields to ``(host_field, security_field)`` names.

    Uses related-type linkability from ``nsm_config``; if ambiguous, keeps
    schema field order (legacy ObjectLink A/B semantics).
    """
    if len(fields) != 2:
        return None
    security_fields = [f for f in fields if _field_is_policy_side(f)]
    host_fields = [f for f in fields if not _field_is_policy_side(f)]
    if len(security_fields) == 1 and len(host_fields) == 1:
        return host_fields[0].name, security_fields[0].name
    return fields[0].name, fields[1].name


def is_link_table_cot(cot) -> bool:
    """True when *cot* is flagged as a link/junction table (``nsm_config.link_table``)."""
    return cot_link_table_flag(cot)


def get_object_link_cot():
    """Return the deployed link-table COT, or ``None``.

    Identified by ``link_table: true`` in ``nsm_config`` (COT comments or native
    ``link_table`` field) — never by slug.
    """
    try:
        for cot in CustomObjectType.objects.all():
            if cot_link_table_flag(cot):
                return cot
    except Exception:
        return None
    return None


def get_object_link_cot_slug() -> str | None:
    """Slug of the deployed link-table COT, or ``None``."""
    cot = get_object_link_cot()
    return getattr(cot, "slug", None) if cot is not None else None


def get_object_link_schema() -> ObjectLinkSchema | None:
    """Resolve link-table COT plus host/policy object-ref field names."""
    cot = get_object_link_cot()
    if cot is None:
        return None
    names = classify_object_link_field_names(object_fields_for_cot(cot))
    if names is None:
        return None
    host_field, security_field = names
    return ObjectLinkSchema(cot=cot, host_field=host_field, security_field=security_field)


def read_link_endpoints(
    schema: ObjectLinkSchema, instance
) -> tuple[object | None, object | None]:
    """Read ``(host_object, security_object)`` from a link row using *schema*."""
    return (
        getattr(instance, schema.host_field, None),
        getattr(instance, schema.security_field, None),
    )
