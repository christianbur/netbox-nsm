"""Address analysis and IP navigation helpers (extracted from legacy rulebook views)."""

from __future__ import annotations

from django.utils.html import conditional_escape

from netbox_nsm.core.api_urls import get_api_url_for_content_type as _get_api_url_for_content_type
from netbox_nsm.core.type_kind import is_address_content_type_id
from netbox_nsm.objects.type_config_specs import content_type_ids_for_cot_slugs

__all__ = (
    "_ADDR_IPAM_FK_FIELDS",
    "_addr_ip_ref",
    "_addr_navigation_refs",
    "_addr_nav_append",
    "_addr_nav_from_assigned",
    "_addr_nav_object_link_hosts",
    "_addr_path_line",
    "_addr_path_parts_for_leaf",
    "_addr_tree_node_display_count",
    "_attach_addr_navigation_refs",
    "_attach_addr_node_prefix_display",
    "_build_addr_tree_node",
    "_build_ipam_category_nodes",
    "_build_addr_diff_analysis",
    "_build_ipa_cell_object_tree",
    "_build_multi_object_addr_analysis",
    "_flatten_ipa_object_tree_copy_lines",
    "_collect_addr_tree_leaf_map",
    "_collect_ipam_prefix_children",
    "_enrich_addr_tree_copy_lines",
    "_enrich_addr_tree_leaf_counts",
    "_ipam_fk_object_for_addr_node",
    "_leaf_count_for_addr_analysis",
    "_object_is_addr_analyzable",
    "_object_supports_addr_analysis",
    "_parse_ipa_column_selections",
    "_prefix_ipam_stats",
    "_query_ipam_category_objects",
)

def _extract_ip_refs(obj):
    """Return list of {display, url, type} for IP-relevant objects reachable from obj."""
    return _extract_ip_refs_visited(obj, set())


_FIELD_TYPE_LABELS = {
    "prefix": "Prefix",
    "ip_address": "IP Address",
    "range": "Range",
}
_ADDR_IPAM_FK_FIELDS = ("prefix", "ip_address", "range")
_ADDR_IPAM_FK_FIELDS_HOST = ("ip_address", "range", "prefix")
_ADDR_IPAM_FK_FIELDS_SUBNET = ("prefix", "ip_address", "range")


def _addr_has_direct_ip_address(obj) -> bool:
    try:
        return getattr(obj, "ip_address", None) is not None
    except Exception:
        return False


def _addr_has_direct_range(obj) -> bool:
    try:
        return getattr(obj, "range", None) is not None
    except Exception:
        return False


def _addr_ip_ref_field_order(obj):
    """Host/range objects compare by specific IP; subnet rows keep prefix drilldown."""
    if _addr_has_direct_ip_address(obj) or _addr_has_direct_range(obj):
        return _ADDR_IPAM_FK_FIELDS_HOST
    return _ADDR_IPAM_FK_FIELDS_SUBNET


def _addr_ip_ref_from_fields(obj, field_names):
    """Return {str, url, type, ct, pk} for the first populated IPAM FK in *field_names*."""
    from django.contrib.contenttypes.models import ContentType

    for field_name in field_names:
        try:
            related = getattr(obj, field_name, None)
            if related is not None:
                ct = ContentType.objects.get_for_model(related)
                return {
                    "str": str(related),
                    "url": related.get_absolute_url(),
                    "type": _FIELD_TYPE_LABELS.get(field_name, field_name),
                    "ct": ct.pk,
                    "pk": related.pk,
                }
        except Exception:
            pass
    return None


def _addr_ip_ref(obj):
    """Return the most appropriate IPAM ref for analysis (host IP before parent prefix)."""
    return _addr_ip_ref_from_fields(obj, _addr_ip_ref_field_order(obj))


def _addr_ip_ref_node_dict(ip_ref):
    """Minimal ip_ref payload for address-tree nodes (includes loupe ct/pk when present)."""
    data = {"str": ip_ref["str"], "url": ip_ref["url"]}
    if ip_ref.get("ct") is not None and ip_ref.get("pk") is not None:
        data["ct"] = ip_ref["ct"]
        data["pk"] = ip_ref["pk"]
    return data


def _addr_group_members(obj):
    """Members contained in this nsm_addresses group (forward M2M on ``group``)."""
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return []
    try:
        return list(group_rel.all().order_by("name"))
    except Exception:
        try:
            return list(group_rel.all())
        except Exception:
            return []


def _addr_is_group_container(obj):
    """True when obj has no direct IP but contains other address objects."""
    if _addr_ip_ref(obj) is not None:
        return False
    if getattr(obj, "address_type", None) == "address-group":
        return True
    return bool(_addr_group_members(obj))


def _extract_ip_refs_visited(obj, visited=None):
    """Like _extract_ip_refs but accepts a visited set to avoid cycles in address groups."""
    if visited is None:
        visited = set()
    refs = []

    fd = getattr(obj, "field_data", None)
    if fd:
        for v in fd.values():
            if (
                isinstance(v, dict)
                and (v.get("str") or v.get("display"))
                and v.get("url")
            ):
                refs.append(
                    {
                        "display": v.get("display") or v.get("str"),
                        "url": v["url"],
                        "type": "",
                    }
                )
        return refs

    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            refs.append(
                {
                    "display": str(obj),
                    "url": obj.get_absolute_url(),
                    "type": obj._meta.verbose_name.capitalize(),
                }
            )
            return refs
    except Exception:
        pass

    ip_ref = _addr_ip_ref(obj)
    if ip_ref is None and _addr_is_group_container(obj):
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        for member in members:
            if member.pk not in visited:
                visited.add(member.pk)
                refs.extend(_extract_ip_refs_visited(member, visited))
        return refs

    if ip_ref is not None:
        refs.append(
            {
                "display": ip_ref["str"],
                "url": ip_ref["url"],
                "type": ip_ref["type"],
            }
        )

    return refs


def _addr_node_prefix_cidr(*, obj=None, ip_ref=None):
    """Return CIDR string for IPv4 IPAM prefixes and host addresses (e.g. /32)."""
    if ip_ref:
        ip_ref_type = ip_ref.get("type")
        cidr = ip_ref.get("str")
        if ip_ref_type == _FIELD_TYPE_LABELS["prefix"]:
            return cidr
        if ip_ref_type == _FIELD_TYPE_LABELS["ip_address"]:
            if cidr and "/" in cidr:
                return cidr
        if not ip_ref_type and cidr and "/" in cidr:
            return cidr
    if obj is not None:
        try:
            if obj._meta.app_label == "ipam":
                if obj._meta.model_name == "prefix":
                    prefix_val = getattr(obj, "prefix", None)
                    return str(prefix_val) if prefix_val is not None else str(obj)
                if obj._meta.model_name == "ipaddress":
                    addr = getattr(obj, "address", None)
                    cidr = str(addr) if addr is not None else str(obj)
                    if cidr and "/" in cidr:
                        return cidr
        except Exception:
            pass
    return None


def _attach_addr_node_prefix_display(node, *, obj=None, ip_ref=None):
    """Attach CIDR/netmask display labels to address-tree nodes for IPv4 prefixes/hosts."""
    from netbox_nsm.analysis.addr_netmask import prefix_display_labels_for_cidr

    cidr = _addr_node_prefix_cidr(obj=obj, ip_ref=ip_ref)
    if not cidr:
        return node
    labels = prefix_display_labels_for_cidr(cidr)
    if labels:
        node["prefix_display_cidr"], node["prefix_display_netmask"] = labels
    return node


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
    if isinstance(obj, Interface):
        iface_ref = _navigation_ref(_("Interface"), obj)
        if iface_ref:
            refs.append(iface_ref)
        device_ref = _navigation_ref(_("Device"), getattr(obj, "device", None))
        if device_ref:
            refs.append(device_ref)
    elif isinstance(obj, VMInterface):
        iface_ref = _navigation_ref(_("Interface"), obj)
        if iface_ref:
            refs.append(iface_ref)
        vm_ref = _navigation_ref(_("VM"), getattr(obj, "virtual_machine", None))
        if vm_ref:
            refs.append(vm_ref)
    elif isinstance(obj, Device):
        device_ref = _navigation_ref(_("Device"), obj)
        if device_ref:
            refs.append(device_ref)
    elif isinstance(obj, VirtualMachine):
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

    if isinstance(assigned, (Interface, VMInterface, Device, VirtualMachine)):
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
        if linked is not None and isinstance(linked, host_types):
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
        from netbox_nsm.objects.address_ipam_fk import is_nsm_address_object
        from virtualization.models import VirtualMachine, VMInterface
    except ImportError:
        return refs

    limit = _ADDR_NAV_REF_LIMIT

    if isinstance(obj, IPAddress):
        _addr_nav_from_assigned(
            getattr(obj, "assigned_object", None), refs, seen_urls, limit=limit
        )
    elif isinstance(obj, Interface):
        _addr_nav_append_chain(refs, seen_urls, obj, limit=limit)
    elif isinstance(obj, VMInterface):
        _addr_nav_append_chain(refs, seen_urls, obj, limit=limit)
    elif isinstance(obj, (Device, VirtualMachine)):
        pass
    elif isinstance(obj, Prefix):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)
        _addr_nav_assigned_ips_in_prefix(obj, refs, seen_urls, limit=limit)
    elif isinstance(obj, IPRange):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)
        _addr_nav_assigned_ips_in_range(obj, refs, seen_urls, limit=limit)
    elif is_nsm_address_object(obj):
        _addr_nav_object_link_hosts(obj, refs, seen_urls, limit=limit)

    return refs


def _ipam_obj_from_ip_ref(ip_ref):
    """Load the IPAM object shown in the tree (matches ``ip_ref`` ct/pk)."""
    if not ip_ref:
        return None
    ct_id = ip_ref.get("ct")
    pk = ip_ref.get("pk")
    if ct_id is None or pk is None:
        return None
    try:
        from django.contrib.contenttypes.models import ContentType

        model = ContentType.objects.get(pk=int(ct_id)).model_class()
        if model is None:
            return None
        return model.objects.filter(pk=int(pk)).first()
    except Exception:
        return None


def _ipam_fk_object_for_addr_node(obj):
    for field_name in _addr_ip_ref_field_order(obj):
        try:
            related = getattr(obj, field_name, None)
            if related is not None:
                return related
        except Exception:
            pass
    return None


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
        if _is_ipam_addr_object(obj):
            target = obj
        else:
            target = _ipam_fk_object_for_addr_node(obj)
    _merge(target)

    if obj is not None and not _is_ipam_addr_object(obj):
        try:
            from netbox_nsm.objects.address_ipam_fk import is_nsm_address_object

            if is_nsm_address_object(obj) and obj is not target:
                _merge(obj)
        except ImportError:
            pass

    if refs:
        node["related_refs"] = refs
    return node


_IPAM_ADDR_MODEL_NAMES = frozenset({"prefix", "ipaddress", "iprange"})
_IPAM_PREFIX_CHILDREN_MAX = 250
_IPAM_PREFIX_LARGE_CHILD_THRESHOLD = 50
_IPAM_PREFIX_LARGE_IP_THRESHOLD = 1000


def _prefix_is_large(stats):
    """True when eager tree expansion would be too expensive."""
    if not stats:
        return False
    child_count = int((stats.get("child_prefixes") or {}).get("count") or 0)
    ip_count = int((stats.get("ip_addresses") or {}).get("count") or 0)
    return (
        child_count > _IPAM_PREFIX_LARGE_CHILD_THRESHOLD
        or ip_count > _IPAM_PREFIX_LARGE_IP_THRESHOLD
    )


def _ipam_analyzer_stat_label(kind):
    from django.utils.translation import gettext as _

    labels = {
        "child_prefixes": _("IPAM > Prefixes"),
        "ip_addresses": _("IPAM > IP Addresses"),
        "ip_ranges": _("IPAM > IP Ranges"),
        "nsm_addresses": _("Custom Objects > Addresses"),
    }
    return str(labels[kind])


