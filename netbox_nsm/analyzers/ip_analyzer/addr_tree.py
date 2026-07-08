
"""Address hierarchy tree building and enrichment."""
from __future__ import annotations
import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub
from netbox_nsm.analyzers.ip_analyzer.ipa_perf import ipa_lazy_load_enabled
from netbox_nsm.analyzers.ip_analyzer.addr_ip_refs import _FIELD_TYPE_LABELS
from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import (
    IPA_NODE_ROLE_PREFIX,
    IPA_NODE_ROLE_RANGE,
    _ipa_object_node_role_from_cidr_hint,
)


def _addr_tree_node_is_range_container(node):
    """True when the node represents an IP range container."""
    ip_ref = (node or {}).get("ip_ref") or {}
    if ip_ref.get("type") == _FIELD_TYPE_LABELS["range"]:
        return True
    cidr = (node or {}).get("prefix_display_cidr") or _hub._ipa_cidr_from_object_name(
        (node or {}).get("name")
    )
    return bool(cidr) and _ipa_object_node_role_from_cidr_hint(cidr) == IPA_NODE_ROLE_RANGE


def _addr_tree_node_is_prefix_container(node):
    """True when the node represents a prefix/subnet container (not a host /32)."""
    ip_ref = (node or {}).get("ip_ref") or {}
    if ip_ref.get("type") == _FIELD_TYPE_LABELS["prefix"]:
        return True
    cidr = (node or {}).get("prefix_display_cidr") or _hub._ipa_cidr_from_object_name(
        (node or {}).get("name")
    )
    return bool(cidr) and _ipa_object_node_role_from_cidr_hint(cidr) == IPA_NODE_ROLE_PREFIX

def _addr_tree_node_effective_network(node):
    """Network for a tree node, including inferred CIDR from NSM names like ``g-10.0.0.0/8``."""
    net = _addr_tree_node_network(node)
    if net is not None:
        return net
    if node and node.get("kind") in ("group", "leaf"):
        cidr = _hub._ipa_cidr_from_object_name(node.get("name"))
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
    """IP count for aggregate badges from IPAM prefix/range stats only."""
    if not node or node.get("count_duplicate") or node.get("subnet_contained_in"):
        return 0
    if containing_networks is None:
        containing_networks = []

    net = _addr_tree_node_effective_network(node)
    if _addr_tree_network_covered(net, containing_networks):
        return 0

    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _hub._ipam_stats_ip_count(ipam_stats)

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
            _hub._ipam_stats_ip_count(child.get("ipam_stats") or []) for child in children
        )
        if stats_ip_total:
            return stats_ip_total
        inferred = _addr_tree_node_effective_network(node)
        if inferred is not None:
            prefix = _hub._lookup_ipam_prefix_for_cidr(str(inferred))
            if prefix is not None:
                return prefix.get_child_ips().count()
        return int(node.get("leaf_count") or 0)

    ip_ref = node.get("ip_ref") or {}
    return _hub._ip_count_from_ip_ref(ip_ref)


def _addr_tree_node_display_count(node):
    """Display count for badges/footer: NetBox stats when present, else loaded leaves."""
    if not node:
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        return _hub._ipam_stats_total(ipam_stats)
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
    if node.get("count_duplicate") or node.get("subnet_contained_in"):
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        subnet_count = _hub._ipam_stats_subnet_count(ipam_stats)
        if not subnet_count:
            ip_ref = node.get("ip_ref") or {}
            if ip_ref.get("type") == _FIELD_TYPE_LABELS["prefix"]:
                return 1
            if _addr_tree_node_is_prefix_container(node):
                return 1
        return subnet_count
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
        if _addr_tree_node_is_prefix_container(node):
            return 1
        return 0
    if _addr_tree_node_is_prefix_container(node):
        return 1
    return 0


