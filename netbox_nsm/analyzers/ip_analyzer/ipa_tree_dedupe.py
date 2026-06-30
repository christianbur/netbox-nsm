"""Generic tree-node deduplication primitives for IPA address trees."""
from __future__ import annotations

import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub


def _default_object_key(node):
    try:
        ct = int(node.get("ct") or 0)
        pk = int(node.get("pk") or 0)
    except (TypeError, ValueError):
        return None
    if ct and pk:
        return (ct, pk)
    return None


def _default_network_key(node):
    return _hub._addr_tree_node_network(node)


def dedupe_by_object_key(nodes, *, key_fn=None, seen_keys=None):
    """Drop nodes whose object identity was already seen in this traversal."""
    if key_fn is None:
        key_fn = _default_object_key
    if seen_keys is None:
        seen_keys = set()
    deduped = []
    for node in nodes or []:
        obj_key = key_fn(node)
        if obj_key is not None:
            if obj_key in seen_keys:
                continue
            seen_keys.add(obj_key)
        deduped.append(node)
    return deduped


def dedupe_by_network(
    nodes,
    *,
    exclude_network=None,
    hoist_children=False,
    network_key_fn=None,
    key_fn=None,
    seen_keys=None,
    seen_networks=None,
    filter_parent_network=False,
):
    """
    Drop repeated networks from a node list.

    When duplicate or excluded nodes have children, those children are hoisted
    into the result (same semantics as the legacy IPAM drilldown deduper).
    """
    if network_key_fn is None:
        network_key_fn = _default_network_key
    if key_fn is None:
        key_fn = _default_object_key
    if seen_keys is None:
        seen_keys = set()
    if seen_networks is None:
        seen_networks = set()

    deduped = []
    for node in nodes or []:
        obj_key = key_fn(node)
        if obj_key is not None:
            if obj_key in seen_keys:
                continue
            seen_keys.add(obj_key)

        children = node.get("children")
        net = network_key_fn(node)

        if (
            filter_parent_network
            and exclude_network is not None
            and net is not None
            and net == exclude_network
        ):
            if children and hoist_children:
                deduped.extend(
                    dedupe_by_network(
                        children,
                        exclude_network=exclude_network,
                        hoist_children=hoist_children,
                        network_key_fn=network_key_fn,
                        key_fn=key_fn,
                        seen_keys=seen_keys,
                        seen_networks=seen_networks,
                        filter_parent_network=True,
                    )
                )
            continue

        if net is not None and net in seen_networks:
            if children and hoist_children:
                deduped.extend(
                    dedupe_by_network(
                        children,
                        exclude_network=exclude_network,
                        hoist_children=hoist_children,
                        network_key_fn=network_key_fn,
                        key_fn=key_fn,
                        seen_keys=seen_keys,
                        seen_networks=seen_networks,
                        filter_parent_network=filter_parent_network,
                    )
                )
            continue
        if net is not None:
            seen_networks.add(net)

        if children:
            node["children"] = dedupe_by_network(
                children,
                exclude_network=exclude_network,
                hoist_children=hoist_children,
                network_key_fn=network_key_fn,
                key_fn=key_fn,
                seen_keys=seen_keys,
                seen_networks=seen_networks,
                filter_parent_network=True,
            )
        deduped.append(node)
    return deduped


def collapse_sibling_networks(nodes, *, network_key_fn=None):
    """Keep one drilldown row per network at each sibling level."""
    if network_key_fn is None:
        network_key_fn = _default_network_key

    by_net = {}
    order = []
    passthrough = []
    for node in nodes or []:
        net = network_key_fn(node)
        if net is None:
            passthrough.append(node)
            continue
        if net not in by_net:
            by_net[net] = node
            order.append(net)
            continue
        kept = by_net[net]
        kept_children = kept.get("children") or []
        new_children = node.get("children") or []
        if len(new_children) > len(kept_children):
            by_net[net] = node
        elif new_children and not kept_children:
            kept["children"] = new_children
    collapsed = passthrough + [by_net[net] for net in order]
    for node in collapsed:
        children = node.get("children")
        if children:
            node["children"] = collapse_sibling_networks(
                children, network_key_fn=network_key_fn
            )
    return collapsed


def _node_renders_self_reference(node):
    """True when drilldown UI would show the same network on both sides (A → A)."""
    ip_ref = node.get("ip_ref") or {}
    target = str(node.get("prefix_display_cidr") or ip_ref.get("str") or "").strip()
    if not target or "/" not in target:
        return False
    name = str(node.get("name") or "").strip()
    if name == target:
        return True
    name_net = _default_network_key({"prefix_display_cidr": name})
    target_net = _default_network_key(node)
    return (
        name_net is not None
        and target_net is not None
        and name_net == target_net
    )


def strip_self_referential_redundant_networks(
    nodes, *, redundant_networks, recursive=True
):
    """
    Drop drilldown rows that repeat a redundant network as ``net → net``.

    Complements :func:`strip_redundant_parent_network` for prefix rows that
    survive stripping as non-``ipam_prefix`` groups (lazy drilldown uses
    ``ipa_cell_pill=False``, which renders the arrow for those nodes).
    """
    if not redundant_networks:
        return nodes
    redundant = frozenset(redundant_networks)
    stripped = []
    for node in nodes or []:
        children = node.get("children") or []
        net = _default_network_key(node)
        if (
            net is not None
            and net in redundant
            and _node_renders_self_reference(node)
        ):
            if recursive:
                stripped.extend(
                    strip_self_referential_redundant_networks(
                        children,
                        redundant_networks=redundant_networks,
                        recursive=True,
                    )
                )
            else:
                stripped.extend(children)
            continue
        if recursive and children:
            node = dict(node)
            node["children"] = strip_self_referential_redundant_networks(
                children,
                redundant_networks=redundant_networks,
                recursive=True,
            )
        stripped.append(node)
    return stripped


def strip_redundant_parent_network(nodes, *, parent_network, recursive=True):
    """Drop nodes that repeat ``parent_network`` (any layer)."""
    if parent_network is None:
        return nodes
    stripped = []
    for node in nodes or []:
        net = _hub._addr_tree_node_network(node)
        if net is not None and net == parent_network:
            child_nodes = node.get("children") or []
            if recursive:
                stripped.extend(
                    strip_redundant_parent_network(
                        child_nodes, parent_network=parent_network, recursive=True
                    )
                )
            else:
                stripped.extend(child_nodes)
            continue
        children = node.get("children")
        if recursive and children:
            node["children"] = strip_redundant_parent_network(
                children, parent_network=parent_network, recursive=True
            )
        stripped.append(node)
    return stripped


__all__ = (
    "collapse_sibling_networks",
    "dedupe_by_network",
    "dedupe_by_object_key",
    "strip_redundant_parent_network",
    "strip_self_referential_redundant_networks",
)