def _prefix_ipam_stats(prefix):
    """NetBox-native prefix inventory counts (same sources as the prefix detail tabs)."""
    from django.urls import reverse

    from netbox_nsm.objects.address_ipam_fk import get_nsm_address_model

    stats = {
        "child_prefixes": {
            "kind": "child_prefixes",
            "label": _ipam_analyzer_stat_label("child_prefixes"),
            "count": prefix.get_child_prefixes().count(),
            "url": reverse("ipam:prefix_prefixes", kwargs={"pk": prefix.pk}),
        },
        "ip_addresses": {
            "kind": "ip_addresses",
            "label": _ipam_analyzer_stat_label("ip_addresses"),
            "count": prefix.get_child_ips().count(),
            "url": reverse("ipam:prefix_ipaddresses", kwargs={"pk": prefix.pk}),
        },
        "ip_ranges": {
            "kind": "ip_ranges",
            "label": _ipam_analyzer_stat_label("ip_ranges"),
            "count": prefix.get_child_ranges().count(),
            "url": reverse("ipam:prefix_ipranges", kwargs={"pk": prefix.pk}),
        },
    }
    addr_model = get_nsm_address_model()
    if addr_model is not None:
        addr_count = addr_model.objects.filter(prefix_id=prefix.pk).count()
        if addr_count:
            stats["nsm_addresses"] = {
                "kind": "nsm_addresses",
                "label": _ipam_analyzer_stat_label("nsm_addresses"),
                "count": addr_count,
                "url": prefix.get_absolute_url(),
            }
    return stats


def _ordered_ipam_stats(stats):
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    ordered = []
    for key in order:
        if key not in stats:
            continue
        item = dict(stats[key])
        item.setdefault("kind", key)
        item.setdefault("label", _ipam_analyzer_stat_label(key))
        ordered.append(item)
    return ordered


def _ipam_stats_short(stats_list):
    """Compact summary: child-prefixes / ips / ranges / nsm-addresses counts."""
    return "/".join(str(item.get("count", 0)) for item in stats_list)


def _ipam_stats_total(stats_list):
    """Sum all NetBox ipam_stats category counts (matches pill segments)."""
    return sum(int(item.get("count") or 0) for item in (stats_list or []))


def _ipam_stats_ip_count(stats_list):
    """Return NetBox IP-address count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "ip_addresses":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "IP Addresses" in label or "IP-Adressen" in label:
            return int(item.get("count") or 0)
    return 0


def _ipam_stats_subnet_count(stats_list):
    """Return NetBox child-prefix count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "child_prefixes":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "Prefixes" in label or "Prefixe" in label:
            return int(item.get("count") or 0)
    return 0


def _ipam_stats_range_count(stats_list):
    """Return NetBox IP-range count from ordered ipam_stats."""
    for item in stats_list or []:
        if item.get("kind") == "ip_ranges":
            return int(item.get("count") or 0)
    for item in stats_list or []:
        label = str(item.get("label") or "")
        if "IP Ranges" in label or "IP-Bereiche" in label:
            return int(item.get("count") or 0)
    return 0


def _addr_tree_node_effective_network(node):
    """Network for a tree node, including inferred CIDR from NSM names like ``g-10.0.0.0/8``."""
    net = _addr_tree_node_network(node)
    if net is not None:
        return net
    if node and node.get("kind") in ("group", "leaf"):
        cidr = _ipa_cidr_from_object_name(node.get("name"))
        if cidr:
            try:
                import ipaddress

                return ipaddress.ip_network(str(cidr).strip(), strict=False)
            except ValueError:
                pass
    return None


def _addr_tree_network_covered(net, containing_networks):
    """True when *net* is already represented by an ancestor prefix in the walk."""
    if net is None or not containing_networks:
        return False
    for anc in containing_networks:
        if net == anc or (net.subnet_of(anc) and net != anc):
            return True
    return False


def _addr_tree_node_ip_count(node, containing_networks=None):
    """IP count for aggregate badges from IPAM child stats, without contained-prefix double-count."""
    if not node or node.get("count_duplicate"):
        return 0
    if containing_networks is None:
        containing_networks = []

    net = _addr_tree_node_effective_network(node)
    if _addr_tree_network_covered(net, containing_networks):
        return 0

    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _ipam_stats_ip_count(ipam_stats)

    kind = node.get("kind")
    next_containing = list(containing_networks)
    if net is not None:
        next_containing.append(net)

    if kind == "category":
        label = str(node.get("name") or "")
        if "IP Addresses" in label or "IP-Adressen" in label:
            return int(node.get("count") or 0)
        return sum(
            _addr_tree_node_ip_count(child, next_containing)
            for child in node.get("children") or []
        )
    if kind == "group":
        children = node.get("children") or []
        child_total = sum(
            _addr_tree_node_ip_count(child, next_containing) for child in children
        )
        if child_total:
            return child_total
        # A group member may share the parent CIDR (e.g. g-10.0.0.0/8 → n-10.0.0.0/8)
        # and be suppressed above; still use its ipam_stats IP total for the badge.
        stats_ip_total = sum(
            _ipam_stats_ip_count(child.get("ipam_stats") or []) for child in children
        )
        if stats_ip_total:
            return stats_ip_total
        inferred = _addr_tree_node_effective_network(node)
        if inferred is not None:
            prefix = _lookup_ipam_prefix_for_cidr(str(inferred))
            if prefix is not None:
                return prefix.get_child_ips().count()
        return int(node.get("leaf_count") or 0)

    ip_ref = node.get("ip_ref") or {}
    if ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]:
        return 1
    cidr = str(ip_ref.get("str") or "")
    if cidr.endswith("/32"):
        return 1
    return 1


def _addr_tree_node_display_count(node):
    """Display count for badges/footer: NetBox stats when present, else loaded leaves."""
    if not node:
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _ipam_stats_total(ipam_stats)
    kind = node.get("kind")
    if kind in ("group", "category"):
        children = node.get("children") or []
        if children:
            return sum(_addr_tree_node_display_count(child) for child in children)
        if kind == "category":
            return int(node.get("count") or 0)
        return int(node.get("leaf_count") or 0)
    return 1


def _addr_tree_node_subnet_count(node):
    """Subnet (child-prefix) count for aggregate badges."""
    if not node:
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _ipam_stats_subnet_count(ipam_stats)
    kind = node.get("kind")
    if kind == "category":
        label = str(node.get("name") or "")
        if "Prefixes" in label or "Prefixe" in label:
            return int(node.get("count") or 0)
        return sum(
            _addr_tree_node_subnet_count(child) for child in node.get("children") or []
        )
    if kind == "group":
        child_total = sum(
            _addr_tree_node_subnet_count(child) for child in node.get("children") or []
        )
        if child_total:
            return child_total
        ip_ref = node.get("ip_ref") or {}
        if ip_ref.get("type") == _FIELD_TYPE_LABELS["prefix"]:
            return 1
        return 0
    return 0


def _addr_tree_node_range_count(node):
    """IP-range count for aggregate badges."""
    if not node:
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _ipam_stats_range_count(ipam_stats)
    kind = node.get("kind")
    if kind == "category":
        label = str(node.get("name") or "")
        if "IP Ranges" in label or "IP-Bereiche" in label:
            return int(node.get("count") or 0)
        return sum(
            _addr_tree_node_range_count(child) for child in node.get("children") or []
        )
    if kind == "group":
        child_total = sum(
            _addr_tree_node_range_count(child) for child in node.get("children") or []
        )
        if child_total:
            return child_total
        return 0
    ip_ref = node.get("ip_ref") or {}
    if ip_ref.get("type") == _FIELD_TYPE_LABELS["range"]:
        return 1
    return 0


def _addr_tree_node_network(node):
    """Return ip_network for a tree root when it represents a prefix or host CIDR."""
    import ipaddress

    if not node:
        return None
    cidr = _addr_node_prefix_cidr(ip_ref=node.get("ip_ref"))
    if not cidr:
        cidr = node.get("prefix_display_cidr")
    if not cidr:
        return None
    try:
        return ipaddress.ip_network(str(cidr).strip(), strict=False)
    except ValueError:
        return None


def _addr_node_containment_map(nodes):
    """Map contained root node id -> enclosing selected root metadata."""
    entries = [(node, _addr_tree_node_effective_network(node)) for node in (nodes or [])]
    contained_in = {}
    for i, (node_i, net_i) in enumerate(entries):
        if net_i is None:
            continue
        for j, (node_j, net_j) in enumerate(entries):
            if i == j or net_j is None:
                continue
            if net_i == net_j and i > j:
                contained_in[id(node_i)] = {
                    "name": str(node_j.get("name") or ""),
                    "url": str(node_j.get("url") or ""),
                }
                break
            if net_i.subnet_of(net_j) and net_i != net_j:
                contained_in[id(node_i)] = {
                    "name": str(node_j.get("name") or ""),
                    "url": str(node_j.get("url") or ""),
                }
                break
    return contained_in


def _mark_contained_addr_duplicate_flags(nodes):
    """Flag top-level roots whose prefix is already counted via another selection."""
    if len(nodes or []) < 2:
        return nodes
    contained_in = _addr_node_containment_map(nodes)
    for node in nodes:
        parent = contained_in.get(id(node))
        if parent:
            node["count_duplicate"] = True
            node["count_duplicate_of"] = parent.get("name") or ""
            node["count_duplicate_of_url"] = parent.get("url") or ""
    return nodes


def _filter_non_contained_addr_nodes(nodes):
    """Drop roots whose prefix is strictly contained in another selected prefix."""
    contained_in = _addr_node_containment_map(nodes)
    return [node for node in (nodes or []) if id(node) not in contained_in]


def _display_count_for_addr_nodes(nodes):
    """Total IP count across top-level roots (no double-count for nested prefixes)."""
    roots = _filter_non_contained_addr_nodes(nodes)
    return sum(_addr_tree_node_ip_count(node) for node in roots)


def _type_counts_for_addr_nodes(nodes):
    """Subnet, range, and IP counts across top-level roots (no double-count)."""
    roots = _filter_non_contained_addr_nodes(nodes)
    return {
        "count_subnets": sum(_addr_tree_node_subnet_count(node) for node in roots),
        "count_ranges": sum(_addr_tree_node_range_count(node) for node in roots),
        "count_ips": sum(_addr_tree_node_ip_count(node) for node in roots),
    }


def _attach_ipam_stats_meta(node, stats, *, truncated=None):
    ordered = _ordered_ipam_stats(stats) if isinstance(stats, dict) else list(stats)
    node["ipam_stats"] = ordered
    node["ipam_stats_short"] = _ipam_stats_short(ordered)
    if truncated is not None:
        node["ipam_truncated"] = any(truncated.values())
    return node


def _attach_prefix_ipam_meta(node, prefix, *, stats=None, truncated=None):
    """Attach NetBox prefix tab counts for the analyzer UI."""
    if stats is None:
        stats = _prefix_ipam_stats(prefix)
    return _attach_ipam_stats_meta(node, stats, truncated=truncated)


