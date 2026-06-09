"""Shared HTML renderers for Rules table cells."""

from __future__ import annotations

from django.utils.html import conditional_escape, escape
from django.utils.translation import ngettext

DEFAULT_MAX_VISIBLE_PILLS = 5

CELL_MODE_INLINE = "inline"
CELL_MODE_STACK = "stack"
CELL_MODE_COMPACT = "compact"
CELL_MODE_PILL_MORE = "pill_more"
CELL_MODE_DEFAULT = CELL_MODE_STACK
CELL_MODES = frozenset(
    {CELL_MODE_INLINE, CELL_MODE_STACK, CELL_MODE_COMPACT, CELL_MODE_PILL_MORE}
)

_CELL_PILL_EXPAND_ONCLICK = (
    "var c=this.closest('.nsm-ag-cell-list');"
    "c.querySelectorAll('.nsm-pill-hidden').forEach(function(e){"
    "e.classList.remove('nsm-pill-hidden');"
    "});"
    "this.remove();"
)


def normalize_rules_cell_mode(raw: str | None) -> str:
    """Return a supported object-cell display mode (default: stack / one per line)."""
    mode = (raw or "").strip().lower()
    if mode in CELL_MODES:
        return mode
    return CELL_MODE_DEFAULT


def ipa_loupe_button_html(
    *,
    ct,
    pk,
    name: str = "",
    title: str = "Objekt analysieren",
) -> str:
    """Small magnifier button for the floating IP Analyzer applet (single object)."""
    return (
        f'<button type="button" class="nsm-ipa-loupe"'
        f' data-ct="{conditional_escape(str(ct))}"'
        f' data-pk="{conditional_escape(str(pk))}"'
        f' data-name="{conditional_escape(name or "")}"'
        f' title="{conditional_escape(title)}"'
        f' aria-label="{conditional_escape(title)}">'
        f'<i class="mdi mdi-magnify" aria-hidden="true"></i></button>'
    )


def ipa_cell_loupe_button_html(*, object_count: int = 1) -> str:
    """One loupe per rules cell — analyzes all address objects in the cell."""
    title = "Objekte analysieren" if object_count > 1 else "Objekt analysieren"
    return (
        f'<button type="button" class="nsm-ipa-loupe nsm-ipa-cell-loupe"'
        f' title="{conditional_escape(title)}"'
        f' aria-label="{conditional_escape(title)}">'
        f'<i class="mdi mdi-magnify" aria-hidden="true"></i></button>'
    )


def _analyzable_cell_items(items) -> list:
    return [
        item
        for item in items or []
        if (item.get("addrAnalyzable") or item.get("addr_analyzable"))
        and item.get("ct") is not None
        and item.get("pk") is not None
    ]


def _cell_probe_item_html(item) -> str:
    """Hidden marker so the applet can collect compact-cell objects."""
    return (
        f'<span class="nsm-ag-cell-item nsm-ag-cell-item--probe" hidden '
        f'data-ct="{conditional_escape(str(item["ct"]))}"'
        f' data-pk="{conditional_escape(str(item["pk"]))}"'
        f' data-name="{conditional_escape(item.get("name") or "")}"'
        f' data-addr-analyzable="1"></span>'
    )


def _cell_loupe_prefix_html(items) -> str:
    analyzable = _analyzable_cell_items(items)
    if not analyzable:
        return ""
    probes = "".join(_cell_probe_item_html(item) for item in analyzable)
    return ipa_cell_loupe_button_html(object_count=len(analyzable)) + probes


def _wrap_rules_cell_list(
    items,
    inner_html: str,
    mode_class: str,
    *,
    include_cell_loupe: bool = True,
) -> str:
    prefix = _cell_loupe_prefix_html(items) if include_cell_loupe else ""
    loupe_class = " nsm-ag-cell-list--has-loupe" if prefix else ""
    return (
        f'<div class="nsm-ag-cell-list {mode_class}{loupe_class}">'
        f"{prefix}{inner_html}</div>"
    )


