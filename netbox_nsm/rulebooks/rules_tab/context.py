"""Rules tab context builder for COT-backed rulebooks."""

from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse
from django.utils.translation import gettext as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.rulebooks.cot_hierarchy import get_cot_row_group_by_col_id
from netbox_nsm.rulebooks.grid import (
    apply_ag_grid_row_filter,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_grid_row,
)
from netbox_nsm.rulebooks.rules_layout import (
    apply_cot_system_field_filters,
    build_cot_grouped_rules_table_data,
    build_cot_rules_layout,
    cot_db_order_fields,
    cot_multiobject_prefetch_plan,
    cot_row_group_object_field_names,
    cot_rule_instances_queryset,
    prefetch_cot_multiobject_fields,
)
from netbox_nsm.rulebooks.rules_row_grouping import (
    build_row_group_tab_summaries,
    build_object_group_pk_index,
    build_system_row_group_tab_summaries_from_queryset,
    cached_row_group_tab_summaries,
    filter_queryset_by_system_group_key,
    filter_rows_by_group_key,
    find_row_group_column,
    prepend_all_rules_tab,
    prepare_row_grouping_tab_columns,
    resolve_row_group_tab,
    resolve_stored_row_group_column_id,
    row_group_sort_applies_to_groups,
    row_group_tab_summaries_cache_key,
    system_group_db_field,
)
from netbox_nsm.rulebooks.rules_tab.badge import format_rules_tab_badge
from netbox_nsm.rulebooks.rules_tab.cells import _attach_rules_cells
from netbox_nsm.rulebooks.rules_tab.column_defs import (
    attach_rules_column_defs_meta,
    flatten_rules_column_defs,
    prepare_rules_column_defs,
)
from netbox_nsm.rulebooks.rules_tab.constants import (
    COLUMN_MODE_EXPANDED,
    RULES_FILTER_PREFIX,
    RULES_HTML_ROW_LIMIT,
    RULES_SYSTEM_FIELDS,
)
from netbox_nsm.rulebooks.rules_tab.filter_params import (
    _sync_column_filter_values_from_model,
    parse_rules_filter_model,
)
from netbox_nsm.rulebooks.rules_tab.filter_resolve import _resolve_rules_filter_model
from netbox_nsm.rulebooks.rules_tab.modes import (
    parse_rules_cell_mode,
    parse_rules_column_mode,
)
from netbox_nsm.rulebooks.rules_tab.sort import (
    _annotate_rules_columns,
    _rules_clamp_page,
    _rules_filter_needs_full_scan,
    _sort_rules_records,
    parse_rules_sort,
)
from netbox_nsm.query.engine import RulebookContext
from netbox_nsm.rulebooks.permissions import (
    can_add_rulebook_rules,
    can_change_rulebook,
    can_delete_rulebook_rules,
)
from utilities.paginator import EnhancedPaginator, get_paginate_count

__all__ = (
    "build_cot_rulebook_rules_tab_context",
    "_cot_rules_page",
    "_cot_rules_row_group_page",
)


class _CotRulebookViewHelpers:
    @staticmethod
    def _build_grouped_rules_table_data(instances, virtual_rb):
        return build_cot_grouped_rules_table_data(instances, virtual_rb)


