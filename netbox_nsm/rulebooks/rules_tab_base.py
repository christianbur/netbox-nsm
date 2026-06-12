"""Rules tab: server-rendered HTML policy table."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.utils.html import conditional_escape, escape
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.security.panel_link_actions import append_return_url
from netbox_nsm.rulebooks.cot_rule_clone import build_rule_clone_url
from netbox_nsm.rulebooks.grid_payload import (
    _description_cell_html,
    _description_line_count,
    _record_field_filter_text,
    build_column_quick_filter_spec,
    build_rulebook_rules_grid_column_defs,
    enabled_status_labels,
    filter_spec_to_column_quick_value,
)
from netbox_nsm.rulebooks.cell_html import (
    rules_filter_target_html,
    CELL_MODE_COMPACT,
    CELL_MODE_DEFAULT,
    CELL_MODE_INLINE,
    CELL_MODE_PILL_MORE,
    normalize_rules_cell_mode,
    render_rules_merged_object_cell_html,
    render_rules_object_cell_html,
)
from utilities.paginator import EnhancedPaginator, get_paginate_count

__all__ = (
    "RULES_HTML_ROW_LIMIT",
    "RULES_FILTER_PREFIX",
    "format_rules_tab_badge",
    "rules_tab_badge_for_object",
    "build_rules_page_url",
    "build_rules_sort_url",
    "build_rules_sort_url_for_order",
    "collapse_rules_column_defs",
    "flatten_rules_column_defs",
    "parse_rules_cell_mode",
    "parse_rules_column_mode",
    "parse_rules_filter_model",
    "parse_rules_sort",
    "rules_field_display_label",
    "rules_object_column_display_label",
    "rules_object_column_header_parts",
    "rules_object_column_accessible_label",
    "RULES_CELL_MODE_QUERY_PARAM",
    "RULES_COLUMN_MODE_QUERY_PARAM",
)

RULES_HTML_ROW_LIMIT = 25
RULES_FILTER_PREFIX = "f_"
RULES_CELL_MODE_QUERY_PARAM = "cell_mode"
RULES_COLUMN_MODE_QUERY_PARAM = "col_mode"
COLUMN_MODE_EXPANDED = "expanded"
COLUMN_MODE_COLLAPSED = "collapsed"
COLUMN_MODE_DEFAULT = COLUMN_MODE_COLLAPSED
COLUMN_MODES = frozenset({COLUMN_MODE_EXPANDED, COLUMN_MODE_COLLAPSED})
RULES_DEFAULT_SORT = ("index", "asc")
RULES_SYSTEM_FIELDS = frozenset({"rulebook", "index", "name", "enabled", "description"})


def format_rules_tab_badge(
    filtered_count: int,
    total_count: int,
    *,
    filter_active: bool,
) -> int | str:
    """Rules nav-tab badge: ``filtered/total`` when filters apply, else total only."""
    if filter_active:
        return f"{filtered_count}/{total_count}"
    return total_count


def rules_tab_badge_for_object(obj) -> int | str | None:
    """Badge value for virtual rulebook tab navigation."""
    badge = getattr(obj, "rules_tab_badge", None)
    if badge is not None and badge != "":
        return badge
    rule_count = getattr(obj, "rule_count", None)
    return rule_count if rule_count is not None else None


def normalize_rules_column_mode(raw: str | None) -> str:
    """Return supported rules-table column layout mode (expanded or collapsed)."""
    mode = (raw or "").strip().lower()
    if mode in COLUMN_MODES:
        return mode
    return COLUMN_MODE_DEFAULT


def parse_rules_column_mode(request) -> str:
    """Column layout mode from the query string (expanded / collapsed)."""
    return normalize_rules_column_mode(request.GET.get(RULES_COLUMN_MODE_QUERY_PARAM))


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


def _rules_column_filter_param_names(col: dict) -> list[str]:
    """URL query keys that apply a quick-search value to this column."""
    primary = _rules_filter_param_name(col)
    names: list[str] = [primary] if primary else []
    for merged_key in col.get("merged_keys") or []:
        alt = f"{RULES_FILTER_PREFIX}{_rules_param_token(merged_key)}"
        if alt not in names:
            names.append(alt)
    field = _rules_query_field(col)
    area_slug = col.get("area_slug") or (
        (field or "").split("::", 1)[0] if field else ""
    )
    if area_slug and field and field != area_slug:
        collapsed = f"{RULES_FILTER_PREFIX}{_rules_param_token(area_slug)}"
        if collapsed not in names:
            names.append(collapsed)
    return names


def _rules_filter_raw_from_request(request, col: dict) -> str:
    """Read the first matching per-column filter value from the query string."""
    for param in _rules_column_filter_param_names(col):
        raw = (request.GET.get(param) or "").strip()
        if raw:
            return raw
    return ""


def rules_field_display_label(
    field_label: str, field_group: str = "", *, cot=None
) -> str:
    """Combine COT field label and UI group, e.g. Zones + Source → Zones (Source)."""
    from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

    label = (field_label or "").strip()
    group = resolve_group_name_for_display(field_group, cot=cot)
    if label and group and group != label:
        return f"{label} ({group})"
    return label or group


def rules_object_column_display_label(
    child_header: str, group_header: str, *, group_in_parens: bool = True
) -> str:
    """Build object column title, e.g. Zones (Source)."""
    title, _subtitle = rules_object_column_header_parts(
        child_header, group_header, group_in_parens=group_in_parens
    )
    return title


def _group_header_is_field_label(group_header: str) -> bool:
    """True when *group_header* is a full field label, not just Source/Destination."""
    group = (group_header or "").strip()
    if not group:
        return False
    if "(" in group:
        return True
    return len(group.split()) > 1 or "&" in group


def rules_object_column_header_parts(
    child_header: str,
    group_header: str = "",
    *,
    field_label: str = "",
    field_group: str = "",
    group_in_parens: bool = True,
) -> tuple[str, str]:
    """Return (title, subtitle) for two-line object column headers.

    *title* — field context, e.g. ``Addresses (Source)`` (small in expanded thead).
    *subtitle* — object/COT type name, e.g. ``Address`` (bold in expanded thead).
    """
    type_label = (child_header or "").strip()
    label = (field_label or "").strip()
    group = (field_group or "").strip()
    legacy_group = (group_header or "").strip()

    if label:
        title = rules_field_display_label(label, group)
        subtitle = type_label or label
        return title, subtitle

    if _group_header_is_field_label(legacy_group):
        title = legacy_group
        subtitle = type_label or legacy_group
        return title, subtitle

    if group_in_parens and type_label and legacy_group and legacy_group != type_label:
        from netbox_nsm.rulebooks.rulebook_groups import resolve_group_name_for_display

        group_suffix = resolve_group_name_for_display(legacy_group) or legacy_group
        title = (
            f"{type_label} ({group_suffix})"
            if group_suffix and group_suffix != type_label
            else type_label
        )
    else:
        title = type_label or legacy_group
    subtitle = type_label or legacy_group
    return title, subtitle


def rules_object_column_accessible_label(title: str, subtitle: str) -> str:
    """Single-line label for aria/filter when header uses title + subtitle."""
    title = (title or "").strip()
    subtitle = (subtitle or "").strip()
    if title and subtitle and title != subtitle:
        return f"{subtitle}, {title}"
    return title or subtitle


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
        raw = _rules_filter_raw_from_request(request, col)
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
    from netbox_nsm.rulebooks.grid_filter import (
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


def _rules_column_meta_payload(col: dict) -> dict:
    """Sort/filter metadata for thead sort-header includes."""
    return {
        "sort_active": bool(col.get("sort_active")),
        "sort_order": col.get("sort_order") or "",
        "sort_url": col.get("sort_url") or "",
        "group_value": col.get("group_header") or col.get("key") or "",
    }


def attach_rules_column_defs_meta(column_defs: list, flat_columns: list) -> None:
    """Copy flat column labels and sort metadata onto nested column_defs for thead."""
    by_col_id: dict[str, dict] = {}
    for col in flat_columns:
        col_id = col.get("col_id") or col.get("key") or col.get("slug")
        if col_id:
            by_col_id[col_id] = col

    for col_def in column_defs or []:
        children = col_def.get("children")
        if children:
            group_header = col_def.get("headerName") or ""
            for child in children:
                col_id = child.get("field") or child.get("colId") or ""
                flat = by_col_id.get(col_id)
                if flat:
                    child["header_title"] = flat.get("header_title") or ""
                    child["header_subtitle"] = flat.get("header_subtitle") or ""
                    child["display_label"] = (
                        flat.get("display_label") or flat.get("label") or ""
                    )
                    child["rules_meta"] = _rules_column_meta_payload(flat)
                else:
                    title, subtitle = rules_object_column_header_parts(
                        child.get("headerName") or "",
                        group_header,
                        field_label=col_def.get("field_label") or "",
                        field_group=col_def.get("field_group") or "",
                    )
                    child["header_title"] = title
                    child["header_subtitle"] = subtitle
                    child["display_label"] = rules_object_column_accessible_label(
                        title, subtitle
                    )
                    child["rules_meta"] = _rules_column_meta_payload({})
            continue
        col_id = col_def.get("colId")
        if col_id and col_id != "_actions":
            flat = by_col_id.get(col_id)
            if flat:
                col_def["rules_meta"] = _rules_column_meta_payload(flat)
                if flat.get("kind") == "object" and not children:
                    col_def["rules_column_kind"] = "object"
                    col_def["header_title"] = flat.get("header_title") or flat.get("label") or ""
                    col_def["header_subtitle"] = flat.get("header_subtitle") or ""
                    col_def["display_label"] = (
                        flat.get("display_label") or flat.get("label") or ""
                    )


def collapse_rules_column_defs(column_defs: list) -> list[dict]:
    """Merge polymorphic child columns into one column per parent field."""
    collapsed: list[dict] = []
    for col in column_defs or []:
        children = col.get("children")
        if children:
            field_label = col.get("field_label") or ""
            field_group = col.get("field_group") or ""
            header_name = col.get("headerName") or rules_field_display_label(
                field_label, field_group
            )
            merged_keys = [
                child.get("field") or child.get("colId") or "" for child in children
            ]
            merged_keys = [key for key in merged_keys if key]
            area_slug = merged_keys[0].split("::", 1)[0] if merged_keys else ""
            type_segments = [
                {
                    "key": child.get("field") or child.get("colId") or "",
                    "type_label": child.get("headerName") or "",
                }
                for child in children
            ]
            width = max(_rules_leaf_default_width(child) for child in children)
            collapsed.append(
                {
                    "colId": area_slug,
                    "field": area_slug,
                    "headerName": header_name,
                    "field_label": field_label,
                    "field_group": field_group,
                    "is_polymorphic": col.get(
                        "is_polymorphic", len(children) > 1
                    ),
                    "merged_keys": merged_keys,
                    "type_segments": type_segments,
                    "rules_column_kind": "object",
                    "cellRenderer": "objectCell",
                    "minWidth": 220,
                    "width": width,
                }
            )
            continue
        collapsed.append(col)
    return collapsed


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


def flatten_rules_column_defs(
    column_defs: list,
    *,
    column_mode: str = COLUMN_MODE_DEFAULT,
) -> list[dict]:
    """Flatten column definitions into leaf columns for table body rendering."""
    if column_mode == COLUMN_MODE_COLLAPSED and any(
        col.get("children") for col in column_defs or []
    ):
        column_defs = collapse_rules_column_defs(column_defs)

    columns: list[dict] = []
    for col in column_defs or []:
        merged_keys = col.get("merged_keys")
        if merged_keys:
            area_slug = col.get("field") or col.get("colId") or ""
            field_label = col.get("field_label") or ""
            field_group = col.get("field_group") or ""
            title = col.get("headerName") or rules_field_display_label(
                field_label, field_group
            )
            columns.append(
                {
                    "kind": "object",
                    "key": area_slug,
                    "col_id": area_slug,
                    "area_slug": area_slug,
                    "label": title,
                    "header_title": title,
                    "header_subtitle": "",
                    "field_label": field_label,
                    "field_group": field_group,
                    "group_header": title,
                    "is_polymorphic": col.get(
                        "is_polymorphic", len(col.get("type_segments") or []) > 1
                    ),
                    "merged_keys": merged_keys,
                    "type_segments": col.get("type_segments") or [],
                    **_rules_column_width_fields(col),
                }
            )
            continue
        children = col.get("children")
        if children:
            field_label = col.get("field_label") or ""
            field_group = col.get("field_group") or ""
            group_header = col.get("headerName") or ""
            for child in children:
                col_key = child.get("field") or child.get("colId") or ""
                title, subtitle = rules_object_column_header_parts(
                    child.get("headerName") or "",
                    group_header,
                    field_label=field_label,
                    field_group=field_group,
                )
                area_slug = col_key.split("::", 1)[0] if col_key else ""
                columns.append(
                    {
                        "kind": "object",
                        "key": col_key,
                        "col_id": col_key,
                        "area_slug": area_slug,
                        "label": title,
                        "header_title": title,
                        "header_subtitle": subtitle,
                        "field_label": field_label,
                        "field_group": field_group,
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
    position = 0
    for col in columns:
        if col.get("col_id") == "_actions":
            continue
        position += 1
        col["col_position"] = position
    return columns


def _inject_rules_cell_context_attrs(
    html: str,
    *,
    rule_index,
    rule_name: str,
    col_id: str,
    col_position,
) -> str:
    """Add rule/column context on the cell loupe container for the IP Analyzer."""
    if not html or rule_index is None or col_position is None:
        return html
    attrs = (
        f' data-rule-index="{conditional_escape(str(rule_index))}"'
        f' data-rule-name="{conditional_escape(rule_name or "")}"'
        f' data-col-id="{conditional_escape(col_id or "")}"'
        f' data-col-position="{conditional_escape(str(col_position))}"'
    )
    for marker in ('class="nsm-ag-cell-list ', 'class="nsm-ag-cell-merged'):
        idx = html.find(marker)
        if idx >= 0:
            insert_at = html.find(">", idx)
            if insert_at >= 0:
                return html[:insert_at] + attrs + html[insert_at:]
    return html


def _render_status_cell_html(enabled: bool) -> str:
    """NetBox object-list ChoiceFieldColumn badge (e.g. IP address status)."""
    labels = enabled_status_labels()
    label = labels["on"] if enabled else labels["off"]
    bg_color = "success" if enabled else "secondary"
    badge = (
        f'<span class="badge text-bg-{bg_color}"'
        f' data-nsm-filter-value="{escape(label)}">{escape(label)}</span>'
    )
    return rules_filter_target_html(badge, label)


def _render_name_cell_html(name: str, url: str) -> str:
    text = str(name or "")
    link = (
        f'<a href="{conditional_escape(url)}"'
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' data-nsm-filter-value="{escape(text)}"'
        f' title="{escape(text)}">{escape(text)}</a>'
    )
    return rules_filter_target_html(link, text)


def _render_index_cell_html(index, url: str, rule_name: str) -> str:
    idx = "" if index is None else str(index)
    name = str(rule_name or "")
    link = (
        f'<a href="{conditional_escape(url)}"'
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' data-nsm-filter-value="{escape(idx)}"'
        f' title="{escape(name)}">{escape(idx)}</a>'
    )
    return rules_filter_target_html(link, idx)


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
    clone_url: str | None = None,
    *,
    can_change: bool,
    can_delete: bool,
    can_add: bool = False,
) -> str:
    toggle_text = _("Toggle Dropdown")
    dropdown_links = []

    if can_delete:
        delete_label = _("Delete")
        dropdown_links.append(
            f'<li><a class="dropdown-item nsm-ag-action-delete"'
            f' href="{conditional_escape(delete_url)}">'
            f'<i class="mdi mdi-trash-can-outline" aria-hidden="true"></i> '
            f"{conditional_escape(delete_label)}</a></li>"
        )
    if can_add and clone_url:
        clone_label = _("Clone")
        dropdown_links.append(
            f'<li><a class="dropdown-item nsm-ag-action-clone"'
            f' href="{conditional_escape(clone_url)}">'
            f'<i class="mdi mdi-content-copy" aria-hidden="true"></i> '
            f"{conditional_escape(clone_label)}</a></li>"
        )

    if can_change:
        edit_label = _("Edit")
        edit_btn = (
            f'<a class="btn btn-sm btn-warning nsm-ag-action-edit"'
            f' href="{conditional_escape(edit_url)}" type="button"'
            f' title="{conditional_escape(edit_label)}"'
            f' aria-label="{conditional_escape(edit_label)}">'
            f'<i class="mdi mdi-pencil" aria-hidden="true"></i></a>'
        )
    else:
        edit_label = _("Edit")
        edit_btn = (
            f'<button type="button" class="btn btn-sm btn-warning" disabled'
            f' aria-disabled="true" title="{conditional_escape(edit_label)}"'
            f' aria-label="{conditional_escape(edit_label)}">'
            f'<i class="mdi mdi-pencil" aria-hidden="true"></i></button>'
        )

    if edit_btn and dropdown_links:
        html = (
            f'<span class="btn-group btn-group-sm dropdown">'
            f"  {edit_btn}"
            f'  <a class="btn btn-sm btn-warning dropdown-toggle" type="button"'
            f' data-bs-toggle="dropdown" style="padding-left: 2px">'
            f'  <span class="visually-hidden">{conditional_escape(toggle_text)}</span></a>'
            f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
            f"</span>"
        )
    elif edit_btn:
        html = f'<span class="btn-group btn-group-sm" role="group">{edit_btn}</span>'
    elif dropdown_links:
        html = (
            f'<span class="btn-group btn-group-sm dropdown">'
            f'  <a class="btn btn-sm btn-secondary dropdown-toggle" type="button"'
            f' data-bs-toggle="dropdown">'
            f'  <span class="visually-hidden">{conditional_escape(toggle_text)}</span></a>'
            f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
            f"</span>"
        )
    else:
        html = ""

    if not html:
        return '<div class="text-end text-nowrap"></div>'

    return f'<div class="text-end text-nowrap">{html}</div>'


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
    can_add: bool = False,
    rulebook_slug: str = "",
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
        area_slug = col.get("area_slug") or key.split("::", 1)[0]
        field = object_fields_by_slug.get(area_slug)
        colored = field.show_colored_pills if field is not None else True
        merged_keys = col.get("merged_keys")
        cells_items = row.get("cells_items") or {}
        if merged_keys:
            type_segments = []
            for segment in col.get("type_segments") or []:
                seg_key = segment.get("key") or ""
                items = cells_items.get(seg_key) or []
                branched = []
                for item in items:
                    copy = dict(item)
                    if copy.get("url"):
                        copy["url"] = with_branch_query(copy["url"], request)
                    branched.append(copy)
                type_segments.append(
                    {
                        "type_label": segment.get("type_label") or "",
                        "items": branched,
                    }
                )
            html = render_rules_merged_object_cell_html(
                type_segments,
                colored=colored,
                cell_mode=cell_mode,
                is_polymorphic=col.get("is_polymorphic", False),
            )
            return _inject_rules_cell_context_attrs(
                html,
                rule_index=system.get("index", row.get("index")),
                rule_name=system.get("name") or row.get("name") or "",
                col_id=col.get("col_id", ""),
                col_position=col.get("col_position"),
            )

        items = cells_items.get(key) or []
        branched = []
        for item in items:
            copy = dict(item)
            if copy.get("url"):
                copy["url"] = with_branch_query(copy["url"], request)
            branched.append(copy)
        html = render_rules_object_cell_html(
            branched,
            colored=colored,
            cell_mode=cell_mode,
        )
        return _inject_rules_cell_context_attrs(
            html,
            rule_index=system.get("index", row.get("index")),
            rule_name=system.get("name") or row.get("name") or "",
            col_id=col.get("col_id", ""),
            col_position=col.get("col_position"),
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
        clone_url = None
        if can_add and rulebook_slug and row.get("pk"):
            clone_url = build_rule_clone_url(
                request,
                rulebook_slug,
                row["pk"],
                return_path=return_path,
            )
        return _render_actions_cell_html(
            edit_url,
            delete_url,
            clone_url,
            can_change=can_change,
            can_delete=can_delete,
            can_add=can_add,
        )

    return '<span class="nsm-cell-empty">-</span>'


def _attach_rules_cells(
    rows: list,
    flat_columns: list,
    *,
    request,
    can_change: bool,
    can_delete: bool,
    can_add: bool = False,
    rulebook_slug: str = "",
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
                "col_position": col.get("col_position"),
                "min_width_px": col.get("min_width_px", 120),
                "html": _build_rules_cell_html(
                    col,
                    row,
                    request=request,
                    can_change=can_change,
                    can_delete=can_delete,
                    can_add=can_add,
                    rulebook_slug=rulebook_slug,
                    object_fields_by_slug=object_fields_by_slug,
                    cell_mode=cell_mode,
                ),
            }
            for col in flat_columns
        ]
