"""
Create missing NSM branch tables in existing netbox_branching schemas.

Junction tables (``RuleObjectItem``, …) must exist in the branch schema or inserts
fall through ``search_path`` to ``public`` and FK-check against ``public.netbox_nsm_rule``.

Reference tables (``RulebookField``, …) must contain rows copied from main when first
created — an empty branch copy shadows ``public`` via ``search_path`` and breaks saves.
"""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection
from netbox.plugins import get_plugin_config

from netbox_nsm.branching_support import register_branching_models

# Junction rows are branch-specific — create empty tables only.
JUNCTION_MODEL_LABELS = (
    "netbox_nsm.ruleobjectitem",
    "netbox_nsm.rulegroupitem",
    "netbox_nsm.objectgroupmember",
)

# Shared rulebook metadata — copy rows from main on create / refresh.
REFERENCE_MODEL_LABELS = (
    "netbox_nsm.rulebookfield",
    "netbox_nsm.rulebookfieldtype",
)


class Command(BaseCommand):
    help = "Replicate missing NSM branch tables into existing branch schemas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema-id",
            dest="schema_id",
            help="Only sync this branch schema_id (e.g. k11eb2ac). Default: all ready branches.",
        )
        parser.add_argument(
            "--refresh-reference-data",
            action="store_true",
            help="Re-copy RulebookField / RulebookFieldType rows from main into branch tables.",
        )
        parser.add_argument(
            "--fix-sequences",
            action="store_true",
            help="Set id column DEFAULT nextval(...) on existing branch tables (fixes null id inserts).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without executing SQL.",
        )

    def handle(self, *args, **options):
        register_branching_models()

        try:
            from netbox_branching.models import Branch
            from netbox_branching.models.branches import BranchStatusChoices
        except ImportError as exc:
            self.stderr.write(f"netbox_branching not installed: {exc}")
            return

        main_schema = get_plugin_config("netbox_branching", "main_schema", "public")
        junction_tables = self._tables_for(JUNCTION_MODEL_LABELS)
        reference_tables = self._tables_for(REFERENCE_MODEL_LABELS)

        branches = Branch.objects.filter(status=BranchStatusChoices.READY)
        if schema_id := options.get("schema_id"):
            branches = branches.filter(schema_id=schema_id)

        dry_run = options["dry_run"]
        refresh = options["refresh_reference_data"]
        fix_sequences = options["fix_sequences"]

        for branch in branches:
            schema = branch.schema_name
            self.stdout.write(f"Branch {branch.name!r} ({schema})")
            for table in junction_tables:
                self._ensure_table(
                    schema, table, main_schema, copy_data=False, dry_run=dry_run
                )
                if fix_sequences or self._table_exists(schema, table):
                    self._ensure_id_sequence(schema, table, dry_run=dry_run)
            for table in reference_tables:
                exists = self._table_exists(schema, table)
                empty = exists and self._row_count(schema, table) == 0
                if not exists:
                    self._ensure_table(
                        schema, table, main_schema, copy_data=True, dry_run=dry_run
                    )
                    self._ensure_id_sequence(schema, table, dry_run=dry_run)
                elif refresh or empty:
                    self._copy_reference_data(
                        schema, table, main_schema, dry_run=dry_run
                    )
                    if fix_sequences:
                        self._ensure_id_sequence(schema, table, dry_run=dry_run)
                else:
                    self.stdout.write(f"  skip {schema}.{table} (exists, has data)")
                    if fix_sequences:
                        self._ensure_id_sequence(schema, table, dry_run=dry_run)

    def _ensure_table(
        self,
        schema: str,
        table: str,
        main_schema: str,
        *,
        copy_data: bool,
        dry_run: bool,
    ) -> None:
        if self._table_exists(schema, table):
            self.stdout.write(f"  skip {schema}.{table} (exists)")
            return
        create_sql = (
            f"CREATE TABLE {schema}.{table} "
            f"( LIKE {main_schema}.{table} INCLUDING INDEXES )"
        )
        if dry_run:
            self.stdout.write(f"  would run: {create_sql}")
            if copy_data:
                self.stdout.write(
                    f"  would copy: INSERT INTO {schema}.{table} "
                    f"SELECT * FROM {main_schema}.{table}"
                )
            return
        with connection.cursor() as cursor:
            cursor.execute(create_sql)
        self.stdout.write(self.style.SUCCESS(f"  created {schema}.{table}"))
        self._ensure_id_sequence(schema, table, dry_run=dry_run)
        if copy_data:
            self._copy_reference_data(schema, table, main_schema, dry_run=False)

    def _ensure_id_sequence(self, schema: str, table: str, *, dry_run: bool) -> None:
        """
        Share the main schema id sequence (same as netbox_branching branch provisioning).

        Without this, INSERT into branch junction tables leaves id=NULL → IntegrityError.
        """
        if not self._table_exists(schema, table):
            return
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
            row = cursor.fetchone()
            if not row or not row[0]:
                return
            sequence_name = row[0]
            cursor.execute(
                """
                SELECT column_default FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = 'id'
                """,
                [schema, table],
            )
            default = (cursor.fetchone() or [None])[0]
            if default and "nextval" in str(default):
                return
            sql = f"ALTER TABLE {schema}.{table} ALTER COLUMN id SET DEFAULT nextval(%s)"
        if dry_run:
            self.stdout.write(f"  would set id default on {schema}.{table} → {sequence_name}")
            return
        with connection.cursor() as cursor:
            cursor.execute(sql, [sequence_name])
        self.stdout.write(
            self.style.SUCCESS(f"  id default on {schema}.{table} → {sequence_name}")
        )

    def _copy_reference_data(
        self, schema: str, table: str, main_schema: str, *, dry_run: bool
    ) -> None:
        sql_truncate = f"TRUNCATE {schema}.{table}"
        sql_insert = (
            f"INSERT INTO {schema}.{table} SELECT * FROM {main_schema}.{table}"
        )
        if dry_run:
            self.stdout.write(f"  would run: {sql_truncate}")
            self.stdout.write(f"  would run: {sql_insert}")
            return
        with connection.cursor() as cursor:
            cursor.execute(sql_truncate)
            cursor.execute(sql_insert)
            count = self._row_count(schema, table)
        self.stdout.write(
            self.style.SUCCESS(f"  copied {count} rows into {schema}.{table}")
        )

    @staticmethod
    def _tables_for(labels: tuple[str, ...]) -> list[str]:
        tables: list[str] = []
        for label in labels:
            app_label, model_name = label.split(".", 1)
            model = apps.get_model(app_label, model_name)
            tables.append(model._meta.db_table)
        return sorted(set(tables))

    @staticmethod
    def _table_exists(schema: str, table: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
                LIMIT 1
                """,
                [schema, table],
            )
            return cursor.fetchone() is not None

    @staticmethod
    def _row_count(schema: str, table: str) -> int:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            return int(cursor.fetchone()[0])
