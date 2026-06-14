"""Build Security Panel object-link rows for a single NetBox object."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.core.display_utils import (
    get_display_template_map,
    render_object_display,
    type_config_display_name_for_ct_id,
)
from netbox_nsm.objects.object_link_service import iter_links_for_object
from netbox_nsm.security.panel_link_actions import object_link_action_urls

__all__ = ("build_object_link_rows",)


def build_object_link_rows(obj, return_url: str | None) -> list[dict]:
    """Return object-link rows for *obj* (same data as the Security Panel link table)."""
    if obj is None or not getattr(obj, "pk", None):
        return []

    tmpl_map = get_display_template_map()
    type_label_cache: dict[int, str] = {}

    def _type_label(content_type) -> str:
        ct_id = content_type.pk
        if ct_id not in type_label_cache:
            type_label_cache[ct_id] = type_config_display_name_for_ct_id(ct_id)
        return type_label_cache[ct_id]

    rows: list[dict] = []
    link_pairs = list(iter_links_for_object(obj))

    for link, direction in link_pairs:
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        lct = ContentType.objects.get_for_model(linked)
        action_urls = object_link_action_urls(link, return_url)
        url = linked.get_absolute_url() if hasattr(linked, "get_absolute_url") else None
        rows.append(
            {
                "type_label": _type_label(lct),
                "name": render_object_display(linked, lct.pk, tmpl_map),
                "url": url,
                "edit_url": action_urls.get("edit_url"),
                "delete_url": action_urls.get("delete_url"),
            }
        )

    rows.sort(key=lambda row: (row["type_label"].lower(), row["name"].lower()))
    return rows