def _addr_tree_node_range_count(node):
    """IP-range count for aggregate badges."""
    if not node:
        return 0
    if node.get("count_duplicate") or node.get("subnet_contained_in"):
        return 0
    ipam_stats = node.get("ipam_stats")
    if ipam_stats:
        range_count = _hub._ipam_stats_range_count(ipam_stats)
        if not range_count:
            ip_ref = node.get("ip_ref") or {}
            if ip_ref.get("type") == _FIELD_TYPE_LABELS["range"]:
                return 1
            if _addr_tree_node_is_range_container(node):
                return 1
        return range_count
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
    candidates = []
    ip_ref_cidr = _hub._addr_node_prefix_cidr(ip_ref=node.get("ip_ref"))
    if ip_ref_cidr:
        candidates.append(ip_ref_cidr)
    display_cidr = node.get("prefix_display_cidr")
    if display_cidr and display_cidr not in candidates:
        candidates.append(display_cidr)
    for cidr in candidates:
        try:
            return ipaddress.ip_network(str(cidr).strip(), strict=False)
        except ValueError:
            continue
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

    ip_ref = _hub._addr_ip_ref(obj)

    if ip_ref is None and _hub._addr_is_group_container(obj):
        if ipa_lazy_load_enabled():
            return {
                "name": str(obj.name),
                "url": obj.get_absolute_url(),
                "kind": "group",
                "ip_ref": None,
                "children": [],
            }
        children = []
        members = _hub._addr_group_members(obj)
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
        ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref) or _hub._ipam_fk_object_for_addr_node(obj)
        ip_ref_dict = _hub._addr_ip_ref_node_dict(ip_ref)
        if ipa_lazy_load_enabled():
            node = {
                "name": str(obj.name),
                "url": obj.get_absolute_url(),
                "kind": "group" if ipam_obj is not None else "leaf",
                "ip_ref": ip_ref_dict,
                "children": [],
            }
            if ipam_obj is not None:
                try:
                    from ipam.models import Prefix as _Prefix

                    if isinstance(ipam_obj, _Prefix):
                        stats = _hub._prefix_ipam_stats(ipam_obj)
                        if stats:
                            _hub._attach_ipam_stats_meta(node, stats)
                except ImportError:
                    pass
            return _hub._attach_addr_node_prefix_display(
                node, obj=obj, ip_ref=ip_ref
            )
        if ipam_obj is not None:
            grouped = None
            prefix_stats = None
            prefix_truncated = None
            child_nodes = []
            try:
                from ipam.models import Prefix as _Prefix

                if isinstance(ipam_obj, _Prefix):
                    grouped, prefix_stats, prefix_truncated = (
                        _hub._collect_ipam_prefix_drilldown(ipam_obj)
                    )
                    child_nodes = [
                        _hub._build_ipam_prefix_layer_node(ipam_obj, visited)
                    ]
                else:
                    from ipam.models import IPRange as _IPRange

                    if isinstance(ipam_obj, _IPRange):
                        child_nodes = [
                            _hub._build_ipam_range_resolve_nodes(ipam_obj, visited)
                        ]
                    else:
                        for child_obj in _hub._collect_ipam_drilldown_children(ipam_obj):
                            child = _build_addr_tree_node(
                                child_obj,
                                _addr_tree_child_visited(visited, child_obj, obj),
                            )
                            if child:
                                child_nodes.append(child)
            except ImportError:
                for child_obj in _hub._collect_ipam_drilldown_children(ipam_obj):
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
                    _hub._attach_ipam_stats_meta(
                        node, prefix_stats, truncated=prefix_truncated
                    )
                return _hub._attach_addr_node_prefix_display(
                    node, obj=obj, ip_ref=ip_ref
                )

        node = {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "leaf",
            "ip_ref": ip_ref_dict,
            "children": [],
        }
        node = _hub._attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)
        return _hub._attach_addr_navigation_refs(node, obj=obj)

    # IPAM prefix — expand contained IPs, ranges, child prefixes, linked addresses
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name == "prefix":
            stats = _hub._prefix_ipam_stats(obj)
            child_nodes = _hub._build_ipam_prefix_resolve_nodes(obj, visited)
            if not child_nodes and not any(
                int((item or {}).get("count") or 0) for item in stats.values()
            ):
                return None
            ip_ref_dict = None
            try:
                from django.contrib.contenttypes.models import ContentType

                ct_id = ContentType.objects.get_for_model(obj).pk
                ip_ref_dict = {
                    "str": str(obj),
                    "url": obj.get_absolute_url(),
                    "type": _FIELD_TYPE_LABELS["prefix"],
                    "ct": str(ct_id),
                    "pk": str(obj.pk),
                }
            except Exception:
                pass
            node = {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "group",
                "ip_ref": ip_ref_dict,
                "children": child_nodes,
            }
            node = _hub._attach_prefix_ipam_meta(node, obj, stats=stats)
            return _hub._attach_addr_node_prefix_display(node, obj=obj)
        if obj._meta.app_label == "ipam" and obj._meta.model_name == "iprange":
            return _hub._build_ipam_range_resolve_nodes(obj, visited)
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
            node = _hub._attach_addr_node_prefix_display(
                node, obj=obj, ip_ref=node["ip_ref"]
            )
            return _hub._attach_addr_navigation_refs(node, ipam_obj=obj)
    except Exception:
        pass
    node = {
        "name": str(getattr(obj, "name", obj)),
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
        "kind": "leaf",
        "ip_ref": None,
        "children": [],
    }
    from netbox_nsm.addresses.address_literal import attach_literal_prefix_display

    return attach_literal_prefix_display(node, obj)


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
        elif kind == "lazy_batch":
            lines.extend(_flatten_addr_tree_paths(node.get("children") or [], path_prefix))
        else:
            lines.append(_addr_path_line(_addr_path_parts_for_leaf(node, path_prefix)))
    return lines


def _enrich_addr_tree_leaf_counts(node):
    """Attach leaf_count: NetBox ipam_stats sum when present, else subtree leaves."""
    kind = node.get("kind")
    if kind in ("group", "category", "lazy_batch"):
        if kind == "group" and node.get("ipam_stats"):
            node["leaf_count"] = _hub._ipam_stats_ip_count(node["ipam_stats"])
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
    elif kind == "lazy_batch":
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