def _collect_ipam_prefix_children_impl(prefix, *, include_nsm_addresses=True):
    """Load a bounded preview tree grouped by NetBox category."""
    from netbox_nsm.objects.address_ipam_fk import get_nsm_address_model

    limit = _IPAM_PREFIX_CHILDREN_MAX
    stats = _prefix_ipam_stats(prefix)
    truncated = {}

    if _prefix_is_large(stats):
        for key in ("child_prefixes", "ip_addresses", "ip_ranges"):
            if key in stats:
                truncated[key] = int(stats[key].get("count") or 0) > 0
        if include_nsm_addresses and "nsm_addresses" in stats:
            truncated["nsm_addresses"] = (
                int(stats["nsm_addresses"].get("count") or 0) > 0
            )
        for key, flag in truncated.items():
            if key in stats:
                stats[key]["truncated"] = flag
        grouped = {
            "child_prefixes": [],
            "ip_addresses": [],
            "ip_ranges": [],
            "nsm_addresses": [],
        }
        return grouped, stats, truncated

    child_prefixes = list(prefix.get_child_prefixes().order_by("prefix", "pk")[:limit])
    truncated["child_prefixes"] = stats["child_prefixes"]["count"] > len(
        child_prefixes
    )

    ip_count = stats["ip_addresses"]["count"]
    child_ips = (
        list(prefix.get_child_ips().order_by("address", "pk")[:limit])
        if ip_count <= limit
        else []
    )
    truncated["ip_addresses"] = ip_count > len(child_ips)

    range_count = stats["ip_ranges"]["count"]
    child_ranges = (
        list(prefix.get_child_ranges().order_by("start_address", "pk")[:limit])
        if range_count <= limit
        else []
    )
    truncated["ip_ranges"] = range_count > len(child_ranges)

    child_addrs = []
    if include_nsm_addresses:
        addr_model = get_nsm_address_model()
        if addr_model is not None:
            addr_count = addr_model.objects.filter(prefix_id=prefix.pk).count()
            if addr_count:
                if "nsm_addresses" not in stats:
                    stats["nsm_addresses"] = {
                        "label": _ipam_analyzer_stat_label("nsm_addresses"),
                        "count": addr_count,
                        "url": prefix.get_absolute_url(),
                    }
                if addr_count <= limit:
                    child_addrs = list(
                        addr_model.objects.filter(prefix_id=prefix.pk).order_by("name")[
                            :limit
                        ]
                    )
                truncated["nsm_addresses"] = addr_count > len(child_addrs)

    for key, flag in truncated.items():
        if key in stats:
            stats[key]["truncated"] = flag

    grouped = {
        "child_prefixes": child_prefixes,
        "ip_addresses": child_ips,
        "ip_ranges": child_ranges,
        "nsm_addresses": child_addrs,
    }
    return grouped, stats, truncated


def _flatten_ipam_grouped(grouped):
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    items = []
    for key in order:
        items.extend(grouped.get(key) or [])
    return items


def _query_ipam_category_objects(prefix, category, *, offset=0, limit=None):
    """Fetch one page of objects for a prefix inventory category."""
    from netbox_nsm.objects.address_ipam_fk import get_nsm_address_model

    page_size = limit if limit is not None else _IPAM_PREFIX_CHILDREN_MAX
    page_size = min(max(int(page_size), 1), _IPAM_PREFIX_CHILDREN_MAX)
    offset = max(int(offset), 0)
    end = offset + page_size

    if category == "child_prefixes":
        return list(
            prefix.get_child_prefixes().order_by("prefix", "pk")[offset:end]
        )
    if category == "ip_addresses":
        return list(prefix.get_child_ips().order_by("address", "pk")[offset:end])
    if category == "ip_ranges":
        return list(
            prefix.get_child_ranges().order_by("start_address", "pk")[offset:end]
        )
    if category == "nsm_addresses":
        addr_model = get_nsm_address_model()
        if addr_model is None:
            return []
        return list(
            addr_model.objects.filter(prefix_id=prefix.pk).order_by("name")[offset:end]
        )
    return []


def _build_ipam_category_nodes(prefix, grouped, stats, visited):
    """Build first-level category groups under a prefix inventory node."""
    nodes = []
    order = ("child_prefixes", "ip_addresses", "ip_ranges", "nsm_addresses")
    large = _prefix_is_large(stats)
    for key in order:
        if key not in stats:
            continue
        stat = stats[key]
        count = int(stat.get("count") or 0)
        items = grouped.get(key) or []
        if large:
            cat_children = []
            loaded = 0
            lazy_load = count > 0
        else:
            cat_children = []
            for item in items:
                child = _build_addr_tree_node(
                    item,
                    _addr_tree_child_visited(visited, item, prefix),
                )
                if child:
                    cat_children.append(child)
            loaded = len(cat_children)
            lazy_load = count > loaded or bool(stat.get("truncated"))
        nodes.append(
            {
                "kind": "category",
                "name": stat["label"],
                "url": stat["url"],
                "count": count,
                "loaded_count": loaded,
                "lazy_load": lazy_load,
                "lazy_ctx": {
                    "prefix_pk": prefix.pk,
                    "category": key,
                },
                "children": cat_children,
            }
        )
    return nodes


def _collect_ipam_prefix_children(prefix):
    """Return analyzable children contained in or linked to an IPAM prefix."""
    grouped, _stats, _truncated = _collect_ipam_prefix_children_impl(
        prefix, include_nsm_addresses=True
    )
    return _flatten_ipam_grouped(grouped)


def _collect_ipam_prefix_ipam_children(prefix):
    """Prefix drill-down: child prefixes, IPs, and ranges only (no nsm_addresses)."""
    grouped, _stats, _truncated = _collect_ipam_prefix_children_impl(
        prefix, include_nsm_addresses=False
    )
    return _flatten_ipam_grouped(grouped)


def _collect_ipam_prefix_drilldown(prefix):
    """Drill-down from nsm_address FK with NetBox stats attached."""
    return _collect_ipam_prefix_children_impl(prefix, include_nsm_addresses=False)


def _is_ipam_addr_object(obj) -> bool:
    try:
        return (
            obj._meta.app_label == "ipam"
            and obj._meta.model_name in _IPAM_ADDR_MODEL_NAMES
        )
    except Exception:
        return False


def _collect_ipam_range_ip_children(ip_range):
    """IP range drill-down: contained IP addresses."""
    from ipam.models import IPAddress

    start = ip_range.start_address
    end = ip_range.end_address
    return list(
        IPAddress.objects.filter(address__gte=start, address__lte=end).order_by(
            "address"
        )[:_IPAM_PREFIX_CHILDREN_MAX]
    )


def _collect_ipam_drilldown_children(ipam_obj):
    """IPAM-only children for drill-down from nsm_address FK targets."""
    try:
        from ipam.models import IPRange, Prefix
    except ImportError:
        return []

    if isinstance(ipam_obj, Prefix):
        grouped, _stats, _truncated = _collect_ipam_prefix_drilldown(ipam_obj)
        return _flatten_ipam_grouped(grouped)
    if isinstance(ipam_obj, IPRange):
        return _collect_ipam_range_ip_children(ipam_obj)
    return []


def _addr_tree_child_visited(parent_visited, child_obj, parent_obj):
    """Child-prefix subtrees must not inherit IP visited keys from the parent prefix."""
    try:
        from ipam.models import Prefix

        if isinstance(child_obj, Prefix):
            parent_pk = getattr(parent_obj, "pk", None)
            return {parent_pk} if parent_pk is not None else set()
    except ImportError:
        pass
    return parent_visited


def _build_addr_tree_node(obj, visited=None):
    """
    Recursively build an address hierarchy tree node for nsm_addresses objects.
    Returns: {name, url, kind: 'group'|'leaf', ip_ref: {str,url}|None, children: [...]}
    """
    if visited is None:
        visited = set()
    if obj.pk in visited:
        return None
    visited.add(obj.pk)

    ip_ref = _addr_ip_ref(obj)

    if ip_ref is None and _addr_is_group_container(obj):
        children = []
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        for sub in members:
            child = _build_addr_tree_node(sub, visited)
            if child:
                children.append(child)
        return {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "group",
            "ip_ref": None,
            "children": children,
        }

    if ip_ref is not None:
        ipam_obj = _ipam_obj_from_ip_ref(ip_ref) or _ipam_fk_object_for_addr_node(obj)
        ip_ref_dict = _addr_ip_ref_node_dict(ip_ref)
        if ipam_obj is not None:
            grouped = None
            prefix_stats = None
            prefix_truncated = None
            child_nodes = []
            try:
                from ipam.models import Prefix as _Prefix

                if isinstance(ipam_obj, _Prefix):
                    grouped, prefix_stats, prefix_truncated = (
                        _collect_ipam_prefix_drilldown(ipam_obj)
                    )
                    child_nodes = _build_ipam_category_nodes(
                        ipam_obj, grouped, prefix_stats, visited
                    )
                else:
                    for child_obj in _collect_ipam_drilldown_children(ipam_obj):
                        child = _build_addr_tree_node(
                            child_obj,
                            _addr_tree_child_visited(visited, child_obj, obj),
                        )
                        if child:
                            child_nodes.append(child)
            except ImportError:
                for child_obj in _collect_ipam_drilldown_children(ipam_obj):
                    child = _build_addr_tree_node(child_obj, visited)
                    if child:
                        child_nodes.append(child)

            if child_nodes or prefix_stats:
                node = {
                    "name": str(obj.name),
                    "url": obj.get_absolute_url(),
                    "kind": "group",
                    "ip_ref": ip_ref_dict,
                    "children": child_nodes,
                }
                if prefix_stats:
                    _attach_ipam_stats_meta(
                        node, prefix_stats, truncated=prefix_truncated
                    )
                return _attach_addr_node_prefix_display(
                    node, obj=obj, ip_ref=ip_ref
                )

        node = {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "leaf",
            "ip_ref": ip_ref_dict,
            "children": [],
        }
        node = _attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)
        return _attach_addr_navigation_refs(node, obj=obj)

    # IPAM prefix — expand contained IPs, ranges, child prefixes, linked addresses
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name == "prefix":
            grouped, stats, truncated = _collect_ipam_prefix_children_impl(obj)
            child_nodes = _build_ipam_category_nodes(obj, grouped, stats, visited)
            if not child_nodes and not any(
                item.get("count") for item in stats.values()
            ):
                return None
            node = {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "group",
                "ip_ref": None,
                "children": child_nodes,
            }
            node = _attach_prefix_ipam_meta(node, obj, stats=stats, truncated=truncated)
            return _attach_addr_node_prefix_display(node, obj=obj)
    except Exception:
        pass

    # Other IPAM objects — treat as leaf
    try:
        if obj._meta.app_label == "ipam":
            node = {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "leaf",
                "ip_ref": {"str": str(obj), "url": obj.get_absolute_url()},
                "children": [],
            }
            node = _attach_addr_node_prefix_display(
                node, obj=obj, ip_ref=node["ip_ref"]
            )
            return _attach_addr_navigation_refs(node, ipam_obj=obj)
    except Exception:
        pass
    return {
        "name": str(getattr(obj, "name", obj)),
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
        "kind": "leaf",
        "ip_ref": None,
        "children": [],
    }


def _addr_path_line(path_parts):
    """CSV path: group,group,...,ip (comma-separated, no spaces)."""
    return ",".join(str(p) for p in path_parts if p is not None and str(p) != "")


def _addr_path_parts_for_leaf(node, path_prefix):
    """Build CSV path segments for a leaf (object name + IP when both differ)."""
    row = list(path_prefix)
    ip_ref = node.get("ip_ref")
    if ip_ref and ip_ref.get("str"):
        ip_str = str(ip_ref["str"])
        name = str(node.get("name") or "").strip()
        if name and name != ip_str:
            row.append(name)
        row.append(ip_str)
    else:
        row.append(node["name"])
    return row


def _prefix_addr_copy_lines(lines, *prefix_parts):
    """Prepend fixed CSV segments (e.g. ``all``) to each copy line."""
    head = _addr_path_line(list(prefix_parts))
    if not head:
        return list(lines or [])
    prefixed = []
    for line in lines or []:
        text = str(line).strip()
        prefixed.append(f"{head},{text}" if text else head)
    return prefixed


def _flatten_addr_tree_paths(nodes, path_prefix=None):
    """Flatten address tree nodes to comma-separated path lines (one per leaf)."""
    if path_prefix is None:
        path_prefix = []
    lines = []
    for node in nodes:
        kind = node.get("kind")
        if kind == "group":
            branch = path_prefix + [node["name"]]
            children = node.get("children") or []
            if children:
                lines.extend(_flatten_addr_tree_paths(children, branch))
            else:
                lines.append(_addr_path_line(branch))
        elif kind == "category":
            lines.extend(_flatten_addr_tree_paths(node.get("children") or [], path_prefix))
        else:
            lines.append(_addr_path_line(_addr_path_parts_for_leaf(node, path_prefix)))
    return lines


