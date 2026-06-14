"""Collect address-tree leaves and prefix groups for diff analysis."""
from __future__ import annotations

import netbox_nsm.analysis._lazy_api as _hub
from netbox_nsm.analysis.addr_ip_refs import _FIELD_TYPE_LABELS

def _addr_leaf_compare_key(node, path_prefix=None):
    """Stable key for address diff set comparison."""
    if path_prefix is None:
        path_prefix = []
    ip_ref = node.get("ip_ref")
    if ip_ref and ip_ref.get("str"):
        return str(ip_ref["str"]).strip().lower()
    return _hub._addr_path_line(_hub._addr_path_parts_for_leaf(node, path_prefix)).strip().lower()


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
                entry["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
                _hub._attach_addr_node_prefix_display(entry, ip_ref=ip_ref)
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