def _cot_rules_page(
    virtual_rb,
    *,
    layout: dict | None = None,
    filter_model: dict,
    sort_field: str,
    sort_order: str,
    page_num: int,
    per_page: int,
) -> tuple[list, EnhancedPaginator, object]:
    if layout is None:
        layout = build_cot_rules_layout(virtual_rb.cot)

    m2m_prefetch = cot_multiobject_prefetch_plan(virtual_rb, layout)
    needs_full_scan = _rules_filter_needs_full_scan(filter_model, sort_field)

    def _load_rows(instances):
        prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
        grouped = build_cot_grouped_rules_table_data(
            instances, virtual_rb, layout=layout
        )
        return grouped.get("rows") or []

    if needs_full_scan:
        instances = list(cot_rule_instances_queryset(virtual_rb))
        rows = _load_rows(instances)

        if filter_model:
            records = [build_rulebook_rules_grid_row(row) for row in rows]
            records = apply_ag_grid_row_filter(records, filter_model)
            allowed_pks = {record["pk"] for record in records}
            rows = [row for row in rows if row["pk"] in allowed_pks]

        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            rows = _sort_rules_records(rows, sort_field, sort_order)

        paginator = EnhancedPaginator(rows, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        return list(page_obj.object_list), paginator, page_obj

    qs = cot_rule_instances_queryset(virtual_rb)
    qs = apply_cot_system_field_filters(qs, filter_model)
    qs = qs.order_by(*cot_db_order_fields(sort_field, sort_order))
    paginator = EnhancedPaginator(qs, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)
    instances = list(page_obj.object_list)
    rows = _load_rows(instances)
    return rows, paginator, page_obj


def _cot_load_display_rows(instances, virtual_rb, *, layout, m2m_prefetch):
    prefetch_cot_multiobject_fields(instances, virtual_rb, m2m_prefetch)
    grouped = build_cot_grouped_rules_table_data(
        instances, virtual_rb, layout=layout
    )
    return grouped.get("rows") or []


def _cot_rules_row_group_page(
    request,
    virtual_rb,
    *,
    layout: dict,
    row_group_column: dict,
    filter_model: dict,
    sort_field: str,
    sort_order: str,
    page_num: int,
    per_page: int,
) -> tuple[list[dict], str, int, list[dict], EnhancedPaginator, object]:
    """Paginated rules for one row-group tab with optimized tab-summary loading."""
    m2m_prefetch = cot_multiobject_prefetch_plan(virtual_rb, layout)
    needs_full_scan = _rules_filter_needs_full_scan(filter_model, sort_field)
    db_group_field = system_group_db_field(row_group_column)
    group_col_id = (
        row_group_column.get("col_id")
        or row_group_column.get("key")
        or row_group_column.get("slug")
        or ""
    )
    summaries_cache_key = row_group_tab_summaries_cache_key(
        virtual_rb.slug,
        group_col_id,
        filter_model,
        sort_field,
        sort_order,
    )

    qs = apply_cot_system_field_filters(
        cot_rule_instances_queryset(virtual_rb), filter_model
    )
    scan_object_fields = cot_row_group_object_field_names(
        row_group_column,
        filter_model,
        system_fields=RULES_SYSTEM_FIELDS,
    )
    all_rows: list[dict] = []
    object_group_pk_index: dict[str, list] | None = None
    filtered_pks: set | None = None

    def _build_object_group_summary_rows(instances) -> list[dict]:
        prefetch_cot_multiobject_fields(
            instances, virtual_rb, sorted(scan_object_fields)
        )
        return build_cot_grouped_rules_table_data(
            instances,
            virtual_rb,
            layout=layout,
            object_field_names=scan_object_fields,
            include_links=False,
        ).get("rows") or []

    if needs_full_scan:
        instances = list(qs)
        all_rows = _build_object_group_summary_rows(instances)

        if filter_model:
            records = [build_rulebook_rules_grid_row(row) for row in all_rows]
            records = apply_ag_grid_row_filter(records, filter_model)
            filtered_pks = {record["pk"] for record in records}
            all_rows = [row for row in all_rows if row["pk"] in filtered_pks]

        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            all_rows = _sort_rules_records(all_rows, sort_field, sort_order)

        total_rule_count = len(all_rows)
        summary_qs = (
            qs.filter(pk__in=filtered_pks)
            if filtered_pks is not None
            else qs
        )

        if db_group_field:
            tab_summaries = cached_row_group_tab_summaries(
                summaries_cache_key,
                lambda: build_system_row_group_tab_summaries_from_queryset(
                    summary_qs,
                    row_group_column,
                    sort_field=sort_field,
                    sort_order=sort_order,
                ),
            )
        else:
            object_group_pk_index = build_object_group_pk_index(
                all_rows, row_group_column
            )
            tab_summaries = cached_row_group_tab_summaries(
                summaries_cache_key,
                lambda: build_row_group_tab_summaries(
                    all_rows,
                    row_group_column,
                    sort_field=sort_field,
                    sort_order=sort_order,
                ),
            )
            all_rows = []
    else:
        total_rule_count = qs.count()
        if db_group_field:
            tab_summaries = cached_row_group_tab_summaries(
                summaries_cache_key,
                lambda: build_system_row_group_tab_summaries_from_queryset(
                    qs,
                    row_group_column,
                    sort_field=sort_field,
                    sort_order=sort_order,
                ),
            )
        else:
            instances = list(qs.order_by(*cot_db_order_fields(sort_field, sort_order)))
            summary_rows = _build_object_group_summary_rows(instances)
            object_group_pk_index = build_object_group_pk_index(
                summary_rows, row_group_column
            )
            tab_summaries = cached_row_group_tab_summaries(
                summaries_cache_key,
                lambda: build_row_group_tab_summaries(
                    summary_rows,
                    row_group_column,
                    sort_field=sort_field,
                    sort_order=sort_order,
                ),
            )

    active_group_key, row_group_tab_active = resolve_row_group_tab(
        request, tab_summaries
    )
    row_group_tabs = prepend_all_rules_tab(tab_summaries, total_rule_count)
    for tab in row_group_tabs:
        tab["is_active"] = tab["group_id"] == row_group_tab_active

    tab_source_qs = qs
    if filtered_pks is not None:
        tab_source_qs = qs.filter(pk__in=filtered_pks)

    if db_group_field:
        if active_group_key is None:
            tab_qs = tab_source_qs
        else:
            tab_qs = filter_queryset_by_system_group_key(
                tab_source_qs, row_group_column, active_group_key
            )
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            tab_qs = tab_qs.order_by(*cot_db_order_fields(sort_field, sort_order))
        paginator = EnhancedPaginator(tab_qs, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        rows = _cot_load_display_rows(
            list(page_obj.object_list), virtual_rb, layout=layout, m2m_prefetch=m2m_prefetch
        )
    elif object_group_pk_index is not None:
        tab_qs = tab_source_qs
        if active_group_key is not None:
            tab_qs = tab_qs.filter(
                pk__in=object_group_pk_index.get(active_group_key, [])
            )
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            tab_qs = tab_qs.order_by(*cot_db_order_fields(sort_field, sort_order))
        elif active_group_key is None or not row_group_sort_applies_to_groups(
            sort_field, row_group_column
        ):
            tab_qs = tab_qs.order_by(*cot_db_order_fields(sort_field, sort_order))
        paginator = EnhancedPaginator(tab_qs, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        rows = _cot_load_display_rows(
            list(page_obj.object_list), virtual_rb, layout=layout, m2m_prefetch=m2m_prefetch
        )
    elif active_group_key is None:
        tab_rows = all_rows
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)
        elif not row_group_sort_applies_to_groups(sort_field, row_group_column):
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)

        paginator = EnhancedPaginator(tab_rows, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        page_pks = [row["pk"] for row in page_obj.object_list]
        page_instances = list(tab_source_qs.filter(pk__in=page_pks))
        rows_by_pk = {
            row["pk"]: row
            for row in _cot_load_display_rows(
                page_instances, virtual_rb, layout=layout, m2m_prefetch=m2m_prefetch
            )
        }
        rows = [rows_by_pk[pk] for pk in page_pks if pk in rows_by_pk]
    else:
        tab_rows = filter_rows_by_group_key(
            all_rows, row_group_column, active_group_key
        )
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)
        elif not row_group_sort_applies_to_groups(sort_field, row_group_column):
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)

        paginator = EnhancedPaginator(tab_rows, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        page_pks = [row["pk"] for row in page_obj.object_list]
        page_instances = list(tab_source_qs.filter(pk__in=page_pks))
        rows_by_pk = {
            row["pk"]: row
            for row in _cot_load_display_rows(
                page_instances, virtual_rb, layout=layout, m2m_prefetch=m2m_prefetch
            )
        }
        rows = [rows_by_pk[pk] for pk in page_pks if pk in rows_by_pk]

    return (
        row_group_tabs,
        row_group_tab_active,
        total_rule_count,
        rows,
        paginator,
        page_obj,
    )


def build_cot_rulebook_rules_tab_context(request, virtual_rb, *, readonly=False) -> dict:
    """Build rules table layout + rows for a COT rulebook."""
    layout = build_cot_rules_layout(virtual_rb.cot)
    grouped_layout = {**layout, "rows": []}
    column_defs_full = build_rulebook_rules_grid_column_defs(grouped_layout)["columnDefs"]
    stored_row_group_col_id = get_cot_row_group_by_col_id(virtual_rb.slug)
    flat_columns_expanded = flatten_rules_column_defs(
        column_defs_full,
        column_mode=COLUMN_MODE_EXPANDED,
    )
    row_group_col_id = resolve_stored_row_group_column_id(
        stored_row_group_col_id,
        flat_columns_expanded,
    ) or ""
    column_mode = parse_rules_column_mode(request)
    column_defs = prepare_rules_column_defs(column_defs_full, column_mode=column_mode)
    flat_columns = flatten_rules_column_defs(column_defs, column_mode=column_mode)
    rules_layout = layout.get("rules_layout") or []

    allowed_sort_fields = set(RULES_SYSTEM_FIELDS)
    for col in flat_columns:
        field = col.get("slug") or col.get("field")
        if field:
            allowed_sort_fields.add(field)

    sort_field, sort_order = parse_rules_sort(request, allowed_sort_fields)
    if sort_field == "status":
        sort_field = "enabled"

    get_params = request.GET.copy()
    get_params.pop("page", None)
    get_params.pop("sort", None)
    get_params.pop("order", None)
    base_qs_str = get_params.urlencode()
    _annotate_rules_columns(
        flat_columns,
        request=request,
        sort_field=sort_field,
        sort_order=sort_order,
        base_qs_str=base_qs_str,
    )
    attach_rules_column_defs_meta(column_defs, flat_columns)

    filter_model, filter_q_error, filter_q_raw = _resolve_rules_filter_model(
        request,
        virtual_rb,
        flat_columns,
        view_helpers=_CotRulebookViewHelpers(),
        rules_layout=rules_layout,
    )
    if not parse_rules_filter_model(request, flat_columns) and filter_model:
        _sync_column_filter_values_from_model(flat_columns, filter_model)

    try:
        page_num = int(request.GET.get("page", 1))
    except (ValueError, TypeError):
        page_num = 1
    per_page = get_paginate_count(request)
    cell_mode = parse_rules_cell_mode(request)

    row_group_column = None
    row_group_tabs: list[dict] = []
    row_group_tab_active = ""
    total_rule_count = 0

    if row_group_col_id:
        row_group_column = find_row_group_column(
            flat_columns_expanded,
            row_group_col_id,
        )
        if row_group_column is None:
            row_group_col_id = ""
        else:
            flat_columns, column_defs, row_group_column = (
                prepare_row_grouping_tab_columns(
                    flat_columns,
                    column_defs,
                    row_group_col_id,
                    group_column=row_group_column,
                )
            )
    if row_group_col_id and row_group_column:
        _annotate_rules_columns(
            flat_columns,
            request=request,
            sort_field=sort_field,
            sort_order=sort_order,
            base_qs_str=base_qs_str,
        )
        attach_rules_column_defs_meta(column_defs, flat_columns)

        (
            row_group_tabs,
            row_group_tab_active,
            total_rule_count,
            rows,
            paginator,
            page_obj,
        ) = _cot_rules_row_group_page(
            request,
            virtual_rb,
            layout=layout,
            row_group_column=row_group_column,
            filter_model=filter_model,
            sort_field=sort_field,
            sort_order=sort_order,
            page_num=page_num,
            per_page=per_page,
        )
    else:
        rows, paginator, page_obj = _cot_rules_page(
            virtual_rb,
            layout=layout,
            filter_model=filter_model,
            sort_field=sort_field,
            sort_order=sort_order,
            page_num=page_num,
            per_page=per_page,
        )
        total_rule_count = paginator.count

    cot = virtual_rb.cot
    can_change = can_change_rulebook(request.user, cot)
    can_delete = can_delete_rulebook_rules(request.user, cot)
    can_add = can_add_rulebook_rules(request.user, cot)
    show_bulk_delete = can_delete and not readonly
    bulk_delete_url = ""
    if show_bulk_delete:
        bulk_delete_url = with_branch_query(
            reverse(
                "plugins:netbox_custom_objects:customobject_bulk_delete",
                kwargs={"custom_object_type": virtual_rb.slug},
            ),
            request,
        )
    return_path = with_branch_query(request.path, request)
    add_url = with_branch_query(
        reverse(
            "plugins:netbox_custom_objects:customobject_add",
            kwargs={"custom_object_type": virtual_rb.slug},
        )
        + f"?return_url={quote(return_path, safe='')}",
        request,
    )

    _attach_rules_cells(
        rows,
        flat_columns,
        request=request,
        can_change=can_change and not readonly,
        can_delete=can_delete and not readonly,
        can_add=can_add and not readonly,
        rulebook_slug=virtual_rb.slug,
        object_fields_by_slug={},
        cell_mode=cell_mode,
    )

    clear_params = request.GET.copy()
    clear_params.pop("page", None)
    for key in list(clear_params.keys()):
        if key.startswith(RULES_FILTER_PREFIX) or key in ("filter_q", "q"):
            clear_params.pop(key)
    clear_filters_path = request.path
    if clear_params:
        clear_filters_path = f"{clear_filters_path}?{clear_params.urlencode()}"

    rulebook_context = RulebookContext(virtual_rb)
    filter_column_map = build_filter_column_query_map(rules_layout, rulebook_context)
    if "enabled" in filter_column_map:
        filter_column_map.setdefault("status", filter_column_map["enabled"])
    filter_column_shorthand = build_filter_column_shorthand_names(
        filter_column_map, rules_layout
    )

    filter_active = bool(filter_model) or bool(filter_q_raw)
    filtered_count = total_rule_count or paginator.count
    if filter_active:
        unfiltered_total = cot_rule_instances_queryset(virtual_rb).count()
    else:
        unfiltered_total = filtered_count

    return {
        "rules_column_defs": column_defs,
        "rules_flat_columns": flat_columns,
        "rules_rows": rows,
        "rules_total_rules": filtered_count,
        "rules_filtered_count": filtered_count,
        "rules_unfiltered_total": unfiltered_total,
        "rules_tab_badge": format_rules_tab_badge(
            filtered_count,
            unfiltered_total,
            filter_active=filter_active,
        ),
        "rules_page_obj": page_obj,
        "rules_paginator": paginator,
        "rules_base_qs_str": base_qs_str,
        "rules_has_object_groups": any(col.get("children") for col in column_defs),
        "rules_has_object_header_stack": (
            bool(layout.get("header_groups"))
            and column_mode != "collapsed"
        ),
        "rules_sort_field": sort_field,
        "rules_sort_order": sort_order,
        "rules_filter_active": filter_active,
        "rules_filter_query": filter_q_raw,
        "rules_filter_query_error": filter_q_error,
        "rules_clear_filters_url": with_branch_query(clear_filters_path, request),
        "rules_form_action": with_branch_query(request.path, request),
        "rules_tab_label": virtual_rb.name,
        "rules_can_change": can_change and not readonly,
        "rules_can_delete": can_delete and not readonly,
        "rules_show_bulk_delete": show_bulk_delete,
        "bulk_delete_url": bulk_delete_url,
        "rules_show_selection_column": not readonly,
        "rules_show_add_rule": can_add and not readonly,
        "nsm_rule_add_url": add_url if not readonly else "",
        "rules_return_url": with_branch_query(request.get_full_path(), request),
        "rules_cell_mode": cell_mode,
        "rules_column_mode": column_mode,
        "rules_row_group_active": bool(row_group_col_id),
        "rules_row_group_col_id": row_group_col_id or "",
        "rules_row_group_tabs": row_group_tabs,
        "rules_row_group_tab_active": row_group_tab_active,
        "rules_chrome_config": {
            "queryValidateUrl": "",
            "rulebookId": virtual_rb.slug,
            "rulebookName": virtual_rb.name,
            "exportJsonUrl": with_branch_query(
                reverse(
                    "plugins:netbox_nsm:cot_rulebook_rules_export",
                    kwargs={"slug": virtual_rb.slug},
                ),
                request,
            ),
            "filterQuery": filter_q_raw,
            "filterQueryError": filter_q_error,
            "filterActive": filter_active,
            "clearFiltersUrl": with_branch_query(clear_filters_path, request),
            "filterColumnMap": filter_column_map,
            "filterColumnShorthand": filter_column_shorthand,
            "cellMode": cell_mode,
            "columnMode": column_mode,
            "rowLimit": RULES_HTML_ROW_LIMIT,
            "readonly": readonly,
            "i18n": {
                "invalidQuery": _("Invalid query"),
                "validationFailed": _("Validation failed"),
            },
        },
    }
