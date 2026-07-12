"""Generic merge/collapse orchestration for IPA cell-tree sibling nodes."""

from __future__ import annotations


def merge_nodes_by_network(
    nodes,
    *,
    network_key_fn,
    sort_fn,
    merge_metadata_fn,
    sync_addresses_fn,
):
    """Merge same-network siblings while preserving stable sort and metadata."""
    merged = {}
    unkeyed = []
    for node in nodes or []:
        net_key = network_key_fn(node)
        if net_key is None:
            unkeyed.append(node)
            continue
        keeper = merged.get(net_key)
        if keeper is None:
            merged[net_key] = node
            continue
        if node.get("is_cell_direct") and not keeper.get("is_cell_direct"):
            merge_metadata_fn(node, keeper)
            merged[net_key] = node
        else:
            merge_metadata_fn(keeper, node)
    result = sort_fn(list(merged.values()) + unkeyed)
    for node in result:
        sync_addresses_fn(node)
    return result


def collapse_siblings_by_network(nodes, *, merge_nodes_fn):
    """Recursively merge same-network siblings at each tree level."""
    collapsed = merge_nodes_fn(nodes)
    for node in collapsed:
        children = node.get("children")
        if children:
            node["children"] = collapse_siblings_by_network(
                children,
                merge_nodes_fn=merge_nodes_fn,
            )
    return collapsed
