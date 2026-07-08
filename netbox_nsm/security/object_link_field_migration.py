"""One-time rename ``policy_object`` → ``security_object`` on ``nsm_object_link``."""

from __future__ import annotations

from netbox_nsm.security.links.cot_link_schema import get_object_link_cot

__all__ = ("migrate_policy_object_field_to_security_object",)


def _table_columns(table: str) -> set[str]:
    from django.db import connection

    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return {col.name for col in description}


def migrate_policy_object_field_to_security_object() -> bool:
    """Rename deployed COT field and DB columns (idempotent)."""
    try:
        import netbox_custom_objects  # noqa: F401
    except ImportError:
        return False

    from django.db import connection

    cot = get_object_link_cot()
    if cot is None:
        return False
    if cot.fields.filter(name="security_object").exists():
        return False
    field = cot.fields.filter(name="policy_object").first()
    if field is None:
        return False

    model = cot.get_model()
    table = model._meta.db_table
    columns = _table_columns(table)
    qn = connection.ops.quote_name

    with connection.cursor() as cursor:
        if "policy_object_content_type_id" in columns:
            cursor.execute(
                f"ALTER TABLE {qn(table)} RENAME COLUMN "
                f"{qn('policy_object_content_type_id')} TO {qn('security_object_content_type_id')}"
            )
        if "policy_object_object_id" in columns:
            cursor.execute(
                f"ALTER TABLE {qn(table)} RENAME COLUMN "
                f"{qn('policy_object_object_id')} TO {qn('security_object_object_id')}"
            )

    updated = cot.fields.filter(pk=field.pk, name="policy_object").update(name="security_object")
    if not updated:
        return False
    cot.clear_model_cache(cot.id)
    return True
