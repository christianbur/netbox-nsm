"""Convert combined-tab rows into Security tab link payloads."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext as _

from netbox_nsm.security.tab.combined import (
    _JunctionField,
    _OutgoingFieldProxy,
    _get_field_value,
    _get_linked_custom_objects,
    _type_label,
    is_untransformed_junction_row,
)
from netbox_nsm.security.tab.value_groups import UNGROUPED_KEY, nsm_object_group_value

_CUSTOM_OBJECTS_APP = "netbox_custom_objects"

__all__ = (
    "append_cot_reference_link_groups",
    "count_cot_reference_links",
    "count_security_link_table_rows",
)


def _display_name(value) -> str:
    if value is None:
        return ""
    return str(value)


def _cot_type_display_label(cot) -> str:
    """Readable Security-tab Type label for a custom object type."""
    if cot is None:
        return ""
    slug = (getattr(cot, "slug", None) or "").strip()
    if slug.startswith("nsm_rb_"):
        from netbox_nsm.rulebooks.create import cot_rulebook_display_label

        return cot_rulebook_display_label(cot)
    verbose = (getattr(cot, "verbose_name", None) or "").strip()
    if verbose:
        return verbose
    name = (getattr(cot, "name", None) or "").strip()
    if name and name != slug:
        return name
    return name or slug or str(cot)


def _object_absolute_url(obj) -> str:
    if obj is None:
        return ""
    url_fn = getattr(obj, "get_absolute_url", None)
    if not callable(url_fn):
        return ""
    try:
        return url_fn() or ""
    except Exception:
        return ""


def _value_item(obj) -> dict:
    label = _display_name(obj)
    return {"label": label, "url": _object_absolute_url(obj)}


def _list_value_items(value) -> list[dict]:
    return [_value_item(item) for item in value]


def _apply_field_value(value) -> tuple[str, str, list[dict]]:
    """Return ``(value_key, value_label, value_items)`` for a field value."""
    if isinstance(value, list):
        items = _list_value_items(value)
        label = ", ".join(item["label"] for item in items)
        return label or UNGROUPED_KEY, label, items
    if value is not None:
        item = _value_item(value)
        label = item["label"]
        if not label:
            return UNGROUPED_KEY, "", []
        return label, label, [item]
    return UNGROUPED_KEY, "", []


def _list_value_key_label(value) -> tuple[str, str]:
    """Return ``(value_key, value_label)`` for a list field value."""
    _key, label, _items = _apply_field_value(value)
    return _key, label


def _row_type_key(row_obj) -> tuple[str, ContentType]:
    ct = ContentType.objects.get_for_model(row_obj)
    return f"{ct.app_label}__{ct.model}", ct


def _junction_via_action_urls(via_obj, return_url: str) -> dict:
    """Action URLs for the junction ``via`` row (policy link or generic COT)."""
    from netbox_nsm.security.links.object_link_service import (
        ObjectLinkRecord,
        is_policy_link_instance,
    )
    from netbox_nsm.security.actions.panel_link_actions import object_link_action_urls
    from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag

    cot = getattr(via_obj, "custom_object_type", None)
    if (
        via_obj is not None
        and cot_link_table_flag(cot)
        and is_policy_link_instance(via_obj)
    ):
        return object_link_action_urls(
            ObjectLinkRecord.from_instance(via_obj),
            return_url,
        )
    return _cot_action_urls(via_obj, return_url)


def _cot_action_urls(cot_obj, return_url: str) -> dict:
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
        changelog = reverse(
            "plugins:netbox_custom_objects:customobject_changelog",
            kwargs={"custom_object_type": slug, "pk": cot_obj.pk},
        )
        return {
            "edit_url": append_return_url(edit, return_url),
            "delete_url": append_return_url(delete, return_url),
            "changelog_url": append_return_url(changelog, return_url),
            "cot_slug": slug,
            "is_cot_row": True,
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
    value_items: list[dict] = []

    extra = {
        "source": "cot_reference",
        "source_label": _("Custom object field"),
        "field_label": str(field),
        "row_type_label": type_label_fn(lct),
    }

    if getattr(field, "is_junction_row", False):
        via_obj = getattr(field, "via_obj", None)
        extra["is_junction_row"] = True
        extra["row_type_label"] = getattr(field, "type_label", None) or extra["row_type_label"]
        extra["via_obj_url"] = (
            via_obj.get_absolute_url()
            if via_obj is not None and hasattr(via_obj, "get_absolute_url")
            else ""
        )
        extra["via_obj_name"] = _display_name(via_obj)
        extra.update(_junction_via_action_urls(via_obj, return_url))
        extra["row_type_filter_key"] = type_key
        if isinstance(value, list) or value is not None:
            value_key, value_label, value_items = _apply_field_value(value)
    elif isinstance(field, _OutgoingFieldProxy):
        host_ct = ContentType.objects.get_for_model(host_obj)
        row_obj = host_obj
        lct = host_ct
        type_key = f"{host_ct.app_label}__{host_ct.model}"
        extra["is_outgoing_row"] = True
        extra["row_type_label"] = getattr(field, "type_label", None) or _type_label(host_obj)
        if isinstance(value, list) or value is not None:
            value_key, value_label, value_items = _apply_field_value(value)
        extra.update(_cot_action_urls(host_obj, return_url))
    else:
        cot = getattr(field, "custom_object_type", None)
        if cot is not None:
            extra["row_type_label"] = _cot_type_display_label(cot)
        if isinstance(value, list) or (value is not None and field.type == "object"):
            value_key, value_label, value_items = _apply_field_value(value)
        extra.update(_cot_action_urls(row_obj, return_url))

    if "row_type_filter_key" not in extra:
        extra["row_type_filter_key"] = (
            extra.get("cot_slug") or extra.get("row_type_label") or type_key
        )

    return type_key, type_label_fn(lct), panel_link_payload(
        row_obj,
        lct,
        tmpl_map,
        value_key=value_key,
        value_label=value_label,
        value_items=value_items,
        **extra,
    )


def _junction_endpoint_visible(row_obj, field) -> bool:
    if not getattr(field, "is_junction_row", False):
        return True
    try:
        from netbox_nsm.type_metadata.config import is_linkable_content_type

        endpoint_ct = ContentType.objects.get_for_model(row_obj)
        if endpoint_ct.app_label == _CUSTOM_OBJECTS_APP:
            return is_linkable_content_type(endpoint_ct.pk)
    except Exception:
        return False
    return True


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
    seen: set[tuple] = set()

    for row_obj, field in _get_linked_custom_objects(obj, user=user):
        if is_untransformed_junction_row(row_obj, field):
            continue
        if not _junction_endpoint_visible(row_obj, field):
            continue
        type_key, _type_label, payload = _payload_for_row(
            row_obj,
            field,
            obj,
            panel_link_payload=panel_link_payload,
            tmpl_map=tmpl_map,
            type_label_fn=type_label_fn,
            return_url=return_url,
        )
        dedupe = (type_key, payload.get("obj_id") or 0, payload.get("field_label", ""))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        group_label = payload.get("row_type_label") or _type_label
        bucket = links_by_type.setdefault(
            type_key,
            {"label": group_label, "objects": []},
        )
        bucket["objects"].append(payload)
        added += 1
    return added


def _iter_deduped_cot_reference_rows(obj, *, user=None):
    """Yield COT reference rows using the same dedupe rules as the link table."""
    seen: set[tuple] = set()
    for row_obj, field in _get_linked_custom_objects(obj, user=user):
        if is_untransformed_junction_row(row_obj, field):
            continue
        if not _junction_endpoint_visible(row_obj, field):
            continue
        type_key, _lct = _row_type_key(row_obj)
        dedupe = (type_key, getattr(row_obj, "pk", None) or 0, str(field))
        if dedupe in seen:
            continue
        seen.add(dedupe)
        yield row_obj, field


def count_cot_reference_links(obj, *, user=None) -> int:
    return sum(1 for _row in _iter_deduped_cot_reference_rows(obj, user=user))


def _count_ipam_fk_security_rows(obj, existing_urls: set[str]) -> int:
    added = 0
    try:
        from ipam.models import IPAddress, IPRange, Prefix

        from netbox_nsm.addresses.address_ipam_fk import (
            get_nsm_address_model,
            is_nsm_address_object,
            iter_address_ipam_fk_refs,
            iter_addresses_for_ipam_object,
        )

        if isinstance(obj, (IPAddress, Prefix, IPRange)):
            addr_model = get_nsm_address_model()
            if addr_model is not None:
                for addr_obj, _fk_field_name in iter_addresses_for_ipam_object(obj):
                    addr_url = (
                        addr_obj.get_absolute_url()
                        if hasattr(addr_obj, "get_absolute_url")
                        else "#"
                    )
                    if addr_url in existing_urls:
                        continue
                    existing_urls.add(addr_url)
                    added += 1

        if is_nsm_address_object(obj):
            for ref in iter_address_ipam_fk_refs(obj):
                ipam_obj = ref.ipam_obj
                ipam_url = (
                    ipam_obj.get_absolute_url()
                    if hasattr(ipam_obj, "get_absolute_url")
                    else "#"
                )
                if ipam_url in existing_urls:
                    continue
                existing_urls.add(ipam_url)
                added += 1
    except Exception:
        pass
    return added


def _count_group_m2m_security_rows(obj, existing_urls: set[str]) -> int:
    added = 0
    try:
        from netbox_nsm.objects.group_m2m import iter_group_m2m_relations

        for relation in iter_group_m2m_relations(obj):
            related = relation.related
            url = (
                related.get_absolute_url()
                if hasattr(related, "get_absolute_url")
                else "#"
            )
            if url in existing_urls:
                continue
            existing_urls.add(url)
            added += 1
    except Exception:
        pass
    return added


def count_security_link_table_rows(obj, *, user=None) -> int:
    """Count Security tab link-table rows (matches ``build_security_tab_context``)."""
    total = 0
    existing_urls: set[str] = set()

    for row_obj, field in _iter_deduped_cot_reference_rows(obj, user=user):
        if not _junction_endpoint_visible(row_obj, field):
            continue
        total += 1
        if hasattr(row_obj, "get_absolute_url"):
            existing_urls.add(row_obj.get_absolute_url())

    total += _count_ipam_fk_security_rows(obj, existing_urls)
    total += _count_group_m2m_security_rows(obj, existing_urls)
    return total
