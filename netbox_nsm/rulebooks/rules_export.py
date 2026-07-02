"""Export COT rulebook rules as bundle-compatible JSON (``objects`` records)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from django.utils.translation import gettext as _

from netbox_nsm.bundles.bundle_extensions import format_portable_ref
from netbox_nsm.rulebooks.grid import (
    apply_ag_grid_row_filter,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_grid_row,
)
from netbox_nsm.rulebooks.rules_layout import (
    _PREFETCHED_M2M_ATTR,
    apply_cot_system_field_filters,
    build_cot_grouped_rules_table_data,
    build_cot_rules_layout,
    cot_db_order_fields,
    cot_multiobject_prefetch_plan,
    cot_rule_instances_queryset,
    prefetch_cot_multiobject_fields,
)
from netbox_nsm.rulebooks.rules_row_grouping import (
    ROW_GROUP_TAB_ALL_ID,
    RULES_ROW_GROUP_TAB_QUERY_PARAM,
    build_row_group_tab_summaries,
    build_system_row_group_tab_summaries_from_queryset,
    filter_queryset_by_system_group_key,
    filter_rows_by_group_key,
    find_row_group_column,
    resolve_row_group_tab,
    resolve_stored_row_group_column_id,
    system_group_db_field,
)
from netbox_nsm.rulebooks.rules_tab.column_defs import (
    flatten_rules_column_defs,
    prepare_rules_column_defs,
)
from netbox_nsm.rulebooks.rules_tab.constants import (
    COLUMN_MODE_EXPANDED,
    RULES_SYSTEM_FIELDS,
)
from netbox_nsm.rulebooks.rules_tab.filter_resolve import _resolve_rules_filter_model
from netbox_nsm.rulebooks.rules_tab.modes import parse_rules_column_mode
from netbox_nsm.rulebooks.rules_tab.sort import (
    _rules_filter_needs_full_scan,
    _sort_rules_records,
    parse_rules_sort,
)
from netbox_nsm.rulebooks.cot_hierarchy import get_cot_row_group_by_col_id

__all__ = (
    "build_cot_rulebook_rules_export_bundle",
    "collect_cot_rulebook_export_instances",
    "cot_instance_to_bundle_record",
)


class _CotRulebookViewHelpers:
    @staticmethod
    def _build_grouped_rules_table_data(instances, virtual_rb, *, layout=None, object_field_names=None):
        return build_cot_grouped_rules_table_data(
            instances,
            virtual_rb,
            layout=layout,
            object_field_names=object_field_names,
        )


def _field_portable_refs(instance, field) -> list[str]:
    from extras.choices import CustomFieldTypeChoices

    if field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return []

    prefetched = getattr(instance, _PREFETCHED_M2M_ATTR, {})
    if field.name in prefetched:
        objs = prefetched[field.name]
    else:
        related = getattr(instance, field.name, None)
        if related is None:
            return []
        objs = list(related.all() if hasattr(related, "all") else [])

    refs: list[str] = []
    for obj in objs:
        try:
            refs.append(format_portable_ref(obj))
        except ValueError:
            continue
    return refs


def cot_instance_to_bundle_record(instance, cot) -> dict[str, Any]:
    """Serialize one COT rule row in bundle ``objects[].records[]`` shape."""
    from extras.choices import CustomFieldTypeChoices

    name = str(getattr(instance, "name", "") or "").strip()
    record: dict[str, Any] = {"name": name}

    for field in cot.fields.exclude(ui_visible="hidden").order_by("weight", "name"):
        if field.name == "name":
            continue

        if field.type == CustomFieldTypeChoices.TYPE_INTEGER:
            value = getattr(instance, field.name, None)
            if value is not None:
                record[field.name] = value
            continue

        if field.type == CustomFieldTypeChoices.TYPE_BOOLEAN:
            record[field.name] = bool(getattr(instance, field.name, True))
            continue

        if field.type in (
            CustomFieldTypeChoices.TYPE_TEXT,
            CustomFieldTypeChoices.TYPE_LONGTEXT,
        ):
            value = getattr(instance, field.name, None)
            if value not in (None, ""):
                record[field.name] = value
            continue

        if field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
            refs = _field_portable_refs(instance, field)
            if refs:
                record[field.name] = refs

    return record


def _instances_for_pks(virtual_rb, pks: list) -> list:
    if not pks:
        return []
    model = virtual_rb.cot.get_model()
    by_pk = {instance.pk: instance for instance in model.objects.filter(pk__in=pks)}
    return [by_pk[pk] for pk in pks if pk in by_pk]


def _resolve_export_row_group_key(
    request,
    *,
    row_group_column: dict,
    rows: list[dict] | None = None,
    qs=None,
    sort_field: str,
    sort_order: str,
) -> str | None:
    raw_tab = (request.GET.get(RULES_ROW_GROUP_TAB_QUERY_PARAM) or "").strip()
    if not raw_tab or raw_tab == ROW_GROUP_TAB_ALL_ID:
        return None

    if system_group_db_field(row_group_column) and qs is not None:
        tab_summaries = build_system_row_group_tab_summaries_from_queryset(
            qs,
            row_group_column,
            sort_field=sort_field,
            sort_order=sort_order,
        )
    elif rows is not None:
        tab_summaries = build_row_group_tab_summaries(
            rows,
            row_group_column,
            sort_field=sort_field,
            sort_order=sort_order,
        )
    else:
        return None

    active_group_key, _active_tab = resolve_row_group_tab(request, tab_summaries)
    return active_group_key


def collect_cot_rulebook_export_instances(request, virtual_rb) -> list:
    """Return all rule instances matching current rules-tab filters (no pagination)."""
    layout = build_cot_rules_layout(virtual_rb.cot)
    column_defs_full = build_rulebook_rules_grid_column_defs({**layout, "rows": []})[
        "columnDefs"
    ]
    flat_columns_expanded = flatten_rules_column_defs(
        column_defs_full,
        column_mode=COLUMN_MODE_EXPANDED,
    )
    row_group_col_id = (
        resolve_stored_row_group_column_id(
            get_cot_row_group_by_col_id(virtual_rb.slug),
            flat_columns_expanded,
        )
        or ""
    )
    column_mode = parse_rules_column_mode(request)
    column_defs = prepare_rules_column_defs(column_defs_full, column_mode=column_mode)
    flat_columns = flatten_rules_column_defs(column_defs, column_mode=column_mode)

    allowed_sort_fields = set(RULES_SYSTEM_FIELDS)
    for col in flat_columns:
        field = col.get("slug") or col.get("field")
        if field:
            allowed_sort_fields.add(field)

    sort_field, sort_order = parse_rules_sort(request, allowed_sort_fields)
    if sort_field == "status":
        sort_field = "enabled"

    filter_model, _filter_q_error, _filter_q_raw = _resolve_rules_filter_model(
        request,
        virtual_rb,
        flat_columns,
        view_helpers=_CotRulebookViewHelpers(),
        rules_layout=layout.get("rules_layout") or [],
    )

    m2m_prefetch = cot_multiobject_prefetch_plan(virtual_rb, layout)
    needs_full_scan = _rules_filter_needs_full_scan(filter_model, sort_field)
    row_group_column = (
        find_row_group_column(flat_columns_expanded, row_group_col_id)
        if row_group_col_id
        else None
    )

    qs = apply_cot_system_field_filters(
        cot_rule_instances_queryset(virtual_rb), filter_model
    )

    if row_group_column is not None:
        raw_tab = (request.GET.get(RULES_ROW_GROUP_TAB_QUERY_PARAM) or "").strip()
        active_group_key = None
        if raw_tab and raw_tab != ROW_GROUP_TAB_ALL_ID:
            active_group_key = _resolve_export_row_group_key(
                request,
                row_group_column=row_group_column,
                qs=qs if system_group_db_field(row_group_column) else None,
                sort_field=sort_field,
                sort_order=sort_order,
            )

        if needs_full_scan or not system_group_db_field(row_group_column):
            instances = list(qs)
            prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
            rows = build_cot_grouped_rules_table_data(
                instances, virtual_rb, layout=layout
            ).get("rows") or []
            if filter_model:
                records = [build_rulebook_rules_grid_row(row) for row in rows]
                records = apply_ag_grid_row_filter(records, filter_model)
                allowed_pks = {record["pk"] for record in records}
                rows = [row for row in rows if row["pk"] in allowed_pks]
            if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
                rows = _sort_rules_records(rows, sort_field, sort_order)
            if active_group_key is None and raw_tab and raw_tab != ROW_GROUP_TAB_ALL_ID:
                active_group_key = _resolve_export_row_group_key(
                    request,
                    row_group_column=row_group_column,
                    rows=rows,
                    sort_field=sort_field,
                    sort_order=sort_order,
                )
            if active_group_key is None:
                pks = [row["pk"] for row in rows]
            else:
                pks = [
                    row["pk"]
                    for row in filter_rows_by_group_key(
                        rows, row_group_column, active_group_key
                    )
                ]
            return _instances_for_pks(virtual_rb, pks)

        tab_qs = qs
        if active_group_key is not None:
            tab_qs = filter_queryset_by_system_group_key(
                tab_qs, row_group_column, active_group_key
            )
        tab_qs = tab_qs.order_by(*cot_db_order_fields(sort_field, sort_order))
        instances = list(tab_qs)
        prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
        return instances

    if needs_full_scan:
        instances = list(cot_rule_instances_queryset(virtual_rb))
        prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
        rows = build_cot_grouped_rules_table_data(
            instances, virtual_rb, layout=layout
        ).get("rows") or []
        if filter_model:
            records = [build_rulebook_rules_grid_row(row) for row in rows]
            records = apply_ag_grid_row_filter(records, filter_model)
            allowed_pks = {record["pk"] for record in records}
            rows = [row for row in rows if row["pk"] in allowed_pks]
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            rows = _sort_rules_records(rows, sort_field, sort_order)
        return _instances_for_pks(virtual_rb, [row["pk"] for row in rows])

    qs = qs.order_by(*cot_db_order_fields(sort_field, sort_order))
    instances = list(qs)
    prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
    return instances


def build_cot_rulebook_rules_export_bundle(request, virtual_rb) -> dict[str, Any]:
    """Build a bundle JSON document importable via NSM bundle ``objects`` seeding."""
    instances = collect_cot_rulebook_export_instances(request, virtual_rb)
    records = [
        cot_instance_to_bundle_record(instance, virtual_rb.cot) for instance in instances
    ]
    records.sort(key=lambda row: (row.get("index") or 0, row.get("name") or ""))
    exported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    title = _("Export: %(name)s rules") % {"name": virtual_rb.name}
    description = _(
        "Exported %(count)d rule(s) from %(slug)s at %(exported_at)s. "
        "Import via Security → Configuration → Bundles (objects seeding)."
    ) % {
        "count": len(records),
        "slug": virtual_rb.slug,
        "exported_at": exported_at,
    }
    return {
        "schema_type": "nsm",
        "schema_version": "1",
        "bundle_kind": "schema",
        "title": str(title),
        "description": str(description),
        "exported_at": exported_at,
        "rulebook_slug": virtual_rb.slug,
        "objects": [
            {
                "type": virtual_rb.slug,
                "records": records,
            }
        ],
    }
