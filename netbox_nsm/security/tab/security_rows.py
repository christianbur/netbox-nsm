"""Convert combined-tab rows into Security tab link payloads."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _

from netbox_nsm.security.tab.combined import (
    _JunctionField,
    _OutgoingFieldProxy,
    _get_field_value,
    _get_linked_custom_objects,
)
from netbox_nsm.security.tab.value_groups import UNGROUPED_KEY, nsm_object_group_value

__all__ = ("append_cot_reference_link_groups", "count_cot_reference_links")


def _display_name(value) -> str:
    if value is None:
        return ""
    return str(value)


def _row_type_key(row_obj) -> tuple[str, str]:
    ct = ContentType.objects.get_for_model(row_obj)
    return f"{ct.app_label}__{ct.model}", ct


def _cot_edit_urls(cot_obj, return_url: str) -> dict:
    slug = getattr(getattr(cot_obj, "custom_object_type", None), "slug", None)
    if not slug or not getattr(cot_obj, "pk", None):
        return {}
    try:
        from django.urls import reverse

        from netbox_nsm.security.actions.panel_link_actions import append_return_url

        edit = reverse(
            "plugins:netbox_custom_objects:customobject_edit",
            kwargs={"custom_object_type": slug, "pk": cot_obj.pk},
        )
        delete = reverse(
            "plugins:netbox_custom_objects:customobject_delete",
            kwargs={"custom_object_type": slug, "pk": cot_obj.pk},
        )
        return {
            "edit_url": append_return_url(edit, return_url),
            "delete_url": append_return_url(delete, return_url),
        }
    except Exception:
        return {}


def _payload_for_row(
    row_obj,
    field,
    host_obj,
    *,
    panel_link_payload,
    tmpl_map,
    type_label_fn,
    return_url: str,
):
    type_key, lct = _row_type_key(row_obj)
    value = _get_field_value(row_obj, field)
    value_key, value_label = nsm_object_group_value(row_obj)

    extra = {
        "source": "cot_reference",
        "source_label": _("Custom object field"),
        "comment": "",
    }

    if getattr(field, "is_junction_row", False):
        via_obj = getattr(field, "via_obj", None)
        extra["comment"] = str(field)
        extra["is_junction_row"] = True
        extra["via_obj_id"] = getattr(via_obj, "pk", None)
        extra.update(_cot_edit_urls(via_obj, return_url))
        if isinstance(value, list):
            value_label = ", ".join(_display_name(v) for v in value[:3])
            value_key = value_label or UNGROUPED_KEY
        elif value is not None:
            value_label = _display_name(value)
            value_key = value_label
    elif isinstance(field, _OutgoingFieldProxy):
        host_ct = ContentType.objects.get_for_model(host_obj)
        row_obj = host_obj
        lct = host_ct
        type_key = f"{host_ct.app_label}__{host_ct.model}"
        extra["comment"] = str(field)
        extra["is_outgoing_row"] = True
        if isinstance(value, list):
            value_label = ", ".join(_display_name(v) for v in value[:3])
            value_key = value_label or UNGROUPED_KEY
        elif value is not None:
            value_label = _display_name(value)
            value_key = value_label
        extra.update(_cot_edit_urls(host_obj, return_url))
    else:
        if isinstance(value, list):
            value_label = ", ".join(_display_name(v) for v in value[:3])
            value_key = value_label or UNGROUPED_KEY
        elif value is not None and field.type == "object":
            value_label = _display_name(value)
            value_key = value_label

    return type_key, type_label_fn(lct), panel_link_payload(
        row_obj,
        lct,
        tmpl_map,
        value_key=value_key,
        value_label=value_label,
        **extra,
    )


def append_cot_reference_link_groups(
    links_by_type: dict,
    obj,
    request,
    *,
    panel_link_payload,
    tmpl_map,
    type_label_fn,
    return_url: str,
) -> int:
    """Merge PR #482-style COT reference rows into ``links_by_type``."""
    user = getattr(request, "user", None) if request is not None else None
    added = 0
    seen: set[tuple[str, int]] = set()

    for row_obj, field in _get_linked_custom_objects(obj, user=user):
        type_key, type_label, payload = _payload_for_row(
            row_obj,
            field,
            obj,
            panel_link_payload=panel_link_payload,
            tmpl_map=tmpl_map,
            type_label_fn=type_label_fn,
            return_url=return_url,
        )
        dedupe = (type_key, payload.get("obj_id") or 0, payload.get("comment", ""))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        bucket = links_by_type.setdefault(
            type_key,
            {"label": type_label, "objects": []},
        )
        bucket["objects"].append(payload)
        added += 1
    return added


def count_cot_reference_links(obj, *, user=None) -> int:
    return len(_get_linked_custom_objects(obj, user=user))
