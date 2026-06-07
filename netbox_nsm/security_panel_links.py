"""Build Security Panel ObjectLink rows for a single NetBox object."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import prefetch_related_objects

from netbox_nsm.display_utils import (
    get_display_template_map,
    render_object_display,
    type_config_display_name_for_ct_id,
)
from netbox_nsm.models import ObjectLink
from netbox_nsm.panel_link_actions import object_link_action_urls

__all__ = ("build_object_link_rows",)


def build_object_link_rows(obj, return_url: str | None) -> list[dict]:
    """Return ObjectLink rows for *obj* (same data as the Security Panel link table)."""
    if obj is None or not getattr(obj, "pk", None):
        return []

    ct = ContentType.objects.get_for_model(obj)
    tmpl_map = get_display_template_map()
    type_label_cache: dict[int, str] = {}

    def _type_label(content_type) -> str:
        ct_id = content_type.pk
        if ct_id not in type_label_cache:
            type_label_cache[ct_id] = type_config_display_name_for_ct_id(ct_id)
        return type_label_cache[ct_id]

    rows: list[dict] = []

    fwd_links = list(
        ObjectLink.objects.filter(object_a_type=ct, object_a_id=obj.pk)
        .select_related("object_b_type")
        .order_by("created")
    )
    rev_links = list(
        ObjectLink.objects.filter(object_b_type=ct, object_b_id=obj.pk)
        .select_related("object_a_type")
        .order_by("created")
    )
    prefetch_related_objects(fwd_links, "object_b")
    prefetch_related_objects(rev_links, "object_a")

    for link in fwd_links:
        linked = link.object_b
        if linked is None:
            continue
        lct = link.object_b_type
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

    for link in rev_links:
        linked = link.object_a
        if linked is None:
            continue
        lct = link.object_a_type
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
