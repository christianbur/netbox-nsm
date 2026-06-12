"""Device/VM Security Panel: per-interface NSM analysis."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.core.branch_urls import with_branch_query
from netbox_nsm.core.interface_parent import (
    interface_parent_host_payload,
    prefetch_interface_parents,
)
from netbox_nsm.rulebooks.assigned_objects import _interfaces_for_host
from netbox_nsm.security.panel import build_cot_security_panel_groups
from netbox_nsm.security.panel_links import build_object_link_rows

__all__ = ("build_host_interface_analysis",)


def build_host_interface_analysis(host, *, request, panel_url) -> list[dict]:
    """Return interfaces on *host* that have NSM object links and/or rulebook refs."""
    from dcim.models import Device
    from virtualization.models import VirtualMachine

    if not isinstance(host, (Device, VirtualMachine)):
        return []

    return_url = request.path if request else "/"

    def _branch_url(url: str) -> str:
        if not url:
            return ""
        return with_branch_query(url, request) if request else url

    interfaces_out: list[dict] = []
    interfaces = list(_interfaces_for_host(host))
    prefetch_interface_parents(interfaces)

    for iface in interfaces:
        ct = ContentType.objects.get_for_model(iface)
        link_rows = build_object_link_rows(iface, return_url)
        panel_data = build_cot_security_panel_groups(
            ct,
            iface.pk,
            panel_url=panel_url,
        )
        rulebook_groups = panel_data["rulebook_groups"]
        unique_rules_total = panel_data["unique_rules_total"]

        if not link_rows and unique_rules_total == 0:
            continue

        iface_url = (
            iface.get_absolute_url() if hasattr(iface, "get_absolute_url") else None
        )
        api_url = _branch_url(
            reverse("plugins:netbox_nsm:object_rules_api")
            + f"?ct_id={ct.pk}&obj_id={iface.pk}"
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
                "entry_count": len(link_rows) + unique_rules_total,
                "link_rows": link_rows,
                "rulebook_groups": rulebook_groups,
                "unique_rules_total": unique_rules_total,
                "api_url": api_url,
            }
        )

    return interfaces_out
