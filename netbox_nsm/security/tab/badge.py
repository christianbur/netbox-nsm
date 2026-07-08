"""Security tab badge counts (shown when non-zero)."""

from __future__ import annotations

from netbox_nsm.security.tab.eligibility import is_security_tab_eligible
from netbox_nsm.security.tab.security_rows import count_security_link_table_rows

__all__ = ("count_security_tab_badge",)


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

    Link-table rows use the same dedupe rules as ``build_security_tab_context``.
    """
    if obj is None or not getattr(obj, "pk", None):
        return 0
    if not is_security_tab_eligible(obj):
        return 0

    total = count_security_link_table_rows(obj) + _count_interface_analysis_entries(obj)
    return total
