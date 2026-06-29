"""COT rulebook detail panel: enforcement points (hosts and interface NSM links)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.core.display_utils import (
    get_display_template_map,
    render_object_display,
    type_config_display_name_for_ct_id,
)
from netbox_nsm.security.links.object_link_service import (
    is_enforcement_point_host_link,
    is_enforcement_point_iface_nsm_link,
    iter_enforcement_point_links_for_slug,
    object_link_permission,
)
from netbox_nsm.security.actions.panel_link_actions import append_return_url

__all__ = ("build_cot_rulebook_assigned_objects_panel",)


def _host_type_meta(host) -> dict:
    from dcim.models import Device, VirtualDeviceContext
    from virtualization.models import VirtualMachine

    if isinstance(host, Device):
        return {"label": _("Device"), "icon": "mdi-server-network"}
    if isinstance(host, VirtualMachine):
        return {"label": _("VM"), "icon": "mdi-cloud-outline"}
    if isinstance(host, VirtualDeviceContext):
        return {"label": _("VDC"), "icon": "mdi-layers-outline"}
    return {"label": _("Object"), "icon": "mdi-cube-outline"}


def _interfaces_for_host(host):
    from dcim.models import Device, Interface
    from virtualization.models import VirtualMachine, VMInterface

    if isinstance(host, Device):
        return list(Interface.objects.filter(device=host).order_by("name"))
    if isinstance(host, VirtualMachine):
        return list(VMInterface.objects.filter(virtual_machine=host).order_by("name"))
    return []


def _enforcement_point_iface_assign_url(iface, cot_slug: str, return_url: str) -> str:
    ct = ContentType.objects.get_for_model(iface)
    url = (
        reverse(
            "plugins:netbox_nsm:enforcement_point_link_assign",
            kwargs={"slug": cot_slug},
        )
        + f"?ct_id={ct.pk}&obj_id={iface.pk}"
    )
    return append_return_url(url, return_url)


def _enforcement_point_nsm_link_row(
    link,
    return_url: str,
    *,
    can_delete: bool,
    tmpl_map,
    type_label_cache: dict[int, str],
) -> dict:
    policy_obj = link.policy_object
    if policy_obj is None:
        return {
            "type_label": _("Enforcement point"),
            "name": link.rulebook_slug,
            "url": None,
            "edit_url": None,
            "delete_url": None,
        }

    lct = ContentType.objects.get_for_model(policy_obj)
    ct_id = lct.pk
    if ct_id not in type_label_cache:
        type_label_cache[ct_id] = type_config_display_name_for_ct_id(ct_id)

    delete_url = None
    if can_delete:
        delete_url = append_return_url(
            reverse(
                "plugins:netbox_nsm:enforcement_point_link_delete",
                kwargs={"pk": link.pk},
            ),
            return_url,
        )

    url = policy_obj.get_absolute_url() if hasattr(policy_obj, "get_absolute_url") else None
    return {
        "type_label": type_label_cache[ct_id],
        "name": render_object_display(policy_obj, lct.pk, tmpl_map),
        "url": url,
        "edit_url": None,
        "delete_url": delete_url,
    }


def build_cot_rulebook_assigned_objects_panel(cot_slug: str, request) -> dict:
    return_url = request.path if request else reverse(
        "plugins:netbox_nsm:cot_rulebook",
        kwargs={"slug": cot_slug},
    )
    if request:
        return_url = with_branch_query(return_url, request)

    user = request.user if request else None
    add_perm = object_link_permission("add")
    delete_perm = object_link_permission("delete")
    assign_perm = object_link_permission("add")
    can_add = bool(user and add_perm and user.has_perm(add_perm))
    can_delete = bool(user and delete_perm and user.has_perm(delete_perm))
    can_assign_links = bool(user and assign_perm and user.has_perm(assign_perm))

    add_url = reverse(
        "plugins:netbox_nsm:cot_rulebook_bulk_assign",
        kwargs={"slug": cot_slug},
    )
    if request:
        add_url = with_branch_query(add_url, request)

    tmpl_map = get_display_template_map()
    type_label_cache: dict[int, str] = {}

    all_links = list(iter_enforcement_point_links_for_slug(cot_slug))
    iface_nsm_links: dict[tuple[int, int], list] = {}
    for link in all_links:
        if not is_enforcement_point_iface_nsm_link(link):
            continue
        obj = link.netbox_object
        ct = ContentType.objects.get_for_model(obj)
        key = (ct.pk, obj.pk)
        iface_nsm_links.setdefault(key, []).append(link)

    hosts: list[dict] = []
    for link in all_links:
        if not is_enforcement_point_host_link(link):
            continue
        host = link.netbox_object
        if host is None:
            continue

        host_url = (
            host.get_absolute_url() if hasattr(host, "get_absolute_url") else None
        )
        remove_url = None
        if can_delete:
            remove_url = append_return_url(
                reverse(
                    "plugins:netbox_nsm:enforcement_point_link_delete",
                    kwargs={"pk": link.pk},
                ),
                return_url,
            )

        interfaces = []
        for iface in _interfaces_for_host(host):
            iface_ct = ContentType.objects.get_for_model(iface)
            point_links = iface_nsm_links.get((iface_ct.pk, iface.pk), [])

            assign_url = None
            if can_assign_links:
                assign_url = _enforcement_point_iface_assign_url(
                    iface, cot_slug, return_url
                )
                if request:
                    assign_url = with_branch_query(assign_url, request)

            iface_url = (
                iface.get_absolute_url() if hasattr(iface, "get_absolute_url") else None
            )
            link_rows = [
                _enforcement_point_nsm_link_row(
                    point_link,
                    return_url,
                    can_delete=can_delete,
                    tmpl_map=tmpl_map,
                    type_label_cache=type_label_cache,
                )
                for point_link in point_links
            ]
            interfaces.append(
                {
                    "name": str(getattr(iface, "name", iface)),
                    "label": str(iface),
                    "url": iface_url,
                    "link_rows": link_rows,
                    "has_links": bool(link_rows),
                    "assign_url": assign_url,
                }
            )

        linked_interface_count = sum(1 for row in interfaces if row["has_links"])
        type_meta = _host_type_meta(host)
        hosts.append(
            {
                "assignment_id": link.pk,
                "host_name": str(host),
                "host_url": host_url,
                "host_type_label": type_meta["label"],
                "host_type_icon": type_meta["icon"],
                "remove_url": remove_url,
                "interfaces": interfaces,
                "linked_interface_count": linked_interface_count,
                "has_unlinked_interfaces": linked_interface_count < len(interfaces),
            }
        )

    hosts.sort(key=lambda row: row["host_name"].lower())

    return {
        "hosts": hosts,
        "add_url": add_url if can_add else None,
        "can_add": can_add,
        "can_delete": can_delete,
        "can_assign_links": can_assign_links,
        "is_empty": not hosts,
    }
