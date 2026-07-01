"""NetBox-style orange Edit button with dropdown actions (Delete, …)."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils.html import conditional_escape
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class SplitDropdownItem:
    href: str
    label: str
    icon: str = "mdi-trash-can-outline"
    css_class: str = ""


def _btn_size_class(size: str) -> str:
    return "btn-sm " if size == "sm" else ""


def _render_dropdown_item(
    *,
    href: str | None,
    label: str,
    icon: str,
    css_class: str = "",
    disabled: bool = False,
    disabled_title: str = "",
) -> str:
    icon_html = f'<i class="mdi {conditional_escape(icon)}" aria-hidden="true"></i> '
    label_html = conditional_escape(label)
    item_class = "dropdown-item"
    if css_class:
        item_class = f"{item_class} {css_class}"

    if disabled or not href:
        title = conditional_escape(disabled_title) if disabled_title else ""
        title_attr = f' title="{title}"' if title else ""
        return (
            f'<li><span class="{item_class} disabled text-muted"'
            f' aria-disabled="true"{title_attr}>'
            f"{icon_html}{label_html}</span></li>"
        )

    return (
        f'<li><a class="{item_class}" href="{conditional_escape(href)}"'
        f' title="{label_html}" aria-label="{label_html}">'
        f"{icon_html}{label_html}</a></li>"
    )


def render_edit_delete_split_button_html(
    edit_url: str = "",
    delete_url: str = "",
    clone_url: str | None = None,
    *,
    can_edit: bool = True,
    can_delete: bool = True,
    can_clone: bool = False,
    size: str = "sm",
    edit_label: str | None = None,
    delete_label: str | None = None,
    clone_label: str | None = None,
    edit_icon_only: bool = True,
    edit_show_text: bool = False,
    edit_css_class: str = "",
    delete_css_class: str = "",
    clone_css_class: str = "",
    delete_disabled: bool = False,
    delete_disabled_title: str = "",
    show_delete_when_blocked: bool = False,
    extra_dropdown_items: list[SplitDropdownItem] | None = None,
    wrapper_class: str = "",
    cell_wrapper: bool = False,
    always_show_edit: bool = False,
) -> str:
    """Render primary Edit (btn-warning) with optional dropdown actions."""
    toggle_text = _("Toggle Dropdown")
    edit_label = edit_label or _("Edit")
    delete_label = delete_label or _("Delete")
    clone_label = clone_label or _("Clone")
    size_class = _btn_size_class(size)

    dropdown_links: list[str] = []

    show_delete_item = (can_delete and bool(delete_url)) or show_delete_when_blocked or delete_disabled
    if show_delete_item:
        dropdown_links.append(
            _render_dropdown_item(
                href=delete_url if can_delete and not delete_disabled else None,
                label=delete_label,
                icon="mdi-trash-can-outline",
                css_class=delete_css_class,
                disabled=not can_delete or delete_disabled or not delete_url,
                disabled_title=delete_disabled_title,
            )
        )

    for item in extra_dropdown_items or ():
        dropdown_links.append(
            _render_dropdown_item(
                href=item.href,
                label=item.label,
                icon=item.icon,
                css_class=item.css_class,
            )
        )

    if can_clone and clone_url:
        dropdown_links.append(
            _render_dropdown_item(
                href=clone_url,
                label=clone_label,
                icon="mdi-content-copy",
                css_class=clone_css_class,
            )
        )

    edit_btn = ""
    show_edit = always_show_edit or bool(edit_url)
    if show_edit:
        edit_classes = f"btn {size_class}btn-warning"
        if edit_css_class:
            edit_classes = f"{edit_classes} {edit_css_class}"
        icon_html = '<i class="mdi mdi-pencil" aria-hidden="true"></i>'
        text_html = (
            f" {conditional_escape(edit_label)}"
            if edit_show_text or not edit_icon_only
            else ""
        )
        if edit_url and can_edit:
            edit_btn = (
                f'<a class="{edit_classes}"'
                f' href="{conditional_escape(edit_url)}" type="button"'
                f' title="{conditional_escape(edit_label)}"'
                f' aria-label="{conditional_escape(edit_label)}">'
                f"{icon_html}{text_html}</a>"
            )
        elif edit_url or not can_edit:
            edit_btn = (
                f'<button type="button" class="{edit_classes}" disabled'
                f' aria-disabled="true"'
                f' title="{conditional_escape(edit_label)}"'
                f' aria-label="{conditional_escape(edit_label)}">'
                f"{icon_html}{text_html}</button>"
            )

    group_classes = "btn-group"
    if size == "sm":
        group_classes = f"{group_classes} btn-group-sm"
    if dropdown_links:
        group_classes = f"{group_classes} dropdown"
    if wrapper_class:
        group_classes = f"{group_classes} {wrapper_class}"

    if edit_btn and dropdown_links:
        html = (
            f'<span class="{group_classes}">'
            f"  {edit_btn}"
            f'  <a class="btn {size_class}btn-warning dropdown-toggle" type="button"'
            f' data-bs-toggle="dropdown" style="padding-left: 2px"'
            f' aria-expanded="false">'
            f'  <span class="visually-hidden">{conditional_escape(toggle_text)}</span></a>'
            f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
            f"</span>"
        )
    elif edit_btn:
        html = f'<span class="{group_classes}" role="group">{edit_btn}</span>'
    elif dropdown_links:
        html = (
            f'<span class="{group_classes}">'
            f'  <a class="btn {size_class}btn-secondary dropdown-toggle" type="button"'
            f' data-bs-toggle="dropdown" aria-expanded="false">'
            f'  <span class="visually-hidden">{conditional_escape(toggle_text)}</span></a>'
            f'  <ul class="dropdown-menu">{"".join(dropdown_links)}</ul>'
            f"</span>"
        )
    else:
        html = ""

    if not html:
        return '<div class="text-end text-nowrap"></div>' if cell_wrapper else ""

    if cell_wrapper:
        return f'<div class="text-end text-nowrap">{html}</div>'
    return html