def _enrich_addr_tree_leaf_counts(node):
    """Attach leaf_count: NetBox ipam_stats sum when present, else subtree leaves."""
    kind = node.get("kind")
    if kind in ("group", "category"):
        if kind == "group" and node.get("ipam_stats"):
            node["leaf_count"] = _ipam_stats_total(node["ipam_stats"])
            return node
        total = 0
        for child in node.get("children") or []:
            _enrich_addr_tree_leaf_counts(child)
            total += child.get("leaf_count") or 0
        if kind == "category" and total == 0 and node.get("count"):
            node["leaf_count"] = int(node["count"])
        else:
            node["leaf_count"] = total
    else:
        node["leaf_count"] = 1
    return node


def _enrich_addr_tree_copy_lines(node, path_prefix=None):
    """Attach copy_lines (subtree) to each group/leaf node for template copy buttons."""
    if path_prefix is None:
        path_prefix = []
    kind = node.get("kind")
    if kind == "group":
        branch = path_prefix + [node["name"]]
        child_lines = []
        for child in node.get("children") or []:
            _enrich_addr_tree_copy_lines(child, branch)
            child_lines.extend(child.get("copy_lines") or [])
        node["copy_lines"] = child_lines
    elif kind == "category":
        child_lines = []
        for child in node.get("children") or []:
            _enrich_addr_tree_copy_lines(child, path_prefix)
            child_lines.extend(child.get("copy_lines") or [])
        node["copy_lines"] = child_lines
    else:
        node["copy_lines"] = [
            _addr_path_line(_addr_path_parts_for_leaf(node, path_prefix))
        ]
    return node


def _build_addr_tree_nodes(objs, *, all_copy_prefix="all"):
    """Build enriched tree nodes and flat CSV path lines for a list of address objects."""
    nodes = []
    for obj in objs:
        node = _build_addr_tree_node(obj)
        if node:
            _enrich_addr_tree_copy_lines(node)
            _enrich_addr_tree_leaf_counts(node)
            nodes.append(node)
    _mark_contained_addr_duplicate_flags(nodes)
    flat_lines = _flatten_addr_tree_paths(nodes)
    if all_copy_prefix:
        flat_lines = _prefix_addr_copy_lines(flat_lines, all_copy_prefix)
    return nodes, flat_lines


def _object_supports_addr_analysis(obj):
    """True when obj can be expanded as an address tree (group container or IP leaf)."""
    if _addr_ip_ref(obj) is not None or _addr_is_group_container(obj):
        return True
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            return True
    except Exception:
        pass
    return False


def _object_is_addr_analyzable(obj, content_type_id, address_ct_ids=None):
    """True when content type is address-class and the object can be IP-analyzed."""
    if not obj or not content_type_id:
        return False
    if not _object_supports_addr_analysis(obj):
        return False
    if _is_ipam_addr_object(obj):
        return True
    if address_ct_ids is None:
        address_ct_ids = set(
            content_type_ids_for_cot_slugs(["nsm_address", "nsm_address_group"])
        )
    return is_address_content_type_id(content_type_id, cache=address_ct_ids)


def _addr_leaf_compare_key(node, path_prefix=None):
    """Stable key for address diff set comparison."""
    if path_prefix is None:
        path_prefix = []
    ip_ref = node.get("ip_ref")
    if ip_ref and ip_ref.get("str"):
        return str(ip_ref["str"]).strip().lower()
    return _addr_path_line(_addr_path_parts_for_leaf(node, path_prefix)).strip().lower()


def _addr_leaf_source_object(node):
    """Shallow source descriptor for diff name comparison (COT/display name)."""
    name = str(node.get("name") or "").strip()
    if not name:
        return None
    return {
        "name": name,
        "url": node.get("url") or "#",
    }


def _addr_source_name_set(entry):
    """Distinct display names that resolve to this IPAM compare key."""
    names = set()
    for src in entry.get("source_objects") or []:
        name = str(src.get("name") or "").strip()
        if name:
            names.add(name)
    return names


def _addr_append_leaf_source(entry, node):
    """Record another tree leaf that resolves to the same IPAM key."""
    src = _addr_leaf_source_object(node)
    if not src:
        return
    existing = {o["name"] for o in entry.get("source_objects") or []}
    if src["name"] not in existing:
        entry.setdefault("source_objects", []).append(src)


def _collect_addr_tree_leaf_keys_under(nodes, path_prefix=None):
    """Collect compare keys for all leaves under *nodes*."""
    if path_prefix is None:
        path_prefix = []
    keys = set()
    for node in nodes or []:
        kind = node.get("kind")
        if kind == "group":
            branch = path_prefix + [node["name"]]
            keys.update(
                _collect_addr_tree_leaf_keys_under(node.get("children") or [], branch)
            )
        elif kind == "category":
            keys.update(
                _collect_addr_tree_leaf_keys_under(node.get("children") or [], path_prefix)
            )
        else:
            key = _addr_leaf_compare_key(node, path_prefix)
            if key:
                keys.add(key)
    return keys


def _addr_tree_node_prefix_compare_key(node):
    """Normalized CIDR key when *node* is a prefix group in the address tree."""
    if node.get("kind") != "group":
        return None
    ip_ref = node.get("ip_ref") or {}
    if ip_ref.get("type") == _FIELD_TYPE_LABELS["prefix"] and ip_ref.get("str"):
        return str(ip_ref["str"]).strip().lower()
    cidr = node.get("prefix_display_cidr")
    if cidr and "/" in str(cidr):
        return str(cidr).strip().lower()
    return None


def _lookup_ipam_prefix_for_cidr(cidr):
    """Return the first NetBox Prefix matching *cidr*, if any."""
    if not cidr:
        return None
    try:
        import ipaddress

        from ipam.models import Prefix

        net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        return Prefix.objects.filter(prefix=net).order_by("pk").first()
    except Exception:
        return None


def _prefix_group_to_diff_entry(node):
    """Shallow diff entry for a prefix group node."""
    src = _addr_leaf_source_object(node)
    entry = {
        "kind": "group",
        "name": node.get("name") or "",
        "url": node.get("url") or "#",
        "ip_ref": node.get("ip_ref"),
        "prefix_display_cidr": node.get("prefix_display_cidr"),
        "prefix_display_netmask": node.get("prefix_display_netmask"),
        "related_refs": node.get("related_refs"),
        "source_objects": [src] if src else [],
        "children": [],
    }
    if not entry.get("ip_ref") and entry.get("prefix_display_cidr"):
        prefix = _lookup_ipam_prefix_for_cidr(entry["prefix_display_cidr"])
        if prefix is not None:
            try:
                from django.contrib.contenttypes.models import ContentType

                ct = ContentType.objects.get_for_model(prefix)
                ip_ref = {
                    "str": str(prefix),
                    "url": prefix.get_absolute_url(),
                    "type": _FIELD_TYPE_LABELS["prefix"],
                    "ct": ct.pk,
                    "pk": prefix.pk,
                }
                entry["ip_ref"] = _addr_ip_ref_node_dict(ip_ref)
                _attach_addr_node_prefix_display(entry, ip_ref=ip_ref)
            except Exception:
                pass
    return entry


def _collect_addr_tree_prefix_groups(nodes, path_prefix=None):
    """Map prefix CIDR key -> diff entry plus all descendant leaf compare keys."""
    if path_prefix is None:
        path_prefix = []
    found = {}
    for node in nodes or []:
        kind = node.get("kind")
        children = node.get("children") or []
        if kind == "group":
            branch = path_prefix + [node["name"]]
            prefix_key = _addr_tree_node_prefix_compare_key(node)
            if prefix_key:
                found[prefix_key] = {
                    "entry": _prefix_group_to_diff_entry(node),
                    "leaf_keys": _collect_addr_tree_leaf_keys_under(
                        children, branch
                    ),
                }
            found.update(_collect_addr_tree_prefix_groups(children, branch))
        elif kind == "category":
            found.update(_collect_addr_tree_prefix_groups(children, path_prefix))
    return found


def _compute_diff_prefix_hierarchy(prefix_groups_a, prefix_groups_b, both_keys):
    """
    Prefix keys that should appear as parent nodes in the intersection tree.
    Includes a prefix when both sides share it and at least one descendant IP
    is in the diff intersection (individual IP pair nodes are kept as children).
    """
    return _compute_diff_prefix_hierarchy_multi(
        [prefix_groups_a, prefix_groups_b], both_keys
    )


def _compute_diff_prefix_hierarchy_multi(prefix_groups_list, in_all_keys):
    """Prefix parents for IPAM keys present on every diff side."""
    if not prefix_groups_list:
        return {}
    in_all_set = set(in_all_keys)
    common_prefix_keys = set(prefix_groups_list[0].keys())
    for prefix_groups in prefix_groups_list[1:]:
        common_prefix_keys &= set(prefix_groups.keys())
    hierarchy = {}
    for key in common_prefix_keys:
        leaf_sets = [prefix_groups[key]["leaf_keys"] for prefix_groups in prefix_groups_list]
        intersection_leaves = leaf_sets[0]
        for leaf_set in leaf_sets[1:]:
            intersection_leaves &= leaf_set
        intersection_leaves &= in_all_set
        if not intersection_leaves:
            continue
        first = prefix_groups_list[0][key]
        second = prefix_groups_list[1][key] if len(prefix_groups_list) > 1 else first
        hierarchy[key] = {
            "key": key,
            "leaf_keys": intersection_leaves,
            "entry_a": first["entry"],
            "entry_b": second["entry"],
        }
    return hierarchy


def _collect_addr_tree_leaf_map(nodes, path_prefix=None):
    """Map compare-key -> shallow leaf node copy plus all source object names."""
    if path_prefix is None:
        path_prefix = []
    found = {}
    for node in nodes or []:
        kind = node.get("kind")
        if kind == "group":
            branch = path_prefix + [node["name"]]
            found.update(
                _collect_addr_tree_leaf_map(node.get("children") or [], branch)
            )
        elif kind == "category":
            found.update(
                _collect_addr_tree_leaf_map(node.get("children") or [], path_prefix)
            )
        else:
            key = _addr_leaf_compare_key(node, path_prefix)
            if not key:
                continue
            if key not in found:
                src = _addr_leaf_source_object(node)
                found[key] = {
                    "kind": "leaf",
                    "name": node.get("name") or key,
                    "url": node.get("url") or "#",
                    "ip_ref": node.get("ip_ref"),
                    "prefix_display_cidr": node.get("prefix_display_cidr"),
                    "prefix_display_netmask": node.get("prefix_display_netmask"),
                    "related_refs": node.get("related_refs"),
                    "source_objects": [src] if src else [],
                    "children": [],
                }
            else:
                _addr_append_leaf_source(found[key], node)
    return found


def _addr_side_has_name_conflict(entry):
    """True when one side resolves the same IPAM key via multiple object names."""
    return len(_addr_source_name_set(entry)) > 1


def _addr_cross_side_name_conflict(entry_a, entry_b):
    """True when both sides share an IPAM key but with different object names."""
    names_a = _addr_source_name_set(entry_a)
    names_b = _addr_source_name_set(entry_b)
    if not names_a or not names_b:
        return False
    return names_a != names_b


def _addr_diff_fund_detail(entry, *, other_entry=None, label_a="", label_b=""):
    """Build tooltip payload for a diff fund marker."""
    names_a = sorted(_addr_source_name_set(entry))
    if other_entry is None:
        if len(names_a) < 2:
            return None
        return {"same_side": True, "names": names_a}
    names_b = sorted(_addr_source_name_set(other_entry))
    if names_a == names_b and len(names_a) <= 1:
        return None
    detail = {
        "names_a": names_a,
        "names_b": names_b,
        "label_a": str(label_a),
        "label_b": str(label_b),
    }
    if _addr_side_has_name_conflict(entry):
        detail["same_side_a"] = True
    if _addr_side_has_name_conflict(other_entry):
        detail["same_side_b"] = True
    return detail


