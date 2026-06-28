
"""Navigation reference links for address tree nodes."""
from __future__ import annotations
from django.utils.translation import gettext as _
import netbox_nsm.analysis._lazy_api as _hub

def _navigation_ref(label, obj) -> dict | None:
    if obj is None:
        return None
    url = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else None
    if not url:
        return None
    return {
        "label": label,
        "name": str(getattr(obj, "name", obj)),
        "url": url,
    }


_ADDR_NAV_REF_LIMIT = 15


def _addr_nav_append(refs, seen_urls, ref, *, limit=_ADDR_NAV_REF_LIMIT):
    if not ref or len(refs) >= limit:
        return
    url = ref.get("url")
    if not url or url in seen_urls:
        return
    seen_urls.add(url)
    refs.append(ref)


def _host_ref_chain(obj) -> list[dict]:
    """Navigation refs for Device / Interface / VM / VMInterface (with parent when applicable)."""
    from dcim.models import Device, Interface
    from virtualization.models import VirtualMachine, VMInterface

    refs: list[dict] = []
    if _hub.isinstance(obj, Interface):
        iface_ref = _navigation_ref(_("Interface"), obj)
        if iface_ref:
            refs.append(iface_ref)
        device_ref = _navigation_ref(_("Device"), getattr(obj, "device", None))
        if device_ref:
            refs.append(device_ref)
    elif _hub.isinstance(obj, VMInterface):
        iface_ref = _navigation_ref(_("Interface"), obj)
        if iface_ref:
            refs.append(iface_ref)
        vm_ref = _navigation_ref(_("VM"), getattr(obj, "virtual_machine", None))
        if vm_ref:
            refs.append(vm_ref)
    elif _hub.isinstance(obj, Device):
        device_ref = _navigation_ref(_("Device"), obj)
        if device_ref:
            refs.append(device_ref)
    elif _hub.isinstance(obj, VirtualMachine):
        vm_ref = _navigation_ref(_("VM"), obj)
        if vm_ref:
            refs.append(vm_ref)
    return refs


def _addr_nav_append_chain(refs, seen_urls, obj, *, limit=_ADDR_NAV_REF_LIMIT):
    for ref in _host_ref_chain(obj):
        _addr_nav_append(refs, seen_urls, ref, limit=limit)
        if len(refs) >= limit:
            return


def _addr_nav_from_assigned(assigned, refs, seen_urls, *, limit=_ADDR_NAV_REF_LIMIT):
    from dcim.models import Device, Interface
    from virtualization.models import VirtualMachine, VMInterface

    if _hub.isinstance(assigned, (Interface, VMInterface, Device, VirtualMachine)):
        _addr_nav_append_chain(refs, seen_urls, assigned, limit=limit)
    elif assigned is not None:
        assigned_ref = _navigation_ref(_("Assigned to"), assigned)
        _addr_nav_append(refs, seen_urls, assigned_ref, limit=limit)


def _addr_nav_object_link_hosts(obj, refs, seen_urls, *, limit=_ADDR_NAV_REF_LIMIT):
    from django.contrib.contenttypes.models import ContentType

    from dcim.models import Device, Interface
    from netbox_nsm.objects.object_link_service import iter_links_for_object
    from virtualization.models import VirtualMachine, VMInterface

    host_types = (Device, Interface, VirtualMachine, VMInterface)
    ct = ContentType.objects.get_for_model(obj)

    for link, direction in iter_links_for_object(obj):
        if len(refs) >= limit:
            return
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is not None and _hub.isinstance(linked, host_types):
            _addr_nav_append_chain(refs, seen_urls, linked, limit=limit)


def _addr_nav_assigned_ips_in_prefix(prefix, refs, seen_urls, *, limit=_ADDR_NAV_REF_LIMIT):
    from ipam.models import IPAddress

    cidr = str(prefix.prefix)
    for ip in IPAddress.objects.filter(
        address__net_contained_or_equal=cidr
    ).order_by("address")[:limit]:
        if len(refs) >= limit:
            return
        assigned = getattr(ip, "assigned_object", None)
        if assigned is not None:
            _addr_nav_from_assigned(assigned, refs, seen_urls, limit=limit)


def _addr_nav_assigned_ips_in_range(ip_range, refs, seen_urls, *, limit=_ADDR_NAV_REF_LIMIT):
    from ipam.models import IPAddress

    start = ip_range.start_address
    end = ip_range.end_address
    for ip in IPAddress.objects.filter(
        address__gte=start, address__lte=end
    ).order_by("address")[:limit]:
        if len(refs) >= limit:
            return
        assigned = getattr(ip, "assigned_object", None)
        if assigned is not None:
            _addr_nav_from_assigned(assigned, refs, seen_urls, limit=limit)


def _addr_navigation_refs(obj) -> list[dict]:
    """Related NetBox objects for drill-down (interface, device, VM) — not IPAM-only."""
    if obj is None:
        return []

    refs: list[dict] = []
    seen_urls: set[str] = set()
    try:
        from dcim.models import Device, Interface
        from ipam.models import IPAddress, IPRange, Prefix
        from netbox_nsm.addresses.address_ipam_fk import is_nsm_address_object
        from virtualization.models import VirtualMachine, VMInterface
    except ImportError:
        return refs

    limit = _ADDR_NAV_REF_LIMIT

    if _hub.isinstance(obj, IPAddress):
        _addr_nav_from_assigned(
            getattr(obj, "assigned_object", None), refs, seen_urls, limit=limit
        )
    elif _hub.isinstance(obj, Interface):
        _addr_nav_append_chain(refs, seen_urls, obj, limit=limit)
    elif _hub.isinstance(obj, VMInterface):
        _addr_nav_append_chain(refs, seen_urls, obj, limit=limit)
    elif _hub.isinstance(obj, (Device, VirtualMachine)):
        pass
    elif _hub.isinstance(obj, Prefix):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)
        _addr_nav_assigned_ips_in_prefix(obj, refs, seen_urls, limit=limit)
    elif _hub.isinstance(obj, IPRange):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)
        _addr_nav_assigned_ips_in_range(obj, refs, seen_urls, limit=limit)
    elif is_nsm_address_object(obj):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)

    return refs


def _attach_addr_navigation_refs(node, *, obj=None, ipam_obj=None):
    refs: list[dict] = []
    seen_urls: set[str] = set()

    def _merge(target):
        if target is None:
            return
        for ref in _addr_navigation_refs(target):
            url = ref.get("url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                refs.append(ref)

    target = ipam_obj
    if target is None and obj is not None:
        if _hub._is_ipam_addr_object(obj):
            target = obj
        else:
            target = _hub._ipam_fk_object_for_addr_node(obj)
    _merge(target)

    if obj is not None and not _hub._is_ipam_addr_object(obj):
        try:
            from netbox_nsm.addresses.address_ipam_fk import is_nsm_address_object

            if is_nsm_address_object(obj) and obj is not target:
                _merge(obj)
        except ImportError:
            pass

    if refs:
        node["related_refs"] = refs
    return node