def rules_pill_html_ag(item, *, hidden=False, colored=True):
    """Colored dot + plain text link (no pill chrome)."""
    color = (item.get("color") or "").strip() if colored else ""
    dot_html = ""
    if color:
        dot_html = (
            f'<span class="nsm-ag-cell-dot" style="background-color:'
            f'{conditional_escape(color)};" aria-hidden="true"></span>'
        )
    hidden_class = " nsm-pill-hidden" if hidden else ""
    excluded_class = " nsm-ag-cell-excluded" if item.get("excluded") else ""
    data_attrs = ""
    ct = item.get("ct")
    pk = item.get("pk")
    analyzable = item.get("addrAnalyzable") or item.get("addr_analyzable")
    if ct is not None and pk is not None:
        data_attrs = (
            f' data-ct="{conditional_escape(str(ct))}"'
            f' data-pk="{conditional_escape(str(pk))}"'
            f' data-name="{conditional_escape(item.get("name") or "")}"'
        )
        if analyzable:
            data_attrs += ' data-addr-analyzable="1"'
    name = item.get("name") or ""
    return (
        f'<span class="nsm-ag-cell-item{hidden_class}{excluded_class}"{data_attrs}>'
        f"{dot_html}"
        f'<a href="{conditional_escape(item["url"])}" '
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' draggable="false"'
        f' data-nsm-filter-value="{conditional_escape(name)}"'
        f' title="{conditional_escape(name)}">'
        f"{escape(name)}"
        f"</a>"
        f"</span>"
    )