def _addr_diff_fund_tooltip(detail):
    """Human-readable tooltip for a diff fund marker."""
    from django.utils.translation import gettext as _

    if not detail:
        return str(_("Same IP address/range/prefix, but different object names"))
    if detail.get("same_side"):
        names = ", ".join(detail.get("names") or [])
        return str(
            _("Same IP address/range/prefix linked to multiple object names: %(names)s")
            % {"names": names}
        )
    if detail.get("multi_side"):
        parts = []
        for side in detail.get("sides") or []:
            names = ", ".join(side.get("names") or [])
            parts.append(f"{side.get('label') or '?'}: {names}")
        return str(
            _(
                "Same IP address/range/prefix, but different object names "
                "(%(details)s)"
            )
            % {"details": "; ".join(parts)}
        )
    names_a = ", ".join(detail.get("names_a") or [])
    names_b = ", ".join(detail.get("names_b") or [])
    return str(
        _(
            "Same IP address/range/prefix, but different object names "
            "(%(side_a)s: %(names_a)s; %(side_b)s: %(names_b)s)"
        )
        % {
            "side_a": detail.get("label_a") or "A",
            "side_b": detail.get("label_b") or "B",
            "names_a": names_a,
            "names_b": names_b,
        }
    )


def _addr_diff_fund_detail_multi(entries, labels):
    """Tooltip payload when an IPAM key differs across multiple diff sides."""
    sides = []
    for index, entry in enumerate(entries):
        if not entry:
            continue
        names = sorted(_addr_source_name_set(entry))
        if not names:
            continue
        label = labels[index] if index < len(labels) else str(index + 1)
        sides.append({"label": str(label), "names": names})
    if not sides:
        return None
    if len(sides) == 1 and len(sides[0]["names"]) < 2:
        return None
    if len(sides) == 1:
        return {"same_side": True, "names": sides[0]["names"]}
    return {
        "multi_side": True,
        "sides": sides,
        "label_a": sides[0]["label"],
        "label_b": sides[1]["label"],
        "names_a": sides[0]["names"],
        "names_b": sides[1]["names"],
    }


def _addr_entries_is_diff_fund(entries, labels):
    """Whether entries for one IPAM key should be flagged as a diff fund."""
    entries = [entry for entry in entries if entry]
    if not entries:
        return False, None
    for entry in entries:
        if _addr_side_has_name_conflict(entry):
            return True, _addr_diff_fund_detail_multi(entries, labels)
    name_sets = [_addr_source_name_set(entry) for entry in entries]
    unique_sets = {frozenset(name_set) for name_set in name_sets}
    if len(unique_sets) > 1:
        return True, _addr_diff_fund_detail_multi(entries, labels)
    return False, None


def _addr_entry_is_diff_fund(entry, *, other_entry=None, label_a="", label_b=""):
    """Whether this IPAM key should be flagged as a diff fund."""
    if _addr_side_has_name_conflict(entry):
        return True
    if other_entry is not None and _addr_cross_side_name_conflict(entry, other_entry):
        return True
    return False


def _enrich_diff_name_pill_fields(node, entry, *, other_entry=None, diff_status):
    """Add diff_name_a/b, diff_url_a/b, diff_same_name for two-color name pills."""
    name = str(entry.get("name") or "").strip()
    url = entry.get("url") or "#"

    if diff_status == "only_a":
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_same_name"] = True
        return
    if diff_status == "only_b":
        node["diff_name_b"] = name
        node["diff_url_b"] = url
        node["diff_same_name"] = True
        return

    if other_entry is None:
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_same_name"] = True
        return

    other_name = str(other_entry.get("name") or "").strip()
    other_url = other_entry.get("url") or "#"
    names_a = _addr_source_name_set(entry)
    names_b = _addr_source_name_set(other_entry)
    if names_a == names_b and len(names_a) <= 1:
        node["diff_same_name"] = True
        node["diff_name_a"] = name or other_name
        node["diff_url_a"] = url
    else:
        node["diff_same_name"] = False
        node["diff_name_a"] = name
        node["diff_url_a"] = url
        node["diff_name_b"] = other_name
        node["diff_url_b"] = other_url


def _shallow_addr_leaf_for_diff(
    node,
    *,
    diff_status,
    diff_fund=False,
    fund_detail=None,
    other_entry=None,
    diff_present_labels=None,
):
    """Return a display leaf with diff_status for grouped diff output."""
    leaf = {
        "kind": "leaf",
        "name": node.get("name") or "",
        "url": node.get("url") or "#",
        "ip_ref": node.get("ip_ref"),
        "prefix_display_cidr": node.get("prefix_display_cidr"),
        "prefix_display_netmask": node.get("prefix_display_netmask"),
        "related_refs": node.get("related_refs"),
        "diff_status": diff_status,
        "children": [],
    }
    if diff_present_labels:
        leaf["diff_present_labels"] = list(diff_present_labels)
    _enrich_diff_name_pill_fields(
        leaf, node, other_entry=other_entry, diff_status=diff_status
    )
    if diff_fund:
        leaf["diff_fund"] = True
        if fund_detail:
            leaf["fund_detail"] = fund_detail
            leaf["fund_tooltip"] = _addr_diff_fund_tooltip(fund_detail)
    _enrich_addr_tree_copy_lines(leaf)
    return leaf


def _build_addr_diff_group(name, leaves, *, diff_group, diff_present_labels=None):
    """One diff section (only A / only B / both) as an address-tree group node."""
    if not leaves:
        return None
    group = {
        "kind": "group",
        "name": name,
        "url": "#",
        "diff_group": diff_group,
        "ip_ref": None,
        "children": leaves,
    }
    if diff_present_labels:
        group["diff_present_labels"] = list(diff_present_labels)
    _enrich_addr_tree_leaf_counts(group)
    _enrich_addr_tree_copy_lines(group)
    return group


def _diff_ipam_prefix_for_intersection_node(node):
    """Return the NetBox Prefix used for IPAM hierarchy nesting."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _ipam_obj_from_ip_ref(ip_ref)
    if ipam_obj is None:
        return None
    try:
        from ipam.models import Prefix

        if isinstance(ipam_obj, Prefix):
            return ipam_obj
    except ImportError:
        pass
    return None


def _intersection_node_compare_key(node):
    """Stable compare key for an intersection tree node."""
    ip_ref = node.get("ip_ref") or {}
    if ip_ref.get("str"):
        return str(ip_ref["str"]).strip().lower()
    return str(node.get("name") or "").strip().lower()


def _build_diff_ipam_hierarchy_prefix_node(prefix_key, entry_a, entry_b):
    """Structural prefix parent in the intersection tree (not a diff pair leaf)."""
    node = {
        "kind": "group",
        "name": entry_a.get("name") or entry_b.get("name") or prefix_key,
        "url": entry_a.get("url") or entry_b.get("url") or "#",
        "ip_ref": entry_a.get("ip_ref") or entry_b.get("ip_ref"),
        "prefix_display_cidr": entry_a.get("prefix_display_cidr")
        or entry_b.get("prefix_display_cidr")
        or prefix_key,
        "prefix_display_netmask": entry_a.get("prefix_display_netmask")
        or entry_b.get("prefix_display_netmask"),
        "related_refs": entry_a.get("related_refs") or entry_b.get("related_refs"),
        "diff_ipam_hierarchy_prefix": True,
        "children": [],
    }
    ip_ref = node.get("ip_ref")
    if ip_ref:
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
    elif node.get("prefix_display_cidr"):
        prefix = _lookup_ipam_prefix_for_cidr(node["prefix_display_cidr"])
        if prefix is not None:
            _enrich_ipa_node_from_resolved_prefix(node, prefix)
    _enrich_addr_tree_leaf_counts(node)
    return node


def _build_diff_ipam_hierarchy_prefix_node_from_prefix(prefix):
    """Structural prefix parent when only a NetBox Prefix object is known."""
    node = {
        "kind": "group",
        "name": str(prefix),
        "url": prefix.get_absolute_url(),
        "diff_ipam_hierarchy_prefix": True,
        "children": [],
    }
    _enrich_ipa_node_from_resolved_prefix(node, prefix)
    _enrich_addr_tree_leaf_counts(node)
    return node


def _lookup_containing_prefix_for_intersection_node(node):
    """Most specific NetBox Prefix containing an intersection pair node."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _ipam_obj_from_ip_ref(ip_ref)
    try:
        from ipam.models import IPAddress, Prefix

        if isinstance(ipam_obj, Prefix):
            return ipam_obj
        if isinstance(ipam_obj, IPAddress):
            ip_str = str(ipam_obj.address).split("/")[0]
            matches = list(Prefix.objects.filter(prefix__net_contains=ip_str))
            matches.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
            return matches[0] if matches else None
    except Exception:
        pass

    cidr = ip_ref.get("str") or node.get("prefix_display_cidr")
    if not cidr:
        return None
    try:
        import ipaddress

        from ipam.models import Prefix

        net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        host = str(net.network_address)
        matches = list(Prefix.objects.filter(prefix__net_contains=host))
        matches.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
        return matches[0] if matches else None
    except Exception:
        return None


def _net_contains_ip_key(prefix_net, leaf_key):
    """True when *leaf_key* is contained in *prefix_net* but is not the same network."""
    import ipaddress

    try:
        leaf_net = ipaddress.ip_network(str(leaf_key).strip(), strict=False)
    except ValueError:
        return False
    if leaf_net == prefix_net:
        return False
    return leaf_net.subnet_of(prefix_net)


def _reorganize_diff_leaves_under_prefix_hierarchy(
    leaves,
    prefix_hierarchy=None,
    *,
    assignable_child=None,
):
    """
    Nest diff leaves under structural prefix parents using NetBox IPAM Prefix
    parent chains. Individual leaf nodes are kept when not fully covered.
    """
    if not leaves:
        return []

    import ipaddress

    if assignable_child is None:
        assignable_child = lambda child: child.get("diff_intersection_pair")

    prefix_hierarchy = prefix_hierarchy or {}
    key_to_leaf = {}
    for node in leaves:
        key = _intersection_node_compare_key(node)
        if key:
            key_to_leaf[key] = node

    assigned = set()
    prefix_nodes = {}

    for prefix_key, info in prefix_hierarchy.items():
        parent = _build_diff_ipam_hierarchy_prefix_node(
            prefix_key, info["entry_a"], info["entry_b"]
        )
        prefix_nodes[prefix_key] = parent
        try:
            prefix_net = ipaddress.ip_network(prefix_key, strict=False)
        except ValueError:
            prefix_net = None
        for leaf_key in info.get("leaf_keys") or ():
            child = key_to_leaf.get(leaf_key)
            if child is None:
                continue
            if prefix_net is not None and not _net_contains_ip_key(
                prefix_net, leaf_key
            ):
                continue
            parent.setdefault("children", []).append(child)
            assigned.add(id(child))

    for node in leaves:
        if id(node) in assigned:
            continue
        prefix = _lookup_containing_prefix_for_intersection_node(node)
        if prefix is None:
            continue
        prefix_key = str(prefix).strip().lower()
        if prefix_key not in prefix_nodes:
            prefix_nodes[prefix_key] = (
                _build_diff_ipam_hierarchy_prefix_node_from_prefix(prefix)
            )
        prefix_nodes[prefix_key].setdefault("children", []).append(node)
        assigned.add(id(node))

    forest = [node for node in leaves if id(node) not in assigned]

    prefix_forest_candidates = []
    for parent in prefix_nodes.values():
        children = parent.get("children") or []
        nested_children = [
            child for child in children if assignable_child(child)
        ]
        if not nested_children:
            continue
        parent["children"] = sorted(nested_children, key=_ipa_object_tree_sort_key)
        _enrich_addr_tree_leaf_counts(parent)
        prefix_forest_candidates.append(parent)

    if not prefix_forest_candidates:
        return sorted(forest, key=_ipa_object_tree_sort_key)

    prefix_pk_to_node = {}
    node_prefix = {}
    for node in prefix_forest_candidates:
        prefix = _diff_ipam_prefix_for_intersection_node(node)
        if prefix is None:
            continue
        node_prefix[id(node)] = prefix
        prefix_pk_to_node.setdefault(prefix.pk, node)

    nested_prefix_forest = []
    for node in sorted(prefix_forest_candidates, key=_ipa_object_tree_sort_key):
        prefix = node_prefix.get(id(node))
        parent = (
            _ipa_deepest_cell_ancestor_node(prefix, prefix_pk_to_node)
            if prefix is not None
            else None
        )
        if parent is None:
            net = _addr_tree_node_network(node)
            parent = (
                _ipa_find_deepest_containing_node(nested_prefix_forest, net)
                if net
                else None
            )
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["kind"] = "group"
        else:
            nested_prefix_forest.append(node)

    forest.extend(nested_prefix_forest)
    return sorted(forest, key=_ipa_object_tree_sort_key)


