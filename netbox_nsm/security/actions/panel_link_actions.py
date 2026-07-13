"""Security Panel row action URLs (edit/remove ObjectLink assignments)."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from django.urls import NoReverseMatch, reverse

__all__ = (
    "address_ipam_fk_action_urls",
    "address_ipam_fk_clear_url",
    "address_ipam_fk_ref_action_urls",
    "append_return_url",
    "find_object_link_between",
    "group_m2m_action_urls",
    "group_m2m_edit_url",
    "object_link_action_urls",
    "object_link_assign_url",
    "object_link_panel_delete_url",
    "object_link_panel_edit_url",
    "panel_object_edit_url",
)


def append_return_url(url: str, return_url: str | None) -> str:
    if not return_url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}return_url={quote(return_url, safe='')}"


def panel_object_edit_url(obj, return_url: str | None = None) -> str | None:
    """Edit URL for a NetBox or Custom Object instance."""
    if obj is None:
        return None
    try:
        if hasattr(obj, "custom_object_type"):
            from netbox_custom_objects.utilities import get_viewname

            viewname = get_viewname(obj, "edit")
            url = reverse(
                viewname,
                kwargs={
                    "pk": obj.pk,
                    "custom_object_type": obj.custom_object_type.slug,
                },
            )
        else:
            from utilities.views import get_viewname

            viewname = get_viewname(obj, "edit")
            url = reverse(viewname, kwargs={"pk": obj.pk})
    except (NoReverseMatch, AttributeError, TypeError, ValueError):
        return None
    return append_return_url(url, return_url)


def object_link_action_urls(link, return_url: str | None) -> dict:
    return {
        "edit_url": append_return_url(
            reverse(
                "plugins:netbox_nsm:object_link_edit",
                kwargs={"pk": link.pk},
            ),
            return_url,
        ),
        "delete_url": append_return_url(
            reverse(
                "plugins:netbox_nsm:object_link_delete",
                kwargs={"pk": link.pk},
            ),
            return_url,
        ),
    }


def find_object_link_between(object_a, object_b):
    """Return a COT object link between two objects, if any."""
    from netbox_nsm.security.links.object_link_service import find_link_between

    return find_link_between(object_a, object_b)


def object_link_assign_url(
    object_a,
    return_url: str | None,
    *,
    object_b=None,
    link=None,
) -> str:
    """COT add form URL with Object A/B prefill from the Security panel page object."""
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.security.links.cot_link_schema import (
        get_object_link_cot_slug,
        get_object_link_schema,
    )
    from netbox_nsm.security.links.object_link_service import (
        classify_link_endpoints,
        link_name_for_endpoints,
    )
    from netbox_nsm.security.object_link_cot_form import object_link_field_prefix_for_ct

    params: dict[str, str | int] = {"status": "active"}
    schema = get_object_link_schema()

    def _set_prefill(field_prefix: str, ct_pk: int, obj_pk: int, *, legacy_role: str) -> None:
        # Legacy query keys are kept for compatibility with existing add-form prefill hooks.
        if legacy_role == "a":
            params["ct_id"] = ct_pk
            params["obj_id"] = obj_pk
            params["object_a_type_id"] = ct_pk
            params["object_a_id"] = obj_pk
        else:
            params["object_b_type_id"] = ct_pk
            params["object_b_id"] = obj_pk
        # Direct polymorphic field prefill works even when hook-based mapping is bypassed.
        params[f"{field_prefix}__ct"] = ct_pk
        params[f"{field_prefix}__obj"] = obj_pk

    if object_b is not None:
        netbox, policy = classify_link_endpoints(object_a, object_b)
        netbox_ct = ContentType.objects.get_for_model(netbox)
        policy_ct = ContentType.objects.get_for_model(policy)
        host_prefix = schema.host_field if schema is not None else "netbox_object"
        security_prefix = schema.security_field if schema is not None else "security_object"
        _set_prefill(host_prefix, int(netbox_ct.pk), int(netbox.pk), legacy_role="a")
        _set_prefill(security_prefix, int(policy_ct.pk), int(policy.pk), legacy_role="b")
        params["name"] = link_name_for_endpoints(netbox, policy)
    else:
        ct = ContentType.objects.get_for_model(object_a)
        if object_link_field_prefix_for_ct(ct.pk) == "security_object":
            field_prefix = schema.security_field if schema is not None else "security_object"
            _set_prefill(field_prefix, int(ct.pk), int(object_a.pk), legacy_role="b")
        else:
            field_prefix = schema.host_field if schema is not None else "netbox_object"
            _set_prefill(field_prefix, int(ct.pk), int(object_a.pk), legacy_role="a")
        params["name"] = str(object_a)[:200]

    if link is not None and link.comment:
        params["comments"] = link.comment
    if return_url:
        params["return_url"] = return_url
    query = urlencode(params, quote_via=quote)
    link_cot_slug = get_object_link_cot_slug()
    if not link_cot_slug:
        raise NoReverseMatch("link-table COT is not deployed")
    base = reverse(
        "plugins:netbox_custom_objects:customobject_add",
        kwargs={"custom_object_type": link_cot_slug},
    )
    return f"{base}?{query}"


def object_link_panel_edit_url(object_a, object_b, return_url: str | None) -> str:
    """
    Edit URL for a Security Panel assignment row.

    Uses ObjectLink edit when a link exists; otherwise opens Assign Link
    pre-filled with Object A (page object) and Object B (linked row).
    """
    link = find_object_link_between(object_a, object_b)
    if link is not None:
        return object_link_action_urls(link, return_url)["edit_url"]
    return object_link_assign_url(object_a, return_url, object_b=object_b)


def object_link_panel_delete_url(
    object_a,
    object_b,
    return_url: str | None,
    *,
    fallback: str | None = None,
) -> str | None:
    """
    Delete URL for a Security Panel assignment row.

    Uses ObjectLink delete confirmation when a link exists; otherwise falls
    back to a type-specific remove URL (e.g. IPAM FK clear, group M2M remove).
    """
    link = find_object_link_between(object_a, object_b)
    if link is not None:
        return object_link_action_urls(link, return_url)["delete_url"]
    return fallback


def address_ipam_fk_clear_url(
    addr_obj,
    field_name: str,
    return_url: str | None,
) -> str:
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.addresses.address_ipam_fk import NSM_ADDRESSES_SLUG

    addr_ct = ContentType.objects.get_for_model(addr_obj)
    params = urlencode(
        {
            "addr_ct_id": addr_ct.pk,
            "addr_id": addr_obj.pk,
            "field": field_name,
            "return_url": return_url or "/",
        }
    )
    return (
        reverse(
            "plugins:netbox_nsm:address_ipam_fk_clear",
            kwargs={"slug": NSM_ADDRESSES_SLUG},
        )
        + f"?{params}"
    )


def address_ipam_fk_ref_action_urls(
    page_obj,
    addr_obj,
    field_name: str,
    return_url: str | None,
) -> dict:
    """Action URLs when an IPAM page lists a referencing nsm_addresses row."""
    return {
        "edit_url": object_link_panel_edit_url(page_obj, addr_obj, return_url),
        "delete_url": object_link_panel_delete_url(
            page_obj,
            addr_obj,
            return_url,
            fallback=address_ipam_fk_clear_url(addr_obj, field_name, return_url),
        ),
    }


def address_ipam_fk_action_urls(
    addr_obj,
    field_name: str,
    linked_ipam_obj,
    return_url: str | None,
) -> dict:
    """Action URLs when an nsm_addresses page lists an IPAM FK target."""
    return {
        "edit_url": object_link_panel_edit_url(addr_obj, linked_ipam_obj, return_url),
        "delete_url": object_link_panel_delete_url(
            addr_obj,
            linked_ipam_obj,
            return_url,
            fallback=address_ipam_fk_clear_url(addr_obj, field_name, return_url),
        ),
    }


def group_m2m_edit_url(
    group_obj,
    member_obj,
    return_url: str | None,
) -> str | None:
    if group_obj is None or member_obj is None:
        return None
    from django.contrib.contenttypes.models import ContentType

    group_ct = ContentType.objects.get_for_model(group_obj)
    member_ct = ContentType.objects.get_for_model(member_obj)
    params = urlencode(
        {
            "group_ct_id": group_ct.pk,
            "group_id": group_obj.pk,
            "member_ct_id": member_ct.pk,
            "member_id": member_obj.pk,
            "return_url": return_url or "/",
        }
    )
    return reverse("plugins:netbox_nsm:group_m2m_edit") + f"?{params}"


def group_m2m_remove_url(
    group_obj,
    member_obj,
    return_url: str | None,
) -> str | None:
    if group_obj is None or member_obj is None:
        return None
    from django.contrib.contenttypes.models import ContentType

    group_ct = ContentType.objects.get_for_model(group_obj)
    member_ct = ContentType.objects.get_for_model(member_obj)
    params = urlencode(
        {
            "group_ct_id": group_ct.pk,
            "group_id": group_obj.pk,
            "member_ct_id": member_ct.pk,
            "member_id": member_obj.pk,
            "return_url": return_url or "/",
        }
    )
    return reverse("plugins:netbox_nsm:group_m2m_remove") + f"?{params}"


def group_m2m_action_urls(
    relation,
    return_url: str | None,
    *,
    page_obj=None,
) -> dict:
    """Action URLs for a group M2M Security Panel row."""
    remove_url = group_m2m_remove_url(
        relation.remove_group,
        relation.remove_member,
        return_url,
    )
    delete_url = remove_url
    if page_obj is not None:
        delete_url = object_link_panel_delete_url(
            page_obj,
            relation.related,
            return_url,
            fallback=remove_url,
        )
    return {
        "edit_url": group_m2m_edit_url(
            relation.remove_group,
            relation.remove_member,
            return_url,
        ),
        "delete_url": delete_url,
    }
