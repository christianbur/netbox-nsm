"""Security tab badge counts (shown when non-zero)."""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from netbox_nsm.objects.object_link_service import iter_links_for_object
from netbox_nsm.security.panel import build_cot_security_panel_groups

__all__ = ("count_security_tab_badge",)


def _count_object_links(obj) -> int:
    seen: set[tuple[str, int]] = set()
    total = 0
    for link, direction in iter_links_for_object(obj):
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        lct = ContentType.objects.get_for_model(linked)
        dedupe = (f"{lct.app_label}__{lct.model}", linked.pk)
        if dedupe in seen:
            continue
        seen.add(dedupe)
        total += 1
    return total


def _count_extra_link_refs(obj) -> int:
    """Address IPAM FK and group M2M rows not covered by ObjectLink iteration."""
    total = 0
    try:
        from ipam.models import IPAddress, IPRange, Prefix

        from netbox_nsm.objects.address_ipam_fk import (
            get_nsm_address_model,
            is_nsm_address_object,
            iter_address_ipam_fk_refs,
            iter_addresses_for_ipam_object,
        )

        if isinstance(obj, (IPAddress, Prefix, IPRange)):
            addr_model = get_nsm_address_model()
            if addr_model is not None:
                total += sum(1 for _pair in iter_addresses_for_ipam_object(obj))

        if is_nsm_address_object(obj):
            total += sum(1 for _ref in iter_address_ipam_fk_refs(obj))
    except Exception:
        pass

    try:
        from netbox_nsm.objects.group_m2m import iter_group_m2m_relations

        total += sum(1 for _relation in iter_group_m2m_relations(obj))
    except Exception:
        pass

    return total


def _count_enforcement_entries(obj) -> int:
    try:
        from netbox_nsm.security.enforcement_point_panel import (
            build_enforcement_point_panel,
        )

        panel = build_enforcement_point_panel(
            obj,
            request=None,
            panel_url=lambda url: url,
            return_url="/",
        )
    except Exception:
        return 0
    if not panel:
        return 0
    return int(panel.get("count") or 0)


def _count_interface_analysis_entries(obj) -> int:
    try:
        from dcim.models import Device
        from virtualization.models import VirtualMachine

        from netbox_nsm.security.host_interface_analysis import (
            build_host_interface_analysis,
        )

        if not isinstance(obj, (Device, VirtualMachine)):
            return 0
        return len(
            build_host_interface_analysis(
                obj,
                request=None,
                panel_url=lambda url: url,
            )
        )
    except Exception:
        return 0


def count_security_tab_badge(obj) -> int:
    """
    Return a non-zero badge when the Security tab has content.

    Uses count-only rulebook lookups and deduped link iteration — no full panel
    payload is built.
    """
    if obj is None or not getattr(obj, "pk", None):
        return 0

    ct = ContentType.objects.get_for_model(obj)
    panel_data = build_cot_security_panel_groups(
        ct,
        obj.pk,
        panel_url=lambda url: url,
    )
    total = (
        int(panel_data.get("unique_rules_total") or 0)
        + _count_object_links(obj)
        + _count_extra_link_refs(obj)
        + _count_enforcement_entries(obj)
        + _count_interface_analysis_entries(obj)
    )
    return total