def _reorganize_diff_ipam_intersection_tree(pair_nodes, prefix_hierarchy=None):
    """Nest intersection pair leaves under structural prefix parents."""
    return _reorganize_diff_leaves_under_prefix_hierarchy(
        pair_nodes, prefix_hierarchy
    )


def _suppress_diff_status_on_both_group_leaves(nodes):
    """Drop redundant per-leaf 'both' styling inside the In-both diff group."""
    for node in nodes or []:
        if node.get("kind") == "leaf" and node.get("diff_status") == "both":
            node["diff_suppress_status"] = True
        for child in node.get("children") or []:
            _suppress_diff_status_on_both_group_leaves([child])


def _reorganize_diff_both_group_leaves(leaves, prefix_hierarchy=None):
    """Roll up shared /24 (etc.) prefixes in the In-both diff group."""
    nodes = _reorganize_diff_leaves_under_prefix_hierarchy(
        leaves,
        prefix_hierarchy,
        assignable_child=lambda child: child.get("diff_status") == "both",
    )
    _suppress_diff_status_on_both_group_leaves(nodes)
    for node in nodes:
        _enrich_addr_tree_copy_lines(node)
    return nodes


def _build_diff_ipam_intersection_node(
    key,
    entries,
    *,
    labels,
    label_a="A",
    label_b="B",
):
    """Single leaf for one IPAM key present on all diff sides."""
    entries = [entry for entry in entries if entry]
    if not entries:
        return None
    entry_a = entries[0]
    entry_b = entries[1] if len(entries) > 1 else None
    is_fund, fund_detail = _addr_entries_is_diff_fund(entries, labels)
    if not is_fund and entry_b is not None:
        is_fund = _addr_entry_is_diff_fund(
            entry_a,
            other_entry=entry_b,
            label_a=label_a,
            label_b=label_b,
        )
        if is_fund:
            fund_detail = _addr_diff_fund_detail(
                entry_a,
                other_entry=entry_b,
                label_a=label_a,
                label_b=label_b,
            )
    ip_ref = entry_a.get("ip_ref") or (entry_b or {}).get("ip_ref")
    is_prefix = (ip_ref or {}).get("type") == _FIELD_TYPE_LABELS["prefix"]
    leaf = {
        "kind": "group" if is_prefix else "leaf",
        "name": entry_a.get("name") or (entry_b or {}).get("name") or key,
        "url": entry_a.get("url") or (entry_b or {}).get("url") or "#",
        "ip_ref": ip_ref,
        "prefix_display_cidr": entry_a.get("prefix_display_cidr")
        or (entry_b or {}).get("prefix_display_cidr"),
        "prefix_display_netmask": entry_a.get("prefix_display_netmask")
        or (entry_b or {}).get("prefix_display_netmask"),
        "related_refs": entry_a.get("related_refs") or (entry_b or {}).get("related_refs"),
        "diff_status": "both",
        "diff_intersection_pair": True,
        "children": [],
    }
    _enrich_diff_name_pill_fields(
        leaf, entry_a, other_entry=entry_b, diff_status="both"
    )
    if is_fund:
        leaf["diff_fund"] = True
        if fund_detail:
            leaf["fund_detail"] = fund_detail
            leaf["fund_tooltip"] = _addr_diff_fund_tooltip(fund_detail)
    if ip_ref:
        _attach_addr_node_prefix_display(leaf, ip_ref=ip_ref)
    _enrich_addr_tree_copy_lines(leaf)
    return leaf


def _build_diff_ipam_intersection_pair_node(
    key, entry_a, entry_b, *, label_a="A", label_b="B"
):
    """Single leaf for one IPAM key present on both diff sides (combined name pill)."""
    return _build_diff_ipam_intersection_node(
        key,
        [entry_a, entry_b],
        labels=[label_a, label_b],
        label_a=label_a,
        label_b=label_b,
    )


def _build_diff_ipam_intersection_tree(
    map_a,
    map_b,
    both_keys,
    *,
    label_a="A",
    label_b="B",
    prefix_hierarchy=None,
):
    """IPAM hierarchy tree for IPAM keys present on both diff sides."""
    return _build_diff_ipam_intersection_tree_multi(
        [map_a, map_b],
        both_keys,
        labels=[label_a, label_b],
        prefix_hierarchy=prefix_hierarchy,
    )


def _build_diff_ipam_intersection_tree_multi(
    maps,
    in_all_keys,
    *,
    labels,
    prefix_hierarchy=None,
):
    """IPAM hierarchy tree for IPAM keys present on every diff side."""
    if not in_all_keys:
        return []

    pair_nodes = []
    for key in sorted(in_all_keys):
        entries = [side_map[key] for side_map in maps if key in side_map]
        node = _build_diff_ipam_intersection_node(
            key,
            entries,
            labels=labels,
            label_a=labels[0] if labels else "A",
            label_b=labels[1] if len(labels) > 1 else labels[0] if labels else "B",
        )
        if node is not None:
            pair_nodes.append(node)
    nodes = _reorganize_diff_ipam_intersection_tree(
        pair_nodes, prefix_hierarchy=prefix_hierarchy
    )
    for node in nodes:
        _enrich_addr_tree_copy_lines(node)
    return nodes


def _type_counts_for_diff_addr_entry(entry, counts):
    """Add one diff leaf-map entry to subnet/range/IP totals."""
    ip_ref = entry.get("ip_ref") or {}
    ref_type = ip_ref.get("type")
    if ref_type == _FIELD_TYPE_LABELS["prefix"]:
        counts["count_subnets"] += 1
    elif ref_type == _FIELD_TYPE_LABELS["range"]:
        counts["count_ranges"] += 1
    elif ref_type == _FIELD_TYPE_LABELS["ip_address"]:
        counts["count_ips"] += 1
    else:
        counts["count_ips"] += 1


def _type_counts_for_diff_addr_keys(
    map_a, map_b, only_a_keys, only_b_keys, both_keys
):
    """Subnet/range/IP totals across disjoint diff buckets (no double-count)."""
    return _type_counts_for_multi_diff(
        [map_a, map_b],
        [only_a_keys, only_b_keys],
        both_keys,
        [],
    )


def _type_counts_for_multi_diff(maps, only_keys_by_side, in_all_keys, in_some_keys):
    """Subnet/range/IP totals across disjoint multi-side diff buckets."""
    counts = {"count_subnets": 0, "count_ranges": 0, "count_ips": 0}
    for side_index, keys in enumerate(only_keys_by_side):
        side_map = maps[side_index]
        for key in keys:
            _type_counts_for_diff_addr_entry(side_map[key], counts)
    for key in in_all_keys:
        _type_counts_for_diff_addr_entry(maps[0][key], counts)
    for key in in_some_keys:
        for side_map in maps:
            if key in side_map:
                _type_counts_for_diff_addr_entry(side_map[key], counts)
                break
    return counts


def _diff_status_for_exclusive_side(side_index, side_count):
    """Map an exclusive side index to legacy diff_status / diff_group slugs."""
    if side_count == 2:
        return ("only_a", "only-a") if side_index == 0 else ("only_b", "only-b")
    return (f"only_side_{side_index}", f"only-side-{side_index}")


def _build_addr_diff_analysis_from_sides(side_specs):
    """
    IP Analysis: diff N object sets (N >= 2).

    side_specs: list of {"objs": [...], "label": str}
    """
    if len(side_specs) < 2:
        return []

    labels = [str(spec.get("label") or chr(65 + index)) for index, spec in enumerate(side_specs)]
    maps = []
    prefix_groups_list = []
    has_supported = False
    for spec in side_specs:
        supported = [
            obj for obj in spec.get("objs") or [] if obj and _object_supports_addr_analysis(obj)
        ]
        if supported:
            has_supported = True
        nodes, _lines = _build_addr_tree_nodes(supported, all_copy_prefix="")
        maps.append(_collect_addr_tree_leaf_map(nodes))
        prefix_groups_list.append(_collect_addr_tree_prefix_groups(nodes))

    if not has_supported:
        return []

    side_count = len(maps)
    all_indices = set(range(side_count))
    all_keys = set()
    key_sides = {}
    for side_index, side_map in enumerate(maps):
        for key in side_map:
            all_keys.add(key)
            key_sides.setdefault(key, set()).add(side_index)

    only_keys_by_side = [[] for _ in range(side_count)]
    in_all_keys = []
    in_some_keys = []
    for key in sorted(all_keys):
        present = key_sides[key]
        if present == all_indices:
            in_all_keys.append(key)
        elif len(present) == 1:
            only_keys_by_side[next(iter(present))].append(key)
        else:
            in_some_keys.append(key)

    prefix_hierarchy = _compute_diff_prefix_hierarchy_multi(
        prefix_groups_list, in_all_keys
    )
    fund_count = 0

    intersection_tree = _build_diff_ipam_intersection_tree_multi(
        maps,
        in_all_keys,
        labels=labels,
        prefix_hierarchy=prefix_hierarchy,
    )

    groups = []
    for side_index, label in enumerate(labels):
        keys = only_keys_by_side[side_index]
        if not keys:
            continue
        status, slug = _diff_status_for_exclusive_side(side_index, side_count)
        leaves = []
        side_map = maps[side_index]
        for key in keys:
            entry = side_map[key]
            is_fund = _addr_side_has_name_conflict(entry)
            fund_detail = None
            if is_fund:
                fund_count += 1
                fund_detail = _addr_diff_fund_detail_multi([entry], [label])
            leaves.append(
                _shallow_addr_leaf_for_diff(
                    entry,
                    diff_status=status,
                    diff_fund=is_fund,
                    fund_detail=fund_detail,
                    other_entry=None,
                )
            )
        group = _build_addr_diff_group(f"Only in {label}", leaves, diff_group=slug)
        if group:
            groups.append(group)

    if in_some_keys:
        in_some_by_presence = {}
        for key in in_some_keys:
            present_indices = tuple(sorted(key_sides[key]))
            in_some_by_presence.setdefault(present_indices, []).append(key)
        for present_indices in sorted(in_some_by_presence):
            present_labels = [labels[index] for index in present_indices]
            leaves = []
            for key in in_some_by_presence[present_indices]:
                entries = [maps[index][key] for index in present_indices]
                is_fund, fund_detail = _addr_entries_is_diff_fund(entries, present_labels)
                if is_fund:
                    fund_count += 1
                primary_entry = entries[0]
                other_entry = entries[1] if len(entries) > 1 else None
                leaves.append(
                    _shallow_addr_leaf_for_diff(
                        primary_entry,
                        diff_status="in_some",
                        diff_fund=is_fund,
                        fund_detail=fund_detail,
                        other_entry=other_entry,
                        diff_present_labels=present_labels,
                    )
                )
            group = _build_addr_diff_group(
                "In some",
                leaves,
                diff_group="in-some",
                diff_present_labels=present_labels,
            )
            if group:
                groups.append(group)

    if in_all_keys:
        overlap_name = "In both" if side_count == 2 else "In all"
        overlap_slug = "both" if side_count == 2 else "in-all"
        leaves = []
        for key in in_all_keys:
            entries = [side_map[key] for side_map in maps]
            is_fund, fund_detail = _addr_entries_is_diff_fund(entries, labels)
            if not is_fund and side_count == 2:
                is_fund = _addr_entry_is_diff_fund(
                    entries[0],
                    other_entry=entries[1],
                    label_a=labels[0],
                    label_b=labels[1],
                )
                if is_fund:
                    fund_detail = _addr_diff_fund_detail(
                        entries[0],
                        other_entry=entries[1],
                        label_a=labels[0],
                        label_b=labels[1],
                    )
            if is_fund:
                fund_count += 1
            leaves.append(
                _shallow_addr_leaf_for_diff(
                    entries[0],
                    diff_status="both",
                    diff_fund=is_fund,
                    fund_detail=fund_detail,
                    other_entry=entries[1] if len(entries) > 1 else None,
                )
            )
        leaves = _reorganize_diff_both_group_leaves(
            leaves, prefix_hierarchy=prefix_hierarchy
        )
        group = _build_addr_diff_group(overlap_name, leaves, diff_group=overlap_slug)
        if group:
            groups.append(group)

    if not groups:
        return []

    all_copy_lines = []
    for group in groups:
        all_copy_lines.extend(group.get("copy_lines") or [])

    type_counts = _type_counts_for_multi_diff(
        maps, only_keys_by_side, in_all_keys, in_some_keys
    )
    total_leaf_count = sum(len(keys) for keys in only_keys_by_side)
    total_leaf_count += len(in_all_keys) + len(in_some_keys)

    diff_summary = {
        "side_count": side_count,
        "labels": labels,
        "only_by_side": [
            {"label": label, "count": len(only_keys_by_side[index])}
            for index, label in enumerate(labels)
        ],
        "in_all": len(in_all_keys),
        "in_some": len(in_some_keys),
        "fund": fund_count,
    }
    if side_count == 2:
        diff_summary.update(
            {
                "only_a": len(only_keys_by_side[0]),
                "only_b": len(only_keys_by_side[1]),
                "both": len(in_all_keys),
                "label_a": labels[0],
                "label_b": labels[1],
            }
        )

    return [
        {
            "field_name": "",
            "field_slug": "diff",
            "types": [
                {
                    "type_name": "",
                    "type_config": None,
                    "nodes": groups,
                    "intersection_tree": intersection_tree,
                    "intersection_leaf_count": len(in_all_keys),
                    "all_copy_lines": all_copy_lines,
                    "leaf_count": total_leaf_count,
                    "count_subnets": type_counts["count_subnets"],
                    "count_ranges": type_counts["count_ranges"],
                    "count_ips": type_counts["count_ips"],
                    "has_objects": True,
                    "diff_summary": diff_summary,
                }
            ],
        }
    ]


