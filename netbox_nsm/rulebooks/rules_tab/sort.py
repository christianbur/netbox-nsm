from __future__ import annotations

from django.core.paginator import Paginator

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.rulebooks.grid.rows import _record_field_filter_text
from netbox_nsm.rulebooks.rules_tab.constants import (
    RULES_DEFAULT_SORT,
    RULES_SYSTEM_FIELDS,
)
from netbox_nsm.rulebooks.rules_tab.filter_params import (
    _rules_filter_param_name,
    _rules_filter_raw_from_request,
    _rules_query_field,
)
from netbox_nsm.rulebooks.rules_tab.headers import rules_object_column_accessible_label

def parse_rules_sort(request, allowed_fields: set[str]) -> tuple[str, str]:
    sort_field = (request.GET.get("sort") or RULES_DEFAULT_SORT[0]).strip()
    sort_order = (request.GET.get("order") or RULES_DEFAULT_SORT[1]).strip().lower()
    if sort_field not in allowed_fields:
        sort_field = RULES_DEFAULT_SORT[0]
    if sort_order not in {"asc", "desc"}:
        sort_order = RULES_DEFAULT_SORT[1]
    return sort_field, sort_order
def _rules_sort_key(record: dict, sort_field: str):
    if sort_field == "enabled":
        return (0 if record.get("enabled") else 1, "")
    if sort_field == "index":
        value = record.get("index")
        try:
            return (0, int(value))
        except (TypeError, ValueError):
            return (1, str(value or ""))
    text = _record_field_filter_text(record, sort_field)
    return (0, text)


def _sort_rules_records(records: list, sort_field: str, sort_order: str) -> list:
    reverse = sort_order == "desc"
    return sorted(
        records,
        key=lambda record: _rules_sort_key(record, sort_field),
        reverse=reverse,
    )


def _rules_filter_needs_full_scan(filter_model: dict, sort_field: str) -> bool:
    if sort_field not in RULES_SYSTEM_FIELDS:
        return True
    return any(field not in RULES_SYSTEM_FIELDS for field in filter_model)


def _rules_clamp_page(page_num: int, paginator: Paginator) -> int:
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        page_num = 1
    return max(1, min(page_num, paginator.num_pages or 1))


def build_rules_sort_url_for_order(
    request,
    sort_field: str,
    sort_order: str,
    *,
    base_qs_str: str = "",
) -> str:
    order = sort_order if sort_order in {"asc", "desc"} else "asc"
    query = f"sort={sort_field}&order={order}"
    if base_qs_str:
        query = f"{query}&{base_qs_str}"
    return with_branch_query(f"{request.path}?{query}", request)


def build_rules_sort_url(
    request,
    sort_field: str,
    *,
    current_sort: str,
    current_order: str,
    base_qs_str: str = "",
) -> str:
    next_order = "asc"
    if sort_field == current_sort:
        next_order = "desc" if current_order == "asc" else "asc"
    return build_rules_sort_url_for_order(
        request,
        sort_field,
        next_order,
        base_qs_str=base_qs_str,
    )


def _annotate_rules_columns(
    flat_columns: list,
    *,
    request,
    sort_field: str,
    sort_order: str,
    base_qs_str: str,
) -> None:
    for col in flat_columns:
        field = _rules_query_field(col)
        col["sortable"] = bool(field)
        col["sort_field"] = field
        col["sort_active"] = field == sort_field if field else False
        col["sort_order"] = sort_order if col.get("sort_active") else ""
        if field:
            col["sort_url"] = build_rules_sort_url(
                request,
                field,
                current_sort=sort_field,
                current_order=sort_order,
                base_qs_str=base_qs_str,
            )
            col["sort_url_asc"] = build_rules_sort_url_for_order(
                request, field, "asc", base_qs_str=base_qs_str
            )
            col["sort_url_desc"] = build_rules_sort_url_for_order(
                request, field, "desc", base_qs_str=base_qs_str
            )
            col["filter_param"] = _rules_filter_param_name(col)
            col["filter_value"] = _rules_filter_raw_from_request(request, col)
        else:
            col["sort_url"] = ""
            col["sort_url_asc"] = ""
            col["sort_url_desc"] = ""
            col["filter_param"] = ""
            col["filter_value"] = ""
        header_title = col.get("header_title") or ""
        header_subtitle = col.get("header_subtitle") or ""
        if header_title or header_subtitle:
            col["display_label"] = rules_object_column_accessible_label(
                header_title, header_subtitle
            )
        else:
            col["display_label"] = (
                col.get("label") or col.get("slug") or col.get("key") or ""
            )
