"""Rules tab: server-rendered HTML policy table."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.utils.html import conditional_escape, escape
from django.utils.translation import gettext_lazy as _

from netbox_nsm.branch_urls import with_branch_query
from netbox_nsm.panel_link_actions import append_return_url
from netbox_nsm.query.engine import RulebookContext
from netbox_nsm.rulebook_rules_grid_payload import (
    _description_cell_html,
    _description_line_count,
    _record_field_filter_text,
    apply_ag_grid_row_filter,
    build_column_quick_filter_spec,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_grid_row,
    enabled_status_labels,
    filter_spec_to_column_quick_value,
)
from netbox_nsm.models import Rule, RulebookFieldKind, RulebookTypeChoices
from netbox_nsm.rulebook_field_utils import get_visible_rulebook_fields
from netbox_nsm.virtual_rulebook import is_virtual_all_rules_rulebook
from netbox_nsm.rulebook_rules_cell_html import (
    CELL_MODE_COMPACT,
    CELL_MODE_DEFAULT,
    CELL_MODE_INLINE,
    CELL_MODE_PILL_MORE,
    normalize_rules_cell_mode,
    render_rules_object_cell_html,
)
from utilities.paginator import EnhancedPaginator, get_paginate_count

__all__ = (
    "RULES_HTML_ROW_LIMIT",
    "RULES_FILTER_PREFIX",
    "build_rulebook_rules_tab_context",
    "build_rules_page_url",
    "build_rules_sort_url",
    "build_rules_sort_url_for_order",
    "flatten_rules_column_defs",
    "parse_rules_cell_mode",
    "parse_rules_filter_model",
    "parse_rules_sort",
    "rules_object_column_display_label",
    "RULES_CELL_MODE_QUERY_PARAM",
)

RULES_HTML_ROW_LIMIT = 25
RULES_FILTER_PREFIX = "f_"
RULES_CELL_MODE_QUERY_PARAM = "cell_mode"
RULES_DEFAULT_SORT = ("index", "asc")
RULES_SYSTEM_FIELDS = frozenset({"rulebook", "index", "name", "enabled", "description"})


def parse_rules_cell_mode(request) -> str:
    """Object-cell display mode from the query string (inline / stack / compact)."""
    return normalize_rules_cell_mode(request.GET.get(RULES_CELL_MODE_QUERY_PARAM))


def _rules_query_field(col: dict) -> str | None:
    if col.get("kind") == "actions":
        return None
    if col.get("kind") == "system":
        return "enabled" if col.get("slug") == "status" else col.get("slug")
    return col.get("key")


def _rules_param_token(field: str) -> str:
    return field.replace("::", "__")


def _rules_filter_param_name(col: dict) -> str:
    if col.get("slug") == "status":
        return f"{RULES_FILTER_PREFIX}status"
    field = _rules_query_field(col)
    return f"{RULES_FILTER_PREFIX}{_rules_param_token(field or '')}"


def rules_object_column_display_label(
    child_header: str, group_header: str, *, group_in_parens: bool = True
) -> str:
    """Build object column title, e.g. Zones (Source)."""
    child = (child_header or "").strip()
    group = (group_header or "").strip()
    if group_in_parens and child and group:
        return f"{child} ({group})"
    return child or group


def parse_rules_sort(request, allowed_fields: set[str]) -> tuple[str, str]:
    sort_field = (request.GET.get("sort") or RULES_DEFAULT_SORT[0]).strip()
    sort_order = (request.GET.get("order") or RULES_DEFAULT_SORT[1]).strip().lower()
    if sort_field not in allowed_fields:
        sort_field = RULES_DEFAULT_SORT[0]
    if sort_order not in {"asc", "desc"}:
        sort_order = RULES_DEFAULT_SORT[1]
    return sort_field, sort_order


def _sync_column_filter_values_from_model(
    flat_columns: list,
    filter_model: dict,
) -> None:
    """Mirror resolved filter_q values into per-column quick-search inputs."""
    for col in flat_columns:
        field = _rules_query_field(col)
        if not field:
            continue
        spec = filter_model.get(field)
        if not spec:
            continue
        col["filter_value"] = filter_spec_to_column_quick_value(spec)


def parse_rules_filter_model(request, flat_columns: list) -> dict:
    model: dict = {}
    for col in flat_columns:
        field = _rules_query_field(col)
        if not field:
            continue
        raw = (request.GET.get(_rules_filter_param_name(col)) or "").strip()
        if raw:
            model[field] = build_column_quick_filter_spec(raw)
    return model


def _resolve_rules_filter_model(
    request,
    rulebook,
    flat_columns: list,
    *,
    view_helpers,
    rules_layout: list,
) -> tuple[dict, str | None, str]:
    """filter_q takes precedence over per-column quick-search params."""
    from netbox_nsm.rulebook_rules_grid_filter import (
        extract_grid_filter_params,
        resolve_rules_filter_model,
    )

    filter_raw, filter_q_raw = extract_grid_filter_params(request)
    filter_q_raw = filter_q_raw or ""
    column_model = parse_rules_filter_model(request, flat_columns)
    if column_model:
        return column_model, None, filter_q_raw

    if filter_q_raw:
        filter_model, err = resolve_rules_filter_model(
            filter_model_raw=filter_raw,
            filter_q_raw=filter_q_raw,
            rulebook=rulebook,
            view_helpers=view_helpers,
            rules_layout=rules_layout,
        )
        if err:
            return parse_rules_filter_model(request, flat_columns), err, filter_q_raw
        return filter_model or {}, None, filter_q_raw
    return parse_rules_filter_model(request, flat_columns), None, filter_q_raw


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


def _rules_prefetch_queryset(rulebook):
    if is_virtual_all_rules_rulebook(rulebook):
        return Rule.objects.filter(
            rulebook__rulebook_type=RulebookTypeChoices.SECURITY_RULES
        ).select_related("rulebook").prefetch_related(
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
    return rulebook.rules.prefetch_related(
        "object_items__field",
        "object_items__content_type",
        "group_items__field",
        "group_items__security_group",
    )


def _rules_filter_needs_full_scan(filter_model: dict, sort_field: str) -> bool:
    if sort_field not in RULES_SYSTEM_FIELDS:
        return True
    return any(field not in RULES_SYSTEM_FIELDS for field in filter_model)


def _enabled_filter_q(needle: str) -> Q | None:
    n = needle.lower().strip()
    if not n:
        return None
    labels = enabled_status_labels()
    on_parts = (labels["on"].lower(), "on", "enabled", "aktiv", "ein", "1", "true")
    off_parts = (labels["off"].lower(), "off", "disabled", "inaktiv", "aus", "0", "false")
    matches_on = any(part and part in n for part in on_parts)
    matches_off = any(part and part in n for part in off_parts)
    if matches_on and not matches_off:
        return Q(enabled=True)
    if matches_off and not matches_on:
        return Q(enabled=False)
    return Q(pk__in=[])


def _apply_enabled_db_filter(qs, needle: str):
    q = _enabled_filter_q(needle)
    if q is None:
        return qs
    return qs.filter(q)


def _rules_text_filter_q(field: str, spec: dict) -> Q | None:
    operator = (spec.get("operator") or "").upper()
    conditions = spec.get("conditions") or []
    if operator in {"OR", "AND"} and conditions:
        q = Q()
        for cond in conditions:
            if not isinstance(cond, dict):
                continue
            sub = _rules_text_filter_q(field, cond)
            if sub is None:
                continue
            if operator == "OR":
                q |= sub
            else:
                q &= sub
        return q

    needle = (spec.get("filter") or "").strip()
    if not needle:
        return None
    if field == "name":
        return Q(name__icontains=needle)
    if field == "rulebook":
        return Q(rulebook__name__icontains=needle)
    if field == "description":
        return Q(description__icontains=needle)
    if field == "enabled":
        return _enabled_filter_q(needle)
    if field == "index":
        return Q(_rules_index_text__icontains=needle)
    return None


def _rules_filter_spec_active(field: str, spec: dict) -> bool:
    if not isinstance(spec, dict) or field not in RULES_SYSTEM_FIELDS:
        return False
    if (spec.get("filter") or "").strip():
        return True
    return any(
        _rules_filter_spec_active(field, cond)
        for cond in (spec.get("conditions") or [])
        if isinstance(cond, dict)
    )


def _apply_rules_db_filters(qs, filter_model: dict):
    needs_index_annotate = any(
        field == "index" and _rules_filter_spec_active(field, spec)
        for field, spec in filter_model.items()
    )
    if needs_index_annotate:
        qs = qs.annotate(_rules_index_text=Cast("index", CharField()))
    for field, spec in filter_model.items():
        if not _rules_filter_spec_active(field, spec):
            continue
        q = _rules_text_filter_q(field, spec)
        if q is not None:
            qs = qs.filter(q)
    return qs


def _rules_db_order_by(sort_field: str, sort_order: str) -> list[str]:
    prefix = "-" if sort_order == "desc" else ""
    if sort_field == "rulebook":
        order = [f"{prefix}rulebook__name"]
    else:
        primary = sort_field if sort_field in RULES_SYSTEM_FIELDS else "index"
        order = [f"{prefix}{primary}"]
    if sort_field != "index":
        order.append("index")
    if sort_field != "name":
        order.append("name")
    return order


def _rules_clamp_page(page_num: int, paginator: Paginator) -> int:
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        page_num = 1
    return max(1, min(page_num, paginator.num_pages or 1))


def _rules_page_via_db(
    rulebook,
    *,
    filter_model: dict,
    sort_field: str,
    sort_order: str,
    page_num: int,
    per_page: int,
    view_helpers,
) -> tuple[list, EnhancedPaginator, object]:
    qs = _apply_rules_db_filters(_rules_prefetch_queryset(rulebook), filter_model)
    qs = qs.order_by(*_rules_db_order_by(sort_field, sort_order))
    paginator = EnhancedPaginator(qs, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)
    rules = list(page_obj.object_list)
    grouped = view_helpers._build_grouped_rules_table_data(rules, rulebook)
    return grouped.get("rows") or [], paginator, page_obj


def _rules_page_via_full_scan(
    rulebook,
    *,
    filter_model: dict,
    sort_field: str,
    sort_order: str,
    page_num: int,
    per_page: int,
    view_helpers,
) -> tuple[list, EnhancedPaginator, object]:
    """Object-column filter/sort: must evaluate all rules, still renders one page only."""
    all_rules = list(_rules_prefetch_queryset(rulebook).order_by("index", "name"))
    grouped = view_helpers._build_grouped_rules_table_data(all_rules, rulebook)
    records = [
        build_rulebook_rules_grid_row(row) for row in (grouped.get("rows") or [])
    ]
    if filter_model:
        records = apply_ag_grid_row_filter(records, filter_model)
    records = _sort_rules_records(records, sort_field, sort_order)
    row_by_pk = {row["pk"]: row for row in (grouped.get("rows") or [])}
    filtered_rows = [
        row_by_pk[record["pk"]] for record in records if record["pk"] in row_by_pk
    ]
    paginator = EnhancedPaginator(filtered_rows, per_page)
    page_num = _rules_clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)
    return list(page_obj.object_list), paginator, page_obj


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
            col["filter_value"] = (
                request.GET.get(_rules_filter_param_name(col)) or ""
            ).strip()
        else:
            col["sort_url"] = ""
            col["sort_url_asc"] = ""
            col["sort_url_desc"] = ""
            col["filter_param"] = ""
            col["filter_value"] = ""
        col["display_label"] = col.get("label") or col.get("slug") or col.get("key") or ""


def build_rules_page_url(request, page_num: int, base_qs_str: str = "") -> str:
    """Build a branch-aware Rules page URL preserving non-page query params."""
    query = f"page={page_num}"
    if base_qs_str:
        query = f"{query}&{base_qs_str}"
    return with_branch_query(f"{request.path}?{query}", request)


def _rules_leaf_default_width(col_def: dict) -> int:
    value = col_def.get("width") or col_def.get("minWidth") or 120
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return 120


def _rules_leaf_min_resize_width(default_width: int) -> int:
    return max(1, int(default_width) // 3)


def _rules_column_width_fields(col_def: dict) -> dict:
    default = _rules_leaf_default_width(col_def)
    min_resize = _rules_leaf_min_resize_width(default)
    return {
        "default_width_px": default,
        "min_width_px": min_resize,
        "width_px": default,
    }


def flatten_rules_column_defs(column_defs: list) -> list[dict]:
    """Flatten column definitions into leaf columns for table body rendering."""
    columns: list[dict] = []
    for col in column_defs or []:
        children = col.get("children")
        if children:
            group_header = col.get("headerName") or ""
            for child in children:
                col_key = child.get("field") or child.get("colId") or ""
                columns.append(
                    {
                        "kind": "object",
                        "key": col_key,
                        "col_id": col_key,
                        "label": rules_object_column_display_label(
                            child.get("headerName") or "", group_header
                        ),
                        "group_header": group_header,
                        **_rules_column_width_fields(child),
                    }
                )
            continue
        col_id = col.get("colId")
        if col_id == "_actions":
            columns.append(
                {
                    "kind": "actions",
                    "col_id": "_actions",
                    **_rules_column_width_fields(col),
                }
            )
            continue
        if col_id:
            columns.append(
                {
                    "kind": "system",
                    "slug": col_id,
                    "col_id": col_id,
                    "label": col.get("headerName") or col_id,
                    **_rules_column_width_fields(col),
                }
            )
    return columns


def _render_status_cell_html(enabled: bool) -> str:
    """NetBox object-list ChoiceFieldColumn badge (e.g. IP address status)."""
    labels = enabled_status_labels()
    label = labels["on"] if enabled else labels["off"]
    bg_color = "blue" if enabled else "secondary"
    return f'<span class="badge text-bg-{bg_color}">{escape(label)}</span>'


def _render_name_cell_html(name: str, url: str) -> str:
    text = str(name or "")
    return (
        f'<a href="{conditional_escape(url)}"'
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' draggable="false"'
        f' data-nsm-filter-value="{escape(text)}"'
        f' title="{escape(text)}">{escape(text)}</a>'
    )


def _render_index_cell_html(index, url: str, rule_name: str) -> str:
    idx = "" if index is None else str(index)
    name = str(rule_name or "")
    return (
        f'<a href="{conditional_escape(url)}"'
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' draggable="false"'
        f' data-nsm-filter-value="{escape(idx)}"'
        f' title="{escape(name)}">{escape(idx)}</a>'
    )


def _render_description_cell_html(description: str) -> str:
    desc = description or ""
    if desc == "-":
        desc = ""
    if not desc:
        return '<span class="text-muted">-</span>'
    inner = _description_cell_html({"description": desc})
    return f'<span class="nsm-rules-cell-text">{inner}</span>'


def _render_actions_cell_html(
    edit_url: str,
    delete_url: str,
    *,
    can_change: bool,
    can_delete: bool,
) -> str:
    if can_change:
        edit_btn = (
            f'<a class="btn btn-warning nsm-ag-action-edit" href="{conditional_escape(edit_url)}"'
            f' title="Edit" aria-label="Edit"><i class="mdi mdi-pencil"></i></a>'
        )
    else:
        edit_btn = (
            '<button type="button" class="btn btn-warning" disabled aria-disabled="true"'
            ' title="Edit"><i class="mdi mdi-pencil"></i></button>'
        )
    if can_delete:
        delete_btn = (
            f'<a class="btn btn-danger nsm-ag-action-delete" href="{conditional_escape(delete_url)}"'
            f' title="Delete" aria-label="Delete"><i class="mdi mdi-trash-can-outline"></i></a>'
        )
    else:
        delete_btn = (
            '<button type="button" class="btn btn-danger" disabled aria-disabled="true"'
            ' title="Delete"><i class="mdi mdi-trash-can-outline"></i></button>'
        )
    return (
        f'<div class="text-end text-nowrap">'
        f'<span class="btn-group btn-group-sm" role="group">{edit_btn}{delete_btn}</span>'
        f"</div>"
    )


def _object_line_count(row: dict) -> int:
    cells_items = row.get("cells_items") or {}
    if not cells_items:
        return 1
    return max(max(1, len(items or [])) for items in cells_items.values())


def _rules_row_is_multiline(row: dict, *, cell_mode: str = CELL_MODE_DEFAULT) -> bool:
    system = row.get("system") or {}
    desc_raw = system.get("description") or row.get("description") or ""
    if desc_raw == "-":
        desc_raw = ""
    desc_lines = _description_line_count(desc_raw)
    if cell_mode in (CELL_MODE_INLINE, CELL_MODE_COMPACT, CELL_MODE_PILL_MORE):
        object_lines = 1
    else:
        object_lines = _object_line_count(row)
    line_count = max(object_lines, desc_lines or 0, 1)
    return line_count > 1


def _build_rules_cell_html(
    col: dict,
    row: dict,
    *,
    request,
    can_change: bool,
    can_delete: bool,
    object_fields_by_slug: dict,
    cell_mode: str = CELL_MODE_DEFAULT,
) -> str:
    system = row.get("system") or {}
    detail_url = with_branch_query(system.get("url") or row.get("url") or "", request)

    if col["kind"] == "system":
        slug = col["slug"]
        if slug == "status":
            return _render_status_cell_html(bool(system.get("enabled")))
        if slug == "name":
            return _render_name_cell_html(
                system.get("name") or row.get("name") or "",
                detail_url,
            )
        if slug == "index":
            return _render_index_cell_html(
                system.get("index", row.get("index")),
                detail_url,
                system.get("name") or row.get("name") or "",
            )
        if slug == "rulebook":
            return _render_name_cell_html(
                system.get("rulebook") or "",
                with_branch_query(system.get("rulebook_url") or "", request),
            )
        if slug == "description":
            return _render_description_cell_html(
                system.get("description") or row.get("description") or ""
            )
        return f'<span class="nsm-cell-empty">-</span>'

    if col["kind"] == "object":
        key = col["key"]
        items = (row.get("cells_items") or {}).get(key) or []
        area_slug = col.get("area_slug") or key.split("::", 1)[0]
        field = object_fields_by_slug.get(area_slug)
        colored = field.show_colored_pills if field is not None else True
        branched = []
        for item in items:
            copy = dict(item)
            if copy.get("url"):
                copy["url"] = with_branch_query(copy["url"], request)
            branched.append(copy)
        return render_rules_object_cell_html(
            branched,
            colored=colored,
            cell_mode=cell_mode,
        )

    if col["kind"] == "actions":
        return_path = with_branch_query(request.get_full_path(), request)
        edit_url = append_return_url(
            with_branch_query(row.get("edit_url") or "", request),
            return_path,
        )
        delete_url = append_return_url(
            with_branch_query(row.get("delete_url") or "", request),
            return_path,
        )
        return _render_actions_cell_html(
            edit_url,
            delete_url,
            can_change=can_change,
            can_delete=can_delete,
        )

    return '<span class="nsm-cell-empty">-</span>'


def _attach_rules_cells(
    rows: list,
    flat_columns: list,
    *,
    request,
    can_change: bool,
    can_delete: bool,
    object_fields_by_slug: dict,
    cell_mode: str = CELL_MODE_DEFAULT,
) -> None:
    for row in rows:
        row["rules_multiline"] = _rules_row_is_multiline(row, cell_mode=cell_mode)
        row["rules_cells"] = [
            {
                "kind": col["kind"],
                "slug": col.get("slug", ""),
                "col_id": col.get("col_id", ""),
                "min_width_px": col.get("min_width_px", 120),
                "html": _build_rules_cell_html(
                    col,
                    row,
                    request=request,
                    can_change=can_change,
                    can_delete=can_delete,
                    object_fields_by_slug=object_fields_by_slug,
                    cell_mode=cell_mode,
                ),
            }
            for col in flat_columns
        ]


def build_rulebook_rules_tab_context(
    request, rulebook, *, view_helpers, readonly=False
) -> dict:
    """Build rules table layout + rows for the Rules HTML table."""
    readonly = readonly or is_virtual_all_rules_rulebook(rulebook)
    grouped_layout = view_helpers._build_grouped_rules_table_data([], rulebook)
    rules_layout = grouped_layout.get("rules_layout") or []
    column_defs = build_rulebook_rules_grid_column_defs(grouped_layout)["columnDefs"]
    flat_columns = flatten_rules_column_defs(column_defs)
    area_slug_by_key: dict[str, str] = {}
    for entry in rules_layout:
        if entry.get("kind") != "object":
            continue
        field_slug = entry.get("slug") or ""
        for col in (entry.get("group") or {}).get("columns") or []:
            col_key = col.get("key") or ""
            if col_key:
                area_slug_by_key[col_key] = col.get("area_slug") or field_slug
    for col in flat_columns:
        if col.get("kind") == "object":
            col_key = col.get("key") or ""
            if col_key in area_slug_by_key:
                col["area_slug"] = area_slug_by_key[col_key]
    allowed_sort_fields = {
        field
        for col in flat_columns
        if (field := _rules_query_field(col))
    }
    sort_field, sort_order = parse_rules_sort(request, allowed_sort_fields)
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
    column_meta: dict[str, dict] = {}
    for col in flat_columns:
        if col.get("kind") == "actions":
            column_meta["_actions"] = col
            continue
        field = _rules_query_field(col)
        if not field:
            continue
        column_meta[field] = col
        slug = col.get("slug")
        if slug:
            column_meta[slug] = col
    for col_def in column_defs:
        col_id = col_def.get("colId")
        if col_id and col_id in column_meta:
            col_def["rules_meta"] = column_meta[col_id]
        for child in col_def.get("children") or []:
            child["display_label"] = rules_object_column_display_label(
                child.get("headerName") or child.get("colId") or "",
                col_def.get("headerName") or "",
            )
            child_field = child.get("field") or child.get("colId") or ""
            if child_field in column_meta:
                child["rules_meta"] = column_meta[child_field]

    column_filter_model = parse_rules_filter_model(request, flat_columns)
    filter_model, filter_q_error, filter_q_raw = _resolve_rules_filter_model(
        request,
        rulebook,
        flat_columns,
        view_helpers=view_helpers,
        rules_layout=rules_layout,
    )
    if not column_filter_model and filter_model:
        _sync_column_filter_values_from_model(flat_columns, filter_model)
    clear_params = request.GET.copy()
    clear_params.pop("page", None)
    for key in list(clear_params.keys()):
        if key.startswith(RULES_FILTER_PREFIX) or key in ("filter_q", "q"):
            clear_params.pop(key)
    clear_filters_path = request.path
    if clear_params:
        clear_filters_path = f"{clear_filters_path}?{clear_params.urlencode()}"
    rules_clear_filters_url = with_branch_query(clear_filters_path, request)
    try:
        page_num = int(request.GET.get("page", 1))
    except (ValueError, TypeError):
        page_num = 1
    per_page = get_paginate_count(request)
    cell_mode = parse_rules_cell_mode(request)

    if _rules_filter_needs_full_scan(filter_model, sort_field):
        rows, paginator, page_obj = _rules_page_via_full_scan(
            rulebook,
            filter_model=filter_model,
            sort_field=sort_field,
            sort_order=sort_order,
            page_num=page_num,
            per_page=per_page,
            view_helpers=view_helpers,
        )
    else:
        rows, paginator, page_obj = _rules_page_via_db(
            rulebook,
            filter_model=filter_model,
            sort_field=sort_field,
            sort_order=sort_order,
            page_num=page_num,
            per_page=per_page,
            view_helpers=view_helpers,
        )

    object_fields_by_slug = {
        field.slug: field
        for field in get_visible_rulebook_fields(rulebook)
        if field.field_kind == RulebookFieldKind.OBJECT
    }
    can_change = not readonly and request.user.has_perm("netbox_nsm.change_rule")
    can_delete = not readonly and request.user.has_perm("netbox_nsm.delete_rule")
    from netbox.object_actions import BulkDelete, BulkEdit
    from urllib.parse import quote

    from django.urls import reverse

    bulk_actions = []
    if can_change:
        bulk_actions.append(BulkEdit)
    if can_delete:
        bulk_actions.append(BulkDelete)
    return_path = with_branch_query(request.path, request)
    nsm_rule_add_url = ""
    if not readonly:
        nsm_rule_add_url = with_branch_query(
            reverse("plugins:netbox_nsm:rule_add")
            + f"?rulebook={rulebook.pk}&return_url={quote(return_path, safe='')}",
            request,
        )
    _attach_rules_cells(
        rows,
        flat_columns,
        request=request,
        can_change=can_change,
        can_delete=can_delete,
        object_fields_by_slug=object_fields_by_slug,
        cell_mode=cell_mode,
    )

    rulebook_context = RulebookContext(rulebook)
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
        "rules_has_object_header_stack": False,
        "rules_sort_field": sort_field,
        "rules_sort_order": sort_order,
        "rules_filter_active": bool(filter_model) or bool(filter_q_raw),
        "rules_filter_query": filter_q_raw,
        "rules_filter_query_error": filter_q_error,
        "rules_clear_filters_url": rules_clear_filters_url,
        "rules_form_action": with_branch_query(request.path, request),
        "rules_tab_label": _("Rules"),
        "rules_can_change": can_change,
        "rules_can_delete": can_delete,
        "nsm_rule_add_url": nsm_rule_add_url,
        "rules_return_url": with_branch_query(request.get_full_path(), request),
        "rules_cell_mode": cell_mode,
        "rules_show_selection_column": not readonly,
        "rules_show_add_rule": not readonly,
        "rules_bulk_actions": tuple(bulk_actions),
        "rules_bulk_action_model": Rule,
        "rules_chrome_config": {
            "queryValidateUrl": (
                ""
                if readonly
                else reverse(
                    "plugins:netbox_nsm:rulebook_rules_grid_validate_api",
                    args=[rulebook.pk],
                )
            ),
            "rulebookId": rulebook.pk,
            "rulebookName": rulebook.name,
            "filterQuery": filter_q_raw,
            "filterQueryError": filter_q_error,
            "filterActive": bool(filter_model) or bool(filter_q_raw),
            "clearFiltersUrl": rules_clear_filters_url,
            "filterColumnMap": filter_column_map,
            "filterColumnShorthand": filter_column_shorthand,
            "cellMode": cell_mode,
        },
    }