def _build_addr_diff_analysis(objs_a, objs_b, *, label_a="A", label_b="B"):
    """IP Analysis: diff two object sets into only-A / only-B / both groups."""
    return _build_addr_diff_analysis_from_sides(
        [
            {"objs": objs_a, "label": label_a},
            {"objs": objs_b, "label": label_b},
        ]
    )


def _build_multi_object_addr_analysis(objs):
    """IP Analysis: merged tree for one or more selected objects."""
    supported = [o for o in objs if o and _object_supports_addr_analysis(o)]
    if not supported:
        return []
    nodes, all_copy_lines = _build_addr_tree_nodes(supported)
    if not nodes:
        return []
    type_counts = _type_counts_for_addr_nodes(nodes)
    return [
        {
            "field_name": "",
            "field_slug": "selected",
            "types": [
                {
                    "type_name": "",
                    "type_config": None,
                    "nodes": nodes,
                    "all_copy_lines": all_copy_lines,
                    "leaf_count": type_counts["count_ips"],
                    "count_subnets": type_counts["count_subnets"],
                    "count_ranges": type_counts["count_ranges"],
                    "count_ips": type_counts["count_ips"],
                    "count_duplicates": _count_addr_tree_duplicates(nodes),
                    "has_objects": True,
                }
            ],
        }
    ]


def _leaf_count_for_addr_analysis(sections) -> int:
    total = 0
    for section in sections or []:
        for type_block in section.get("types") or []:
            total += int(type_block.get("count_ips") or type_block.get("leaf_count") or 0)
    return total


def _type_counts_for_addr_analysis(sections) -> dict:
    """Aggregate subnet/range/IP counts from addr_analysis sections."""
    totals = {"count_subnets": 0, "count_ranges": 0, "count_ips": 0}
    for section in sections or []:
        for type_block in section.get("types") or []:
            if type_block.get("count_ips") is not None:
                totals["count_subnets"] += int(type_block.get("count_subnets") or 0)
                totals["count_ranges"] += int(type_block.get("count_ranges") or 0)
                totals["count_ips"] += int(type_block.get("count_ips") or 0)
            elif type_block.get("nodes"):
                node_counts = _type_counts_for_addr_nodes(type_block["nodes"])
                for key in totals:
                    totals[key] += node_counts[key]
    return totals


def _ipa_object_tree_type_counts(nodes):
    """Count prefix/range/IP objects in the cell object tree (shallow, no drilldown)."""
    counts = {"count_subnets": 0, "count_ranges": 0, "count_ips": 0}

    def _walk(node):
        children = node.get("children") or []
        if children:
            for child in children:
                _walk(child)
            return
        ip_ref = node.get("ip_ref") or {}
        ref_type = ip_ref.get("type")
        if ref_type == _FIELD_TYPE_LABELS["prefix"]:
            counts["count_subnets"] += 1
        elif ref_type == _FIELD_TYPE_LABELS["range"]:
            counts["count_ranges"] += 1
        elif ref_type == _FIELD_TYPE_LABELS["ip_address"]:
            counts["count_ips"] += 1

    for node in nodes or []:
        _walk(node)
    return counts


def _count_addr_tree_duplicates(nodes):
    """Count addr-tree nodes flagged as contained duplicates (excluded from IP totals)."""
    count = 0

    def _walk(node):
        nonlocal count
        if node.get("count_duplicate"):
            count += 1
        for child in node.get("children") or []:
            _walk(child)

    for node in nodes or []:
        _walk(node)
    return count


def _count_ipa_object_tree_duplicates(nodes):
    """Count object-tree warning nodes (not addr-tree IP totals).

    Each flagged node counts once:
    - ``subnet_contained_in``: cell object already covered by a parent prefix/group
    - ``is_doppelt``: same object listed twice in the rule cell
    - ``object_duplicate``: same object identity appears again elsewhere in the tree
    """
    count = 0

    def _walk(node):
        nonlocal count
        if (
            node.get("subnet_contained_in")
            or node.get("is_doppelt")
            or node.get("object_duplicate")
        ):
            count += 1
        for child in node.get("children") or []:
            _walk(child)

    for node in nodes or []:
        _walk(node)
    return count


def _resolve_summary_type_counts(addr_analysis, object_tree=None) -> dict:
    """Summary counts for the All row; fall back to object-tree counts when needed."""
    counts = _type_counts_for_addr_analysis(addr_analysis)
    if not any(counts.values()) and object_tree:
        counts = _ipa_object_tree_type_counts(object_tree)
    if object_tree:
        counts["count_duplicates"] = _count_ipa_object_tree_duplicates(object_tree)
    else:
        dup_total = 0
        for section in addr_analysis or []:
            for type_block in section.get("types") or []:
                dup_total += _count_addr_tree_duplicates(type_block.get("nodes") or [])
        counts["count_duplicates"] = dup_total
    return counts


def _apply_summary_type_counts_to_addr_analysis(addr_analysis, type_counts):
    """Mirror resolved All-row counts onto addr_analysis type blocks for templates/API."""
    if not addr_analysis or not type_counts:
        return
    for section in addr_analysis:
        for type_block in section.get("types") or []:
            type_block["count_subnets"] = type_counts.get("count_subnets") or 0
            type_block["count_ranges"] = type_counts.get("count_ranges") or 0
            type_block["count_ips"] = type_counts.get("count_ips") or 0
            type_block["leaf_count"] = type_counts.get("count_ips") or 0
            type_block["count_duplicates"] = type_counts.get("count_duplicates") or 0


def _build_ipa_object_columns(selections, objs):
    """IP Analysis: one table column per selected object (name + counter in header)."""
    columns = []
    for sel, obj in zip(selections, objs):
        analysis = _build_multi_object_addr_analysis([obj]) if obj else []
        columns.append(
            {
                "name": sel["name"],
                "ct": sel["ct"],
                "pk": sel["pk"],
                "leaf_count": _leaf_count_for_addr_analysis(analysis),
                "addr_analysis": analysis,
            }
        )
    return columns


def _parse_ipa_column_selections(request, col_suffix=""):
    """
    Parse repeated ip_ct/ip_pk/ip_name (or ip2_*) query params.
    Returns (selections, addr_analysis) where selections is
    [{"ct", "pk", "name"}, ...].
    """
    from django.contrib.contenttypes.models import ContentType as _CT

    prefix = f"ip{col_suffix}_"
    ct_list = request.GET.getlist(prefix + "ct")
    pk_list = request.GET.getlist(prefix + "pk")
    name_list = request.GET.getlist(prefix + "name")

    selections = []
    objs = []
    seen: set = set()

    for i, ct_str in enumerate(ct_list):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        name_hint = name_list[i] if i < len(name_list) else ""
        if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
            continue
        key = (int(ct_str), int(pk_str))
        if key in seen:
            continue
        try:
            ct = _CT.objects.get(pk=key[0])
            mc = ct.model_class()
            if not mc:
                continue
            obj = mc.objects.filter(pk=key[1]).first()
            if not obj:
                continue
            seen.add(key)
            name = getattr(obj, "name", None) or name_hint or str(obj)
            selections.append({"ct": str(key[0]), "pk": str(key[1]), "name": str(name)})
            objs.append(obj)
        except Exception:
            continue

    return selections, _build_ipa_object_columns(selections, objs)


def _ipa_object_expands_members(obj) -> bool:
    """True when the IP analyzer object tree should expand group members."""
    if getattr(obj, "address_type", None) == "address-group":
        return True
    if _addr_ip_ref(obj) is not None:
        return False
    return bool(_addr_group_members(obj))


def _attach_ipa_object_tree_ip_meta(node, obj):
    """Attach resolved IP/CIDR display fields to an object-tree node."""
    ip_ref = _addr_ip_ref(obj)
    if not ip_ref:
        return node
    node["ip_ref"] = _addr_ip_ref_node_dict(ip_ref)
    _attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)
    if node.get("children"):
        node["kind"] = "group"
    else:
        node["kind"] = "leaf"
    return node


def _build_ipa_object_tree_node(obj, *, ct_id=None, member_visited=None):
    """
    Shallow object hierarchy for the IP analyzer cell object tree.
    Expands address groups only (no IPAM prefix drilldown).
    """
    if member_visited is None:
        member_visited = set()

    if obj.pk in member_visited:
        return None
    member_visited = set(member_visited)
    member_visited.add(obj.pk)

    if ct_id is None:
        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(obj).pk

    name = str(getattr(obj, "name", obj) or obj)
    url = getattr(obj, "get_absolute_url", lambda: "#")()

    if _ipa_object_expands_members(obj):
        children = []
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        child_visited = set(member_visited)
        for sub in members:
            child = _build_ipa_object_tree_node(
                sub, member_visited=child_visited
            )
            if child:
                children.append(child)
        node = {
            "name": name,
            "url": url,
            "ct": str(ct_id),
            "pk": str(obj.pk),
            "kind": "group" if children else "leaf",
            "children": children,
        }
        return _attach_ipa_object_tree_ip_meta(node, obj)

    node = {
        "name": name,
        "url": url,
        "ct": str(ct_id),
        "pk": str(obj.pk),
        "kind": "leaf",
        "children": [],
    }
    return _attach_ipa_object_tree_ip_meta(node, obj)


def _ipa_object_tree_node_key(node):
    try:
        return (int(node.get("ct") or 0), int(node.get("pk") or 0))
    except (TypeError, ValueError):
        return None


def _collect_ipa_object_tree_keys(nodes):
    keys = set()
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        if key and key != (0, 0):
            keys.add(key)
        keys.update(_collect_ipa_object_tree_keys(node.get("children") or []))
    return keys


