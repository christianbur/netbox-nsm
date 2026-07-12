from __future__ import annotations

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.core.type_kind import column_is_address
from netbox_nsm.rulebooks.rules_tab.constants import (
    COLUMN_MODE_COLLAPSED,
    COLUMN_MODE_DEFAULT,
    COLUMN_MODE_EXPANDED,
)
from netbox_nsm.rulebooks.rules_tab.headers import (
    rules_field_display_label,
    rules_object_column_accessible_label,
    rules_object_column_header_parts,
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
            if flat and flat.get("kind") == "field":
                col_def["rules_column_kind"] = "field"
                col_def["display_label"] = flat.get("label") or col_id
            elif flat:
                col_def["rules_meta"] = _rules_column_meta_payload(flat)
                if flat.get("kind") == "object" and not children:
                    col_def["rules_column_kind"] = "object"
                    col_def["header_title"] = flat.get("header_title") or flat.get("label") or ""
                    col_def["header_subtitle"] = flat.get("header_subtitle") or ""
                    col_def["display_label"] = (
                        flat.get("display_label") or flat.get("label") or ""
                    )


def _column_def_child_is_address(child: dict) -> bool:
    """True when a grid/header child column is an Address or Address Group type."""
    label = str(child.get("headerName") or "")
    if label:
        return "address" in label.lower()
    key = child.get("field") or child.get("colId") or ""
    type_name = key.rsplit("::", 1)[-1] if "::" in key else ""
    return column_is_address(
        {
            "type_name": type_name,
            "label": label,
        }
    )


def _children_are_all_address_types(children: list) -> bool:
    return bool(children) and all(
        _column_def_child_is_address(child) for child in children
    )


def _merge_polymorphic_children_col(col: dict, children: list) -> dict:
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
            "group_label": header_name,
        }
        for child in children
    ]
    width = max(_rules_leaf_default_width(child) for child in children)
    return {
        "colId": area_slug,
        "field": area_slug,
        "headerName": header_name,
        "field_label": field_label,
        "field_group": field_group,
        "is_polymorphic": col.get("is_polymorphic", len(children) > 1),
        "merged_keys": merged_keys,
        "type_segments": type_segments,
        "rules_column_kind": "object",
        "cellRenderer": "objectCell",
        "minWidth": 220,
        "width": width,
    }


def collapse_rules_column_defs(
    column_defs: list,
    *,
    address_only: bool = False,
) -> list[dict]:
    """Merge polymorphic child columns into one column per parent field.

    When *address_only* is true, only fields whose children are exclusively
    Address / Address Group types are merged (expanded-mode address columns).
    """
    collapsed: list[dict] = []
    for col in column_defs or []:
        children = col.get("children")
        if children:
            if address_only and not _children_are_all_address_types(children):
                collapsed.append(col)
                continue
            collapsed.append(_merge_polymorphic_children_col(col, children))
            continue
        collapsed.append(col)
    return collapsed


def prepare_rules_column_defs(
    column_defs: list,
    *,
    column_mode: str = COLUMN_MODE_DEFAULT,
) -> list[dict]:
    """Apply column-mode layout: collapsed merges polymorphic children per field."""
    if column_mode == COLUMN_MODE_COLLAPSED and any(
        col.get("children") for col in column_defs or []
    ):
        result = collapse_rules_column_defs(column_defs)
    else:
        result = column_defs
    return result


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
    column_defs = prepare_rules_column_defs(column_defs, column_mode=column_mode)

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
        if col_id and col.get("rules_column_kind") == "field":
            label = col.get("headerName") or col_id
            columns.append(
                {
                    "kind": "field",
                    "slug": col_id,
                    "col_id": col_id,
                    "label": label,
                    "header_title": label,
                    "header_subtitle": "",
                    "field_type": col.get("field_type") or "",
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
