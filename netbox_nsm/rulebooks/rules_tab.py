"""Rules tab context builder for COT-backed rulebooks."""

from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.rulebooks.rules_layout import (
    build_cot_grouped_rules_table_data,
    build_cot_rules_layout,
    cot_db_order_fields,
    cot_multiobject_prefetch_plan,
    cot_rule_instances_queryset,
    prefetch_cot_multiobject_fields,
)
from netbox_nsm.rulebooks.grid_payload import (
    apply_ag_grid_row_filter,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    build_rulebook_rules_grid_row,
)
from netbox_nsm.rulebooks.rules_tab_base import (
    RULES_FILTER_PREFIX,
    RULES_HTML_ROW_LIMIT,
    RULES_SYSTEM_FIELDS,
    _annotate_rules_columns,
    _attach_rules_cells,
    attach_rules_column_defs_meta,
    _resolve_rules_filter_model,
    _rules_clamp_page,
    _rules_filter_needs_full_scan,
    _sort_rules_records,
    build_rulebook_rules_grid_column_defs,
    build_rules_page_url,
    collapse_rules_column_defs,
    flatten_rules_column_defs,
    parse_rules_cell_mode,
    parse_rules_column_mode,
    parse_rules_filter_model,
    parse_rules_sort,
)
from netbox_nsm.query.engine import RulebookContext
from utilities.paginator import EnhancedPaginator, get_paginate_count

__all__ = ("build_cot_rulebook_rules_tab_context",)


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
    needs_full_scan = bool(filter_model) or _rules_filter_needs_full_scan(
        filter_model, sort_field
    )

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
    qs = qs.order_by(*cot_db_order_fields(sort_field, sort_order))
    paginator = EnhancedPaginator(qs, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)
    instances = list(page_obj.object_list)
    rows = _load_rows(instances)
    return rows, paginator, page_obj


def build_cot_rulebook_rules_tab_context(request, virtual_rb, *, readonly=False) -> dict:
    """Build rules table layout + rows for a COT rulebook."""
    layout = build_cot_rules_layout(virtual_rb.cot)
    grouped_layout = {**layout, "rows": []}
    column_defs = build_rulebook_rules_grid_column_defs(grouped_layout)["columnDefs"]
    column_mode = parse_rules_column_mode(request)
    if column_mode == "collapsed":
        column_defs = collapse_rules_column_defs(column_defs)
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
        from netbox_nsm.rulebooks.rules_tab_base import _sync_column_filter_values_from_model

        _sync_column_filter_values_from_model(flat_columns, filter_model)

    try:
        page_num = int(request.GET.get("page", 1))
    except (ValueError, TypeError):
        page_num = 1
    per_page = get_paginate_count(request)
    cell_mode = parse_rules_cell_mode(request)

    rows, paginator, page_obj = _cot_rules_page(
        virtual_rb,
        layout=layout,
        filter_model=filter_model,
        sort_field=sort_field,
        sort_order=sort_order,
        page_num=page_num,
        per_page=per_page,
    )

    can_change = request.user.has_perm("netbox_custom_objects.change_customobject")
    can_delete = request.user.has_perm("netbox_custom_objects.delete_customobject")
    can_add = request.user.has_perm("netbox_custom_objects.add_customobject")
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

    return {
        "rules_column_defs": column_defs,
        "rules_flat_columns": flat_columns,
        "rules_rows": rows,
        "rules_total_rules": paginator.count,
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
        "rules_filter_active": bool(filter_model) or bool(filter_q_raw),
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
        "rules_chrome_config": {
            "queryValidateUrl": "",
            "rulebookId": virtual_rb.slug,
            "rulebookName": virtual_rb.name,
            "filterQuery": filter_q_raw,
            "filterQueryError": filter_q_error,
            "filterActive": bool(filter_model) or bool(filter_q_raw),
            "clearFiltersUrl": with_branch_query(clear_filters_path, request),
            "filterColumnMap": filter_column_map,
            "filterColumnShorthand": filter_column_shorthand,
            "cellMode": cell_mode,
            "columnMode": column_mode,
            "rowLimit": RULES_HTML_ROW_LIMIT,
            "readonly": readonly,
        },
    }
