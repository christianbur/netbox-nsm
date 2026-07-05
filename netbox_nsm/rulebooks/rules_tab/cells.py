from __future__ import annotations

from django.utils.html import conditional_escape, escape
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.rulebooks.cell_html import (
    rules_filter_target_html,
    CELL_MODE_COMPACT,
    CELL_MODE_DEFAULT,
    CELL_MODE_INLINE,
    CELL_MODE_PILL_MORE,
    render_rules_merged_object_cell_html,
    render_rules_object_cell_html,
)
from netbox_nsm.rulebooks.cot_rule_clone import build_rule_clone_url
from netbox_nsm.rulebooks.grid.cells import (
    _description_cell_html,
    _description_line_count,
    enabled_status_labels,
)
from netbox_nsm.security.actions.panel_link_actions import append_return_url

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
    from netbox_nsm.core.split_actions import render_edit_delete_split_button_html

    return render_edit_delete_split_button_html(
        edit_url,
        delete_url,
        clone_url,
        can_edit=can_change,
        can_delete=can_delete,
        can_clone=can_add,
        edit_css_class="nsm-ag-action-edit",
        delete_css_class="nsm-ag-action-delete",
        clone_css_class="nsm-ag-action-clone",
        always_show_edit=True,
        cell_wrapper=True,
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
            label = (
                system.get("rulebook")
                or row.get("rulebook_name")
                or ""
            )
            url = system.get("rulebook_url") or row.get("rulebook_url") or ""
            rb_slug = system.get("rulebook_slug") or row.get("rulebook_slug") or ""
            if not url and rb_slug:
                from netbox_nsm.security.object_rules import build_rulebook_rules_tab_url

                url = build_rulebook_rules_tab_url(rb_slug)
            return _render_name_cell_html(
                label,
                with_branch_query(url, request),
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
