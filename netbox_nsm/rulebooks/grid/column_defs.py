from __future__ import annotations

from django.utils.translation import gettext as _

from netbox_nsm.core.type_kind import column_is_address

from netbox_nsm.rulebooks.grid.constants import _SYSTEM_COLUMN_DEFS

def _object_column_def(col: dict) -> dict:
    return {
        "colId": col["key"],
        "field": col["key"],
        "headerName": col["label"],
        "cellRenderer": "objectCell",
        "minWidth": 220,
        "width": 260,
        "cellRendererParams": {
            "maxPills": col.get("max_visible_pills", 5),
            "colored": col.get("show_colored_pills", True),
            "addressColumn": column_is_address(col),
        },
    }


def build_rulebook_rules_group_column_def(*, header_name: str | None = None) -> dict:
    """Pinned Group column for custom grouping in Group view."""
    label = header_name if header_name is not None else str(_("Group"))
    return {
        "colId": "_group",
        "field": "_groupLabel",
        "headerName": label,
        "pinned": "left",
        "lockPosition": "left",
        "cellRenderer": "rulesGroupCell",
        "width": 280,
        "minWidth": 160,
        "maxWidth": 480,
        "sortable": False,
        "filter": False,
        "floatingFilter": False,
        "resizable": True,
        "suppressHeaderMenuButton": True,
        "suppressColumnsToolPanel": True,
        "suppressFiltersToolPanel": True,
        "suppressMovable": True,
        "cellClass": "nsm-rules-group-cell",
    }


def apply_suppress_movable(column_defs: list[dict]) -> list[dict]:
    """Every leaf column must be non-movable or other columns can shift around it."""
    out: list[dict] = []
    for col in column_defs:
        next_col = dict(col)
        children = next_col.get("children")
        if children:
            next_col["children"] = apply_suppress_movable(children)
        else:
            next_col["suppressMovable"] = True
        out.append(next_col)
    return out


def _ensure_description_column_last(column_defs: list[dict]) -> list[dict]:
    """Description follows field config (sort_order 100): last data column before _actions."""
    desc_col = None
    rest: list[dict] = []
    for col in column_defs:
        if col.get("colId") == "description":
            desc_col = col
        else:
            rest.append(col)
    if desc_col is None:
        return column_defs
    insert_at = len(rest)
    for idx, col in enumerate(rest):
        if col.get("colId") == "_actions":
            insert_at = idx
            break
    rest.insert(insert_at, desc_col)
    return rest


def build_rulebook_rules_grid_column_defs(grouped: dict) -> dict:
    """Column definitions only (no row data)."""
    rules_layout = grouped.get("rules_layout") or []
    column_defs: list[dict] = []

    for entry in rules_layout:
        if entry.get("kind") == "system":
            slug = entry["slug"]
            spec = _SYSTEM_COLUMN_DEFS.get(slug)
            if not spec:
                continue
            column_defs.append({"colId": slug, "headerName": entry["label"], **spec})
            continue

        if entry.get("kind") == "field":
            column_defs.append(
                {
                    "colId": entry["slug"],
                    "field": entry["slug"],
                    "headerName": entry.get("label") or entry["slug"],
                    "rules_column_kind": "field",
                    "field_type": entry.get("field_type") or "",
                    "cellRenderer": "fieldCell",
                    "minWidth": 120,
                    "width": 160,
                }
            )
            continue

        group = entry.get("group") or {}
        children = [_object_column_def(col) for col in (group.get("columns") or [])]
        if not children:
            continue
        column_defs.append(
            {
                "headerName": entry.get("label") or group.get("label") or "",
                "field_label": entry.get("field_label") or group.get("field_label") or "",
                "field_group": entry.get("field_group") or group.get("field_group") or "",
                "is_polymorphic": entry.get("is_polymorphic", group.get("is_polymorphic")),
                "children": children,
            }
        )

    column_defs.append(
        {
            "colId": "_actions",
            "field": "_actions",
            "headerName": "",
            "cellRenderer": "actionsCell",
            "pinned": "right",
            "width": 72,
            "sortable": False,
            "filter": False,
            "floatingFilter": False,
            "suppressHeaderMenuButton": True,
            "suppressColumnsToolPanel": True,
            "suppressFiltersToolPanel": True,
        }
    )
    return {"columnDefs": column_defs}
