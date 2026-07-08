"""Device/VM Security Panel: per-interface NSM analysis."""

from __future__ import annotations

from netbox_nsm.core.interface_parent import (
    interface_parent_host_payload,
    prefetch_interface_parents,
)
from netbox_nsm.security.links.link_rows import build_object_link_rows

__all__ = ("build_host_interface_analysis",)


def _interfaces_for_host(host):
    from dcim.models import Device, Interface
    from virtualization.models import VirtualMachine, VMInterface

    if isinstance(host, Device):
        return list(Interface.objects.filter(device=host).order_by("name"))
    if isinstance(host, VirtualMachine):
        return list(VMInterface.objects.filter(virtual_machine=host).order_by("name"))
    return []


def build_host_interface_analysis(host, *, request, panel_url) -> list[dict]:
    """Return interfaces on *host* that have NSM object links."""
    from dcim.models import Device
    from virtualization.models import VirtualMachine

    if not isinstance(host, (Device, VirtualMachine)):
        return []

    def _branch_url(url: str) -> str:
        if not url:
            return ""
        from netbox_nsm.core.branch_urls import with_branch_query

        return with_branch_query(url, request) if request else url

    interfaces_out: list[dict] = []
    interfaces = list(_interfaces_for_host(host))
    prefetch_interface_parents(interfaces)

    for iface in interfaces:
        link_rows = build_object_link_rows(iface, request.path if request else "/")
        if not link_rows:
            continue

        iface_url = (
            iface.get_absolute_url() if hasattr(iface, "get_absolute_url") else None
        )

        parent_payload = interface_parent_host_payload(iface)
        parent_url = parent_payload.get("parent_url") or ""
        if parent_url:
            parent_url = _branch_url(parent_url)

        interfaces_out.append(
            {
                "pk": iface.pk,
                "name": str(getattr(iface, "name", iface)),
                "url": iface_url,
                "parent_url": parent_url,
                "parent_name": parent_payload.get("parent_name") or "",
                "entry_count": len(link_rows),
                "link_rows": link_rows,
            }
        )

    return interfaces_out
