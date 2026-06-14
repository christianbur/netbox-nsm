"""Simple pill HTML for rules layout previews (non-AG-grid contexts)."""

from __future__ import annotations

from django.utils.html import conditional_escape

from netbox_nsm.core.nsm_object_status import nsm_object_status_icon_html

__all__ = (
    "DEFAULT_MAX_VISIBLE_PILLS",
    "render_rules_pill_cell",
    "_render_rules_cell",
)

DEFAULT_MAX_VISIBLE_PILLS = 5


def _rules_pill_html(item, *, hidden=False, colored=True):
    color = (item.get("color") or "").strip() if colored else ""
    style_parts = []
    if color:
        try:
            hex_val = color.lstrip("#")
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#111111" if luminance > 0.6 else "#ffffff"
        except (ValueError, IndexError):
            text_color = "#ffffff"
        style_parts.extend(
            [
                f"background-color: {conditional_escape(color)};",
                f"border-color: {conditional_escape(color)};",
                f"color: {text_color};",
            ]
        )
    if hidden:
        style_parts.append("display:none;")
    style_attr = f' style="{"".join(style_parts)}"' if style_parts else ""
    hidden_class = " nsm-pill-hidden" if hidden else ""
    colored_class = " nsm-rule-pill-colored" if color else ""
    excluded_class = " nsm-pill-excluded" if item.get("excluded") else ""
    parent_url = (item.get("parent_url") or "").strip()
    parent_name = (item.get("parent_name") or "").strip()
    parent_html = ""
    if parent_url and parent_name:
        parent_html = (
            f'<a href="{conditional_escape(parent_url)}" class="nsm-rule-pill-parent text-decoration-none">'
            f'{conditional_escape(parent_name)}</a>'
            f'<span class="text-muted"> / </span>'
        )
    status_icon = nsm_object_status_icon_html(item.get("status"))
    return (
        f"{parent_html}"
        f'<a href="{conditional_escape(item["url"])}" '
        f' class="nsm-rule-pill{colored_class}{hidden_class} text-decoration-none{excluded_class}"'
        f"{style_attr}"
        f' title="{conditional_escape(item["name"])}">'
        f'{conditional_escape(item["name"])}'
        f"</a>"
        f"{status_icon}"
    )


def render_rules_pill_cell(items, max_pills=None, *, colored=True):
    if not items:
        return '<span class="text-muted small">-</span>'
    try:
        limit = max(
            1, int(max_pills if max_pills is not None else DEFAULT_MAX_VISIBLE_PILLS)
        )
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_VISIBLE_PILLS
    shown = items[:limit]
    hidden = items[limit:]
    parts = [_rules_pill_html(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(_rules_pill_html(item, hidden=True, colored=colored))
    if hidden:
        parts.append(
            '<button type="button"'
            ' class="nsm-rule-pill nsm-rule-pill-muted nsm-pill-more"'
            ' style="border:none;cursor:pointer;flex-shrink:0;max-width:none;overflow:visible;"'
            " onclick=\"var c=this.closest('.nsm-rule-pills');"
            "c.querySelectorAll('.nsm-pill-hidden').forEach(function(e){e.style.display='';});"
            'this.remove();"'
            f">+{len(hidden)}</button>"
        )
    return f'<div class="nsm-rule-pills">{"".join(parts)}</div>'


# Backward-compatible alias for existing imports.
_render_rules_cell = render_rules_pill_cell
