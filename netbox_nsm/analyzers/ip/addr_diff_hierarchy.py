"""IPAM prefix hierarchy and intersection tree for address diff."""
from __future__ import annotations

import netbox_nsm.analyzers.ip._lazy_api as _hub
from netbox_nsm.analyzers.ip.addr_diff_collect import (
    _addr_tree_node_prefix_compare_key,
    _lookup_ipam_prefix_for_cidr,
)
from netbox_nsm.analyzers.ip.addr_diff_fund import (
    _addr_diff_fund_detail,
    _addr_diff_fund_tooltip,
    _addr_entries_is_diff_fund,
    _addr_entry_is_diff_fund,
    _enrich_diff_cell_pill_fields,
    _enrich_diff_name_pill_fields,
)
from netbox_nsm.analyzers.ip.addr_ip_refs import _FIELD_TYPE_LABELS

def _build_addr_diff_group(
    name, leaves, *, diff_group, diff_present_labels=None, diff_label=None
):
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
    if diff_label:
        group["diff_label"] = str(diff_label)
    if diff_present_labels:
        group["diff_present_labels"] = list(diff_present_labels)
    _hub._enrich_addr_tree_leaf_counts(group)
    _hub._enrich_addr_tree_copy_lines(group)
    return group


def _diff_ipam_prefix_for_intersection_node(node):
    """Return the NetBox Prefix used for IPAM hierarchy nesting."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
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
        _hub._attach_addr_node_prefix_display(node, ip_ref=ip_ref)
    elif node.get("prefix_display_cidr"):
        prefix = _lookup_ipam_prefix_for_cidr(node["prefix_display_cidr"])
        if prefix is not None:
            _hub._enrich_ipa_node_from_resolved_prefix(node, prefix)
    _hub._enrich_addr_tree_leaf_counts(node)
    _enrich_diff_cell_pill_fields(
        node,
        entry={
            "source_objects": (entry_a.get("source_objects") or [])
            + (entry_b.get("source_objects") or []),
        },
    )
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
    _hub._enrich_ipa_node_from_resolved_prefix(node, prefix)
    _hub._enrich_addr_tree_leaf_counts(node)
    return node


def _lookup_containing_prefix_for_intersection_node(node):
    """Most specific NetBox Prefix containing an intersection pair node."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
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
        prefix = _hub._lookup_containing_prefix_for_intersection_node(node)
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
        parent["children"] = sorted(nested_children, key=_hub._ipa_object_tree_sort_key)
        _hub._enrich_addr_tree_leaf_counts(parent)
        prefix_forest_candidates.append(parent)

    if not prefix_forest_candidates:
        return sorted(forest, key=_hub._ipa_object_tree_sort_key)

    prefix_pk_to_node = {}
    node_prefix = {}
    for node in prefix_forest_candidates:
        prefix = _diff_ipam_prefix_for_intersection_node(node)
        if prefix is None:
            continue
        node_prefix[id(node)] = prefix
        prefix_pk_to_node.setdefault(prefix.pk, node)

    nested_prefix_forest = []
    for node in sorted(prefix_forest_candidates, key=_hub._ipa_object_tree_sort_key):
        prefix = node_prefix.get(id(node))
        parent = (
            _hub._ipa_deepest_cell_ancestor_node(prefix, prefix_pk_to_node)
            if prefix is not None
            else None
        )
        if parent is None:
            net = _hub._addr_tree_node_network(node)
            parent = (
                _hub._ipa_find_deepest_containing_node(nested_prefix_forest, net)
                if net
                else None
            )
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["kind"] = "group"
        else:
            nested_prefix_forest.append(node)

    forest.extend(nested_prefix_forest)
    return sorted(forest, key=_hub._ipa_object_tree_sort_key)


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
        _hub._enrich_addr_tree_copy_lines(node)
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
    _enrich_diff_cell_pill_fields(leaf, entry=entry_a)
    if is_fund:
        leaf["diff_fund"] = True
        if fund_detail:
            leaf["fund_detail"] = fund_detail
            leaf["fund_tooltip"] = _addr_diff_fund_tooltip(fund_detail)
    if ip_ref:
        _hub._attach_addr_node_prefix_display(leaf, ip_ref=ip_ref)
    _hub._enrich_addr_tree_copy_lines(leaf)
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
        _hub._enrich_addr_tree_copy_lines(node)
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

