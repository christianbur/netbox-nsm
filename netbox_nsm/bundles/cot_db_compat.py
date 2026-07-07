"""Database compatibility for netbox-custom-objects extension columns.

Some installs carry NOT NULL columns (``menu_name``, ``link_table``, …) on
``netbox_custom_objects_customobjecttype`` before the installed Python package
defines matching model fields.  Inserts that omit those columns then fail with
NOT NULL violations even though the schema executor only sets the legacy attrs.
"""

from __future__ import annotations

__all__ = (
    "apply_schema_document",
    "ensure_cot_extension_column_defaults",
)

# column_name -> SQL DEFAULT expression
_COT_EXTENSION_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("menu_name", "''"),
    ("link_table", "false"),
    ("metadata", "''"),
    ("views", "''"),
    ("config_context_enabled", "false"),
)

_TABLE = "netbox_custom_objects_customobjecttype"


def ensure_cot_extension_column_defaults() -> None:
    """Set PostgreSQL DEFAULTs for extension columns when missing (idempotent)."""
    from django.db import connection

    columns = [name for name, _default in _COT_EXTENSION_DEFAULTS]
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, column_default
            FROM information_schema.columns
            WHERE table_name = %s
              AND column_name = ANY(%s)
            """,
            [_TABLE, columns],
        )
        current = {row[0]: row[1] for row in cursor.fetchall()}
        if not current:
            return

        for column, default_sql in _COT_EXTENSION_DEFAULTS:
            if column not in current or current[column] is not None:
                continue
            cursor.execute(
                f"ALTER TABLE {_TABLE} ALTER COLUMN {column} SET DEFAULT {default_sql}"
            )


def apply_schema_document(schema_doc: dict, *, allow_destructive: bool = False):
    """Apply a portable-schema document, ensuring DB defaults exist first."""
    ensure_cot_extension_column_defaults()
    from netbox_custom_objects.schema.executor import apply_document

    return apply_document(schema_doc, allow_destructive=allow_destructive)
