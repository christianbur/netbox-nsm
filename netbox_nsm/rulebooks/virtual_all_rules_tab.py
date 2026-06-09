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
    _resolve_rules_filter_model,
    _rules_clamp_page,
    _rules_filter_needs_full_scan,
    _sort_rules_records,
    build_rulebook_rules_grid_column_defs,
    build_rules_page_url,
    flatten_rules_column_defs,
    parse_rules_cell_mode,
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
            row["pk"] = f"{cot.slug}:{row['pk']}"
            all_rows.append(row)
    if layout is None:
        layout = {"rows": [], "rules_layout": [], "header_groups": [], "grouped_columns": []}
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
        }

    base_ctx = build_cot_rulebook_rules_tab_context(
        request,
        build_virtual_cot_rulebook_row(first_cot),
        readonly=True,
    )
    rows, layout = _aggregate_cot_rows(virtual_all_rules)

    filter_model = parse_rules_filter_model(request)
    sort_field, sort_order = parse_rules_sort(request)
    per_page = get_paginate_count(request)
    page_num = int(request.GET.get("page") or 1)

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

    paginator = EnhancedPaginator(rows, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)

    base_ctx.update(
        {
            "rows": list(page_obj.object_list),
            "paginator": paginator,
            "page_obj": page_obj,
            "rules_readonly": True,
            "rules_empty": not rows,
            "all_rules_aggregate": True,
            "rules_show_bulk_delete": False,
            "bulk_delete_url": "",
        }
    )
    return base_ctx