def _join_inline_cell_items(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    joined: list[str] = []
    for idx, part in enumerate(parts):
        if idx:
            joined.append('<span class="nsm-ag-cell-sep">, </span>')
        joined.append(part)
    return "".join(joined)


def _render_rules_object_cell_stack(
    items, *, colored=True, include_cell_loupe: bool = True
) -> str:
    parts = [rules_pill_html_ag(item, colored=colored) for item in items]
    return _wrap_rules_cell_list(
        items,
        "".join(parts),
        "nsm-ag-cell-list--stack",
        include_cell_loupe=include_cell_loupe,
    )


def _render_rules_object_cell_inline(
    items, *, colored=True, include_cell_loupe: bool = True
) -> str:
    parts = [rules_pill_html_ag(item, colored=colored) for item in items]
    return _wrap_rules_cell_list(
        items,
        _join_inline_cell_items(parts),
        "nsm-ag-cell-list--inline",
        include_cell_loupe=include_cell_loupe,
    )


def _render_rules_object_cell_pill_more(
    items, *, colored=True, include_cell_loupe: bool = True
) -> str:
    if len(items) <= 1:
        return _render_rules_object_cell_stack(
            items, colored=colored, include_cell_loupe=include_cell_loupe
        )
    shown = items[:1]
    hidden = items[1:]
    parts = [rules_pill_html_ag(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(rules_pill_html_ag(item, hidden=True, colored=colored))
    parts.append(
        '<button type="button"'
        ' class="nsm-rule-pill nsm-rule-pill-muted nsm-ag-cell-more"'
        f' onclick="{_CELL_PILL_EXPAND_ONCLICK}"'
        f">+{len(hidden)}</button>"
    )
    inner = "".join(parts)
    return _wrap_rules_cell_list(
        items,
        inner,
        "nsm-ag-cell-list--pill-more",
        include_cell_loupe=include_cell_loupe,
    )


def _render_rules_object_cell_compact(
    items, *, colored=True, include_cell_loupe: bool = True
) -> str:
    if len(items) < 2:
        return _render_rules_object_cell_stack(
            items, colored=colored, include_cell_loupe=include_cell_loupe
        )
    names = [str(item.get("name") or "").strip() for item in items]
    names = [name for name in names if name]
    title = ", ".join(names) if names else str(len(items))
    count = len(items)
    count_label = ngettext(
        "%(count)s object",
        "%(count)s objects",
        count,
    ) % {"count": count}
    style = ""
    if colored:
        color = (items[0].get("color") or "").strip()
        if color:
            style = (
                f' style="background-color:{conditional_escape(color)};'
                f'border-color:{conditional_escape(color)};color:#fff;"'
            )
    inner = (
        f'<span class="nsm-rule-pill nsm-rule-pill--counter nsm-ag-cell-counter"'
        f' title="{conditional_escape(title)}"'
        f' aria-label="{conditional_escape(count_label)}"'
        f' data-nsm-filter-value="{conditional_escape(title)}"{style}>'
        f"{escape(count_label)}</span>"
    )
    return _wrap_rules_cell_list(
        items,
        inner,
        "nsm-ag-cell-list--compact",
        include_cell_loupe=include_cell_loupe,
    )


def render_rules_object_cell_html(
    items,
    *,
    colored=True,
    cell_mode: str = CELL_MODE_DEFAULT,
    include_cell_loupe: bool = True,
):
    """Render object cell HTML for Rules (inline, stacked lines, or compact counter)."""
    if not items:
        return '<span class="nsm-cell-empty">-</span>'
    mode = normalize_rules_cell_mode(cell_mode)
    if mode == CELL_MODE_INLINE:
        return _render_rules_object_cell_inline(
            items, colored=colored, include_cell_loupe=include_cell_loupe
        )
    if mode == CELL_MODE_COMPACT:
        return _render_rules_object_cell_compact(
            items, colored=colored, include_cell_loupe=include_cell_loupe
        )
    if mode == CELL_MODE_PILL_MORE:
        return _render_rules_object_cell_pill_more(
            items, colored=colored, include_cell_loupe=include_cell_loupe
        )
    return _render_rules_object_cell_stack(
        items, colored=colored, include_cell_loupe=include_cell_loupe
    )


def _wrap_merged_cell_html(items, inner_html: str) -> str:
    """One loupe for the entire polymorphic merged cell (corner-hover in CSS)."""
    prefix = _cell_loupe_prefix_html(items)
    loupe_class = " nsm-ag-cell-merged--has-loupe" if prefix else ""
    return f'<div class="nsm-ag-cell-merged{loupe_class}">{prefix}{inner_html}</div>'


def _render_merged_type_group(
    type_label: str,
    items: list,
    *,
    colored: bool,
    cell_mode: str,
    show_subheading: bool = True,
    include_cell_loupe: bool = True,
) -> str:
    inner = render_rules_object_cell_html(
        items,
        colored=colored,
        cell_mode=cell_mode,
        include_cell_loupe=include_cell_loupe,
    )
    if inner == '<span class="nsm-cell-empty">-</span>':
        return ""
    subheading = ""
    if show_subheading and type_label:
        subheading = (
            f'<span class="nsm-ag-cell-type-subheading">{escape(type_label)}</span>'
        )
    return (
        f'<div class="nsm-ag-cell-type-group">'
        f"{subheading}"
        f'<div class="nsm-ag-cell-type-items">{inner}</div>'
        f"</div>"
    )


def render_rules_merged_object_cell_html(
    type_segments: list,
    *,
    colored=True,
    cell_mode: str = CELL_MODE_DEFAULT,
    is_polymorphic: bool = False,
):
    """Render a collapsed object column; type subheadings only when polymorphic."""
    all_items = []
    for segment in type_segments or []:
        all_items.extend(segment.get("items") or [])

    if not is_polymorphic:
        return render_rules_object_cell_html(
            all_items,
            colored=colored,
            cell_mode=cell_mode,
        )

    groups = []
    for segment in type_segments or []:
        items = segment.get("items") or []
        if not items:
            continue
        group_html = _render_merged_type_group(
            segment.get("type_label") or "",
            items,
            colored=colored,
            cell_mode=cell_mode,
            show_subheading=True,
            include_cell_loupe=False,
        )
        if group_html:
            groups.append(group_html)
    if not groups:
        return '<span class="nsm-cell-empty">-</span>'
    return _wrap_merged_cell_html(all_items, "".join(groups))


def render_rules_cell_ag(items, max_pills=None, *, colored=True):
    if not items:
        return '<span class="nsm-cell-empty">-</span>'
    try:
        limit = max(
            1, int(max_pills if max_pills is not None else DEFAULT_MAX_VISIBLE_PILLS)
        )
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_VISIBLE_PILLS
    shown = items[:limit]
    hidden = items[limit:]
    parts = [rules_pill_html_ag(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(rules_pill_html_ag(item, hidden=True, colored=colored))
    if hidden:
        parts.append(
            '<button type="button"'
            ' class="nsm-ag-cell-more"'
            f' onclick="{_CELL_PILL_EXPAND_ONCLICK}"'
            f">+{len(hidden)}</button>"
        )
    inner = "".join(parts)
    return _wrap_rules_cell_list(items, inner, "")
