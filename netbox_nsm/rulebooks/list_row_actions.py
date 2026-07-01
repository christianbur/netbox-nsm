"""Row action buttons for the COT rulebook list."""

from __future__ import annotations

from django.urls import reverse

from netbox_nsm.rulebooks.permissions import can_change_rulebook, can_show_rulebook_delete
from netbox_nsm.rulebooks.rules_tab.cells import _render_actions_cell_html
from netbox_nsm.rulebooks.virtual_cot import is_virtual_cot_rulebook

__all__ = ("render_rulebook_list_row_actions_html",)


def render_rulebook_list_row_actions_html(request, record) -> str:
    if not is_virtual_cot_rulebook(record):
        return ""

    cot = record.cot
    can_edit = can_change_rulebook(request.user, cot)
    can_delete = can_show_rulebook_delete(request.user)
    if not can_edit and not can_delete:
        return ""

    edit_url = reverse(
        "plugins:netbox_nsm:cot_rulebook",
        kwargs={"slug": record.slug},
    )
    if can_edit:
        edit_url = f"{edit_url}?edit=1"
    delete_url = reverse(
        "plugins:netbox_nsm:cot_rulebook_delete",
        kwargs={"slug": record.slug},
    )
    return _render_actions_cell_html(
        edit_url,
        delete_url,
        can_change=can_edit,
        can_delete=can_delete,
    )