def _collapse_ipa_cell_object_tree_roots(nodes):
    """Drop root entries already shown under another root's member subtree."""
    if len(nodes) <= 1:
        return nodes
    covered = set()
    for root in nodes:
        for child in root.get("children") or []:
            covered.update(_collect_ipa_object_tree_keys([child]))
    return [
        node
        for node in nodes
        if _ipa_object_tree_node_key(node) not in covered
    ]


def _ipa_object_tree_sort_key(node):
    """Broader prefixes first (smaller prefix length), then stable name."""
    net = _addr_tree_node_network(node)
    if net is None:
        return (1, 999, node.get("name") or "")
    return (0, net.prefixlen, str(net.network_address), node.get("name") or "")


def _ipa_cidr_from_object_name(name):
    """Extract CIDR from NSM naming like ``g-10.0.0.0/8`` or ``n-10.1.0.0/16``."""
    import re

    match = re.match(r"^[gn]-(.+)$", (name or "").strip(), re.I)
    if not match:
        return None
    cidr = match.group(1).strip()
    return cidr if "/" in cidr else None


def _ipa_prefix_for_cell_object(obj):
    """Return the NetBox IPAM Prefix associated with a rules-cell object, if any."""
    from ipam.models import Prefix

    try:
        if isinstance(obj, Prefix):
            return obj
        related = _ipam_fk_object_for_addr_node(obj)
        if isinstance(related, Prefix):
            return related
    except Exception:
        pass

    cidr = _ipa_cidr_from_object_name(getattr(obj, "name", None))
    if not cidr:
        return None
    try:
        return Prefix.objects.filter(prefix=cidr).order_by("pk").first()
    except Exception:
        return None


def _enrich_ipa_node_from_resolved_prefix(node, prefix):
    """Attach ``ip_ref``/CIDR display when a prefix was inferred outside ``ip_ref``."""
    if not prefix or node.get("ip_ref"):
        return node
    try:
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(prefix)
        ip_ref = {
            "str": str(prefix),
            "url": prefix.get_absolute_url(),
            "type": _FIELD_TYPE_LABELS["prefix"],
            "ct": ct.pk,
            "pk": prefix.pk,
        }
        node["ip_ref"] = _addr_ip_ref_node_dict(ip_ref)
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
    except Exception:
        pass
    return node


def _ipa_deepest_cell_ancestor_node(prefix, prefix_pk_to_node):
    """Return the deepest cell node whose prefix is an IPAM parent of *prefix*."""
    if not prefix or not prefix_pk_to_node:
        return None
    try:
        parents = list(prefix.get_parents())
    except Exception:
        return None
    if not parents:
        return None
    best = None
    best_prefixlen = -1
    for ancestor in parents:
        ancestor_node = prefix_pk_to_node.get(ancestor.pk)
        if ancestor_node is None:
            continue
        try:
            prefixlen = ancestor.prefix.prefixlen
        except Exception:
            continue
        if prefixlen > best_prefixlen:
            best = ancestor_node
            best_prefixlen = prefixlen
    return best


def _ipa_find_deepest_containing_node(nodes, net):
    """Return the deepest node in *nodes* whose network strictly contains *net*."""
    best = None
    best_prefixlen = -1
    for node in nodes or []:
        parent_net = _addr_tree_node_network(node)
        if not parent_net or not net.subnet_of(parent_net) or net == parent_net:
            continue
        deeper = _ipa_find_deepest_containing_node(node.get("children") or [], net)
        if deeper:
            return deeper
        if parent_net.prefixlen > best_prefixlen:
            best = node
            best_prefixlen = parent_net.prefixlen
    return best


def _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(nodes, obj_by_key):
    """
    Nest sibling nodes using NetBox IPAM Prefix parent chains among cell objects.
    Falls back to pure CIDR containment when no IPAM parent match exists.
    """
    if not nodes:
        return nodes

    for node in nodes:
        children = node.get("children") or []
        if children:
            node["children"] = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(
                children, obj_by_key
            )

    if len(nodes) < 2:
        return nodes

    prefix_pk_to_node = {}
    node_prefix = {}

    for node in nodes:
        key = _ipa_object_tree_node_key(node)
        if not key:
            continue
        obj = obj_by_key.get(key)
        if obj is None:
            continue
        prefix = _ipa_prefix_for_cell_object(obj)
        if prefix is None:
            continue
        _enrich_ipa_node_from_resolved_prefix(node, prefix)
        node_prefix[id(node)] = prefix
        prefix_pk_to_node.setdefault(prefix.pk, node)

    forest = []
    for node in sorted(nodes, key=_ipa_object_tree_sort_key):
        parent = _ipa_deepest_cell_ancestor_node(
            node_prefix.get(id(node)), prefix_pk_to_node
        )
        if parent is None:
            net = _addr_tree_node_network(node)
            parent = _ipa_find_deepest_containing_node(forest, net) if net else None
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["kind"] = "group"
        else:
            forest.append(node)

    for node in forest:
        children = node.get("children") or []
        if children:
            node["children"] = sorted(children, key=_ipa_object_tree_sort_key)
    return forest


def _ipa_object_tree_containment_cidr(node):
    """Resolved CIDR string for containment warnings."""
    return (
        node.get("prefix_display_cidr")
        or (node.get("ip_ref") or {}).get("str")
        or ""
    )


def _mark_ipa_subnet_containment_warnings(nodes, ancestors=None):
    """
    Flag nodes whose resolved prefix is contained in an ancestor supernet.
    ``subnet_contained_in`` stores the root-most enclosing ancestor CIDR.
    """
    if ancestors is None:
        ancestors = []

    for node in nodes or []:
        net = _addr_tree_node_network(node)
        if net and ancestors:
            for anc in ancestors:
                anc_net = _addr_tree_node_network(anc)
                if anc_net and net.subnet_of(anc_net) and net != anc_net:
                    node["subnet_contained_in"] = _ipa_object_tree_containment_cidr(anc)
                    node["subnet_contained_in_name"] = anc.get("name") or ""
                    break

        next_ancestors = ancestors
        if _addr_tree_node_network(node):
            next_ancestors = ancestors + [node]
        _mark_ipa_subnet_containment_warnings(
            node.get("children") or [], next_ancestors
        )


def _mark_ipa_object_tree_duplicate_flags(
    nodes, *, is_root=False, seen=None, first_names=None, first_urls=None
):
    """
    Mark nodes whose object identity already appeared elsewhere in the tree.
    Root-level ``is_doppelt`` entries keep only the red marker (no duplicate badge).
    """
    if seen is None:
        seen = {}
        first_names = {}
        first_urls = {}

    for node in nodes or []:
        try:
            key = (int(node.get("ct") or 0), int(node.get("pk") or 0))
        except (TypeError, ValueError):
            key = None

        if key and key in seen:
            if not (is_root and node.get("is_doppelt")):
                node["object_duplicate"] = True
                node["object_duplicate_of"] = first_names.get(key, "")
                node["object_duplicate_of_url"] = first_urls.get(key, "")
        elif key:
            seen[key] = True
            first_names[key] = node.get("name") or ""
            first_urls[key] = node.get("url") or ""

        _mark_ipa_object_tree_duplicate_flags(
            node.get("children") or [],
            is_root=False,
            seen=seen,
            first_names=first_names,
            first_urls=first_urls,
        )


def _ipa_cell_object_tree_visible(nodes, raw_count):
    if raw_count > 1:
        return True
    for node in nodes or []:
        if node.get("is_doppelt") or node.get("children"):
            return True
    return False


def _mark_ipa_cell_direct_flags(nodes, cell_object_keys):
    """Mark only objects explicitly listed in the rule cell (not tree-expanded children)."""
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        if key and key in cell_object_keys:
            node["is_cell_direct"] = True
        else:
            node.pop("is_cell_direct", None)
        _mark_ipa_cell_direct_flags(node.get("children") or [], cell_object_keys)


def _build_ipa_cell_object_tree(raw_selections, obj_by_key):
    """
    Build ordered root nodes for objects referenced in a rules cell.
    ``raw_selections`` preserves duplicate ct/pk pairs (doppelt).
    """
    cell_object_keys: set[tuple[int, int]] = set()
    for sel in raw_selections or []:
        try:
            cell_object_keys.add((int(sel["ct"]), int(sel["pk"])))
        except (KeyError, TypeError, ValueError):
            continue

    nodes = []
    root_counts: dict[tuple[int, int], int] = {}

    for sel in raw_selections or []:
        try:
            key = (int(sel["ct"]), int(sel["pk"]))
        except (KeyError, TypeError, ValueError):
            continue
        obj = obj_by_key.get(key)
        if not obj:
            continue
        root_counts[key] = root_counts.get(key, 0) + 1
        node = _build_ipa_object_tree_node(obj, ct_id=key[0])
        if not node:
            continue
        node["is_doppelt"] = root_counts[key] > 1
        nodes.append(node)

    nodes = _collapse_ipa_cell_object_tree_roots(nodes)
    nodes = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(nodes, obj_by_key)
    nodes = sorted(nodes, key=_ipa_object_tree_sort_key)
    _mark_ipa_subnet_containment_warnings(nodes)
    _mark_ipa_object_tree_duplicate_flags(nodes, is_root=True)
    _mark_ipa_object_addr_drilldown_flags(nodes, obj_by_key)
    _mark_ipa_cell_direct_flags(nodes, cell_object_keys)
    return nodes


def _ipa_object_has_addr_drilldown(obj) -> bool:
    """True when lazy-loading should expose IPAM resolution beyond cell members."""
    if not obj or not _object_supports_addr_analysis(obj):
        return False
    if _ipa_object_expands_members(obj) and _addr_ip_ref(obj) is None:
        return False
    return True


def _mark_ipa_object_addr_drilldown_flags(nodes, obj_by_key=None):
    """Mark cell objects that can lazy-load an IPAM address drilldown on expand."""
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        drilldown = False
        if key and obj_by_key:
            obj = obj_by_key.get(key)
            if obj is not None:
                drilldown = _ipa_object_has_addr_drilldown(obj)
        elif node.get("ip_ref") or node.get("prefix_display_cidr"):
            drilldown = True
        if drilldown:
            node["addr_drilldown_lazy"] = True
        _mark_ipa_object_addr_drilldown_flags(node.get("children") or [], obj_by_key)


def _ipa_object_tree_csv_line(path_prefix, node):
    """One CSV row for a cell object, including subnet containment warnings."""
    row = list(path_prefix or [])
    ip_str = (
        node.get("prefix_display_cidr")
        or (node.get("ip_ref") or {}).get("str")
        or ""
    )
    ip_str = str(ip_str).strip()
    if ip_str and (not row or ip_str != row[-1]):
        row.append(ip_str)
    line = _addr_path_line(row)
    contained = node.get("subnet_contained_in")
    if contained:
        line = f"{line},warn duplicate→{contained}"
    return line


def _flatten_ipa_object_tree_copy_lines(nodes, path_prefix=None):
    """CSV copy lines for cell object tree nodes (with containment warnings)."""
    if path_prefix is None:
        path_prefix = []
    lines = []
    for node in nodes or []:
        name = str(node.get("name") or "").strip()
        branch = path_prefix + ([name] if name else [])
        if node.get("ip_ref") or node.get("prefix_display_cidr"):
            lines.append(_ipa_object_tree_csv_line(branch, node))
        lines.extend(_flatten_ipa_object_tree_copy_lines(node.get("children") or [], branch))
    return lines


def _apply_object_tree_copy_lines(addr_analysis, object_tree):
    """Replace All-level CSV paths when the cell object tree is shown."""
    if not object_tree or not addr_analysis:
        return addr_analysis
    lines = _prefix_addr_copy_lines(
        _flatten_ipa_object_tree_copy_lines(object_tree),
        "all",
    )
    if not lines:
        return addr_analysis
    for section in addr_analysis:
        for type_block in section.get("types") or []:
            type_block["all_copy_lines"] = lines
    return addr_analysis


def _build_object_address_analysis(_rulebook, obj, content_type_id):
    """Address analysis for a single object (IP Analysis — object only, no src/dst)."""
    if not obj or not content_type_id:
        return []
    return _build_multi_object_addr_analysis([obj])


