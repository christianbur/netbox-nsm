"""Helpers for custom-object M2M through tables (standard vs polymorphic)."""

from __future__ import annotations

from functools import lru_cache

__all__ = (
    "field_uses_polymorphic_through",
    "get_field_through_model",
    "read_m2m_ref_pairs",
    "through_table_column_names",
    "through_uses_polymorphic_columns",
    "write_standard_m2m_targets",
)


@lru_cache(maxsize=256)
def through_table_column_names(table_name: str) -> frozenset[str]:
    """Return live DB column names for *table_name* (not ORM metadata)."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            [table_name],
        )
        return frozenset(row[0] for row in cursor.fetchall())


def through_uses_polymorphic_columns(through_model) -> bool:
    """True when the through table stores ``(content_type_id, object_id)`` rows."""
    cols = through_table_column_names(through_model._meta.db_table)
    return "content_type_id" in cols and "object_id" in cols


def get_field_through_model(field):
    from django.apps import apps

    from netbox_custom_objects.constants import APP_LABEL

    through_name = getattr(field, "through_model_name", None)
    if not through_name:
        return None
    try:
        return apps.get_model(APP_LABEL, through_name)
    except LookupError:
        return None


def field_uses_polymorphic_through(field) -> bool:
    """True when *field* metadata and the live through table are polymorphic."""
    if not getattr(field, "is_polymorphic", False):
        return False
    through = get_field_through_model(field)
    if through is None:
        return False
    return through_uses_polymorphic_columns(through)


def read_m2m_ref_pairs(through_model, source_pk: int) -> list[tuple[int, int]]:
    """Return sorted ``(content_type_id, object_id)`` or ``(0, target_pk)`` rows."""
    from django.contrib.contenttypes.models import ContentType

    qs = through_model.objects.filter(source_id=source_pk)
    if through_uses_polymorphic_columns(through_model):
        return sorted(qs.values_list("content_type_id", "object_id"))

    pairs: list[tuple[int, int]] = []
    for row in qs.select_related("target"):
        target = getattr(row, "target", None)
        if target is None:
            continue
        ct = ContentType.objects.get_for_model(target)
        pairs.append((ct.pk, target.pk))
    return sorted(pairs)


def write_standard_m2m_targets(through_model, source_pk: int, target_pks) -> None:
    """Replace standard ``source_id`` / ``target_id`` through rows."""
    normalized = sorted({int(pk) for pk in target_pks if pk is not None})
    through_model.objects.filter(source_id=source_pk).delete()
    for target_pk in normalized:
        through_model.objects.create(source_id=source_pk, target_id=target_pk)
