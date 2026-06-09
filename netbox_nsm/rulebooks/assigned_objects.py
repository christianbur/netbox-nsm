"""COT rulebook detail panel: assigned hosts and Security Panel interface links."""

from __future__ import annotations

from django.db.models import prefetch_related_objects
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.security.panel_link_actions import append_return_url, object_link_assign_url
from netbox_nsm.security.panel_links import build_object_link_rows

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


def build_cot_rulebook_assigned_objects_panel(cot_slug: str, request) -> dict:
    return_url = request.path if request else reverse(
        "plugins:netbox_nsm:cot_rulebook",
        kwargs={"slug": cot_slug},
    )
    if request:
        return_url = with_branch_query(return_url, request)

    user = request.user if request else None
    can_add = bool(user and user.has_perm("netbox_nsm.add_rulebookassignment"))
    can_delete = bool(user and user.has_perm("netbox_nsm.delete_rulebookassignment"))
    can_assign_links = bool(user and user.has_perm("netbox_nsm.add_objectlink"))

    add_url = reverse(
        "plugins:netbox_nsm:cot_rulebook_bulk_assign",
        kwargs={"slug": cot_slug},
    )
    if request:
        add_url = with_branch_query(add_url, request)

    hosts: list[dict] = []
    assignments = list(
        CotRulebookAssignment.objects.filter(cot_slug=cot_slug)
        .select_related("assigned_object_type")
        .order_by("assigned_object_type__model", "assigned_object_id")
    )
    prefetch_related_objects(assignments, "assigned_object")

    for assignment in assignments:
        host = assignment.assigned_object
        if host is None:
            continue

        host_url = (
            host.get_absolute_url() if hasattr(host, "get_absolute_url") else None
        )
        remove_url = None
        if can_delete:
            remove_url = append_return_url(
                reverse(
                    "plugins:netbox_nsm:cotrulebookassignment_delete",
                    kwargs={"pk": assignment.pk},
                ),
                return_url,
            )

        interfaces = []
        for iface in _interfaces_for_host(host):
            assign_url = (
                object_link_assign_url(iface, return_url) if can_assign_links else None
            )
            if request and assign_url:
                assign_url = with_branch_query(assign_url, request)
            iface_url = (
                iface.get_absolute_url() if hasattr(iface, "get_absolute_url") else None
            )
            link_rows = build_object_link_rows(iface, return_url)
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
                "assignment_id": assignment.pk,
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
