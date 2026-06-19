"""Rules tab context for the virtual All Rules aggregate (all COT rulebooks)."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks
from netbox_nsm.rulebooks.rules_layout import (
    build_cot_grouped_rules_table_data,
    cot_rule_instances_queryset,
)
from netbox_nsm.rulebooks.rules_tab import build_cot_rulebook_rules_tab_context
from netbox_nsm.rulebooks.grid import (
    apply_ag_grid_row_filter,
    build_rulebook_rules_grid_row,
)
from netbox_nsm.rulebooks.rules_row_grouping import (
    build_row_group_tab_summaries,
    filter_rows_by_group_key,
    prepend_all_rules_tab,
    prepare_row_grouping_tab_columns,
    resolve_row_group_tab,
    row_group_sort_applies_to_groups,
)
from netbox_nsm.rulebooks.rules_tab import (
    RULES_SYSTEM_FIELDS,
    _attach_rules_cells,
    _annotate_rules_columns,
    _rules_clamp_page,
    _sort_rules_records,
    attach_rules_column_defs_meta,
    format_rules_tab_badge,
    parse_rules_filter_model,
    parse_rules_sort,
)
from netbox_nsm.rulebooks.virtual_cot import build_virtual_cot_rulebook_row
from utilities.paginator import EnhancedPaginator, get_paginate_count

__all__ = ("build_virtual_all_rules_rules_tab_context",)


def _aggregate_cot_rows(virtual_all_rules) -> tuple[list, dict]:
    """Merge grouped rows from every deployed COT rulebook."""
    all_rows = []
    layout = None
    for cot in iter_deployed_cot_rulebooks():
        virtual_rb = build_virtual_cot_rulebook_row(cot)
        instances = list(
            cot_rule_instances_queryset(virtual_rb).order_by("index", "pk")
        )
        grouped = build_cot_grouped_rules_table_data(instances, virtual_rb)
        if layout is None:
            layout = grouped
        rb_name = virtual_rb.name
        rb_url = virtual_rb.get_absolute_url()
        for row in grouped.get("rows") or []:
            row = dict(row)
            row["rulebook_name"] = rb_name
            row["rulebook_url"] = rb_url
            row["system"] = dict(row.get("system") or {})
            row["system"]["rulebook"] = rb_name
            row["system"]["rulebook_url"] = rb_url
            row["pk"] = f"{cot.slug}:{row['pk']}"
            all_rows.append(row)
    if layout is None:
        layout = {
            "rows": [],
            "rules_layout": [],
            "header_groups": [],
            "grouped_columns": [],
        }
    layout["rows"] = all_rows
    return all_rows, layout


def build_virtual_all_rules_rules_tab_context(request, virtual_all_rules) -> dict:
    """Read-only rules table spanning all COT rulebooks."""
    first_cot = next(iter_deployed_cot_rulebooks(), None)
    if first_cot is None:
        return {
            "rules_layout": [],
            "header_groups": [],
            "grouped_columns": [],
            "rows": [],
            "paginator": None,
            "page_obj": None,
            "rules_readonly": True,
            "rules_empty": True,
            "rules_row_group_active": False,
            "rules_row_group_col_id": "",
        }

    base_ctx = build_cot_rulebook_rules_tab_context(
        request,
        build_virtual_cot_rulebook_row(first_cot),
        readonly=True,
    )
    rows, layout = _aggregate_cot_rows(virtual_all_rules)
    unfiltered_total = len(rows)

    flat_columns_for_filter = list(base_ctx.get("rules_flat_columns") or [])
    filter_model = parse_rules_filter_model(request, flat_columns_for_filter)
    filter_active = bool(filter_model) or bool(base_ctx.get("rules_filter_query"))
    sort_field, sort_order = parse_rules_sort(request)
    per_page = get_paginate_count(request)
    try:
        page_num = int(request.GET.get("page") or 1)
    except (ValueError, TypeError):
        page_num = 1

    if filter_model:
        records = [build_rulebook_rules_grid_row(row) for row in rows]
        records = apply_ag_grid_row_filter(records, filter_model)
        allowed = {record["pk"] for record in records}
        rows = [row for row in rows if row["pk"] in allowed]

    if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
        rows = _sort_rules_records(rows, sort_field, sort_order)
    elif sort_field == "rulebook":
        rows.sort(
            key=lambda r: (r.get("rulebook_name") or "").lower(),
            reverse=sort_order == "desc",
        )

    row_group_col_id = base_ctx.get("rules_row_group_col_id") or ""
    flat_columns = list(base_ctx.get("rules_flat_columns") or [])
    column_defs = list(base_ctx.get("rules_column_defs") or [])
    cell_mode = base_ctx.get("rules_cell_mode")
    filtered_count = len(rows)

    row_group_tabs: list[dict] = []
    row_group_tab_active = ""

    if row_group_col_id:
        flat_columns, column_defs, row_group_column = prepare_row_grouping_tab_columns(
            flat_columns,
            column_defs,
            row_group_col_id,
        )
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

        tab_summaries = build_row_group_tab_summaries(
            rows,
            row_group_column,
            sort_field=sort_field,
            sort_order=sort_order,
        )
        active_group_key, row_group_tab_active = resolve_row_group_tab(
            request, tab_summaries
        )
        row_group_tabs = prepend_all_rules_tab(tab_summaries, filtered_count)
        for tab in row_group_tabs:
            tab["is_active"] = tab["group_id"] == row_group_tab_active

        if active_group_key is None:
            tab_rows = rows
        else:
            tab_rows = filter_rows_by_group_key(
                rows, row_group_column, active_group_key
            )
        if sort_field in RULES_SYSTEM_FIELDS or sort_field == "enabled":
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)
        elif sort_field == "rulebook":
            tab_rows.sort(
                key=lambda r: (r.get("rulebook_name") or "").lower(),
                reverse=sort_order == "desc",
            )
        elif not row_group_sort_applies_to_groups(sort_field, row_group_column):
            tab_rows = _sort_rules_records(tab_rows, sort_field, sort_order)

        paginator = EnhancedPaginator(tab_rows, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        display_rows = list(page_obj.object_list)
        _attach_rules_cells(
            display_rows,
            flat_columns,
            request=request,
            can_change=False,
            can_delete=False,
            can_add=False,
            rulebook_slug="",
            object_fields_by_slug={},
            cell_mode=cell_mode,
        )
    else:
        paginator = EnhancedPaginator(rows, per_page)
        page_num = _rules_clamp_page(page_num, paginator)
        page_obj = paginator.get_page(page_num)
        display_rows = list(page_obj.object_list)
        _attach_rules_cells(
            display_rows,
            flat_columns,
            request=request,
            can_change=False,
            can_delete=False,
            can_add=False,
            rulebook_slug="",
            object_fields_by_slug={},
            cell_mode=cell_mode,
        )

    base_ctx.update(
        {
            "rules_column_defs": column_defs,
            "rules_flat_columns": flat_columns,
            "rules_rows": display_rows,
            "rules_total_rules": filtered_count,
            "rules_filtered_count": filtered_count,
            "rules_unfiltered_total": unfiltered_total,
            "rules_tab_badge": format_rules_tab_badge(
                filtered_count,
                unfiltered_total,
                filter_active=filter_active,
            ),
            "rules_filter_active": filter_active,
            "paginator": paginator,
            "page_obj": page_obj,
            "rules_paginator": paginator,
            "rules_page_obj": page_obj,
            "rules_row_group_tabs": row_group_tabs,
            "rules_row_group_tab_active": row_group_tab_active,
            "rules_readonly": True,
            "rules_empty": not rows,
            "all_rules_aggregate": True,
            "rules_show_bulk_delete": False,
            "bulk_delete_url": "",
        }
    )
    return base_ctx
