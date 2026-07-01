
"""Merged address analysis and summary type counts."""
from __future__ import annotations
import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub

def _build_multi_object_addr_analyzer(objs):
    """IP Analyzer: merged tree for one or more selected objects."""
    supported = [o for o in objs if o and _hub._object_supports_addr_analyzer(o)]
    if not supported:
        return []
    nodes, all_copy_lines = _hub._build_addr_tree_nodes(supported)
    if not nodes:
        return []
    type_counts = _hub._type_counts_for_addr_nodes(nodes)
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
                    "leaf_count": (
                        type_counts["count_subnets"]
                        + type_counts["count_ranges"]
                        + type_counts["count_ips"]
                    ),
                    "count_subnets": type_counts["count_subnets"],
                    "count_ranges": type_counts["count_ranges"],
                    "count_ips": type_counts["count_ips"],
                    "count_duplicates": _count_addr_tree_duplicates(nodes),
                    "has_objects": True,
                }
            ],
        }
    ]


def _leaf_count_for_addr_analyzer(sections) -> int:
    total = 0
    for section in sections or []:
        for type_block in section.get("types") or []:
            typed = (
                int(type_block.get("count_subnets") or 0)
                + int(type_block.get("count_ranges") or 0)
                + int(type_block.get("count_ips") or 0)
            )
            total += typed or int(type_block.get("leaf_count") or 0)
    return total


def _type_counts_for_addr_analyzer(sections) -> dict:
    """Aggregate subnet/range/IP counts from addr_analyzer sections."""
    totals = {"count_subnets": 0, "count_ranges": 0, "count_ips": 0}
    for section in sections or []:
        for type_block in section.get("types") or []:
            if type_block.get("count_ips") is not None:
                totals["count_subnets"] += int(type_block.get("count_subnets") or 0)
                totals["count_ranges"] += int(type_block.get("count_ranges") or 0)
                totals["count_ips"] += int(type_block.get("count_ips") or 0)
            elif type_block.get("nodes"):
                node_counts = _hub._type_counts_for_addr_nodes(type_block["nodes"])
                for key in totals:
                    totals[key] += node_counts[key]
    return totals


def _ipa_object_tree_type_counts(nodes):
    """Summary counts for the IPA cell object tree (visible rows, not IPAM inventory)."""
    from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _ipa_cell_object_tree_type_counts

    return _ipa_cell_object_tree_type_counts(nodes)


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
    - ``cell_addresses_multi``: several NSM address names share the same network
    - ``is_doppelt``: same object listed twice in the rule cell
    - ``object_duplicate``: same object identity appears again elsewhere in the tree
    - ``count_duplicate``: excluded from addr-tree IP totals (legacy addr tree)
    """
    count = 0

    def _walk(node):
        nonlocal count
        if (
            node.get("subnet_contained_in")
            or node.get("cell_addresses_multi")
            or node.get("is_doppelt")
            or node.get("object_duplicate")
            or node.get("count_duplicate")
        ):
            count += 1
        for child in node.get("children") or []:
            _walk(child)

    for node in nodes or []:
        _walk(node)
    return count


def _count_ipa_object_tree_group_duplicates(nodes):
    """Count addresses that belong to more than one cell group."""
    count = 0

    def _walk(node):
        nonlocal count
        if node.get("cell_groups_multi"):
            count += 1
        for child in node.get("children") or []:
            _walk(child)

    for node in nodes or []:
        _walk(node)
    return count


def _resolve_summary_type_counts(addr_analyzer, object_tree=None) -> dict:
    """Summary counts for the All row; prefer object-tree IPAM stats when present."""
    if object_tree:
        counts = _ipa_object_tree_type_counts(object_tree)
        counts["count_duplicates"] = _count_ipa_object_tree_duplicates(object_tree)
        counts["count_group_duplicates"] = _count_ipa_object_tree_group_duplicates(
            object_tree
        )
        if not any(
            counts.get(key) for key in ("count_subnets", "count_ranges", "count_ips")
        ):
            fallback = _type_counts_for_addr_analyzer(addr_analyzer)
            for key in ("count_subnets", "count_ranges", "count_ips"):
                counts[key] = fallback.get(key) or 0
        return counts
    counts = _type_counts_for_addr_analyzer(addr_analyzer)
    dup_total = 0
    for section in addr_analyzer or []:
        for type_block in section.get("types") or []:
            dup_total += _count_addr_tree_duplicates(type_block.get("nodes") or [])
    counts["count_duplicates"] = dup_total
    counts["count_group_duplicates"] = 0
    return counts


def _apply_summary_type_counts_to_addr_analyzer(addr_analyzer, type_counts):
    """Mirror resolved All-row counts onto addr_analyzer type blocks for templates/API."""
    if not addr_analyzer or not type_counts:
        return
    for section in addr_analyzer:
        for type_block in section.get("types") or []:
            type_block["count_subnets"] = type_counts.get("count_subnets") or 0
            type_block["count_ranges"] = type_counts.get("count_ranges") or 0
            type_block["count_ips"] = type_counts.get("count_ips") or 0
            type_block["leaf_count"] = type_counts.get("count_ips") or 0
            type_block["count_duplicates"] = type_counts.get("count_duplicates") or 0
            type_block["count_group_duplicates"] = (
                type_counts.get("count_group_duplicates") or 0
            )


