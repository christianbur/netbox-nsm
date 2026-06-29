"""Top-level address diff analysis builders (N-side comparison)."""
from __future__ import annotations

import netbox_nsm.analyzers.ip._lazy_api as _hub
from netbox_nsm.analyzers.ip.addr_diff_collect import (
    _collect_addr_tree_leaf_map,
    _collect_addr_tree_prefix_groups,
    _compute_diff_prefix_hierarchy_multi,
)
from netbox_nsm.analyzers.ip.addr_diff_fund import (
    _addr_diff_fund_detail,
    _addr_diff_fund_detail_multi,
    _addr_entries_is_diff_fund,
    _addr_entry_is_diff_fund,
    _addr_side_has_name_conflict,
    _shallow_addr_leaf_for_diff,
)
from netbox_nsm.analyzers.ip.addr_diff_hierarchy import (
    _build_addr_diff_group,
    _build_diff_ipam_intersection_tree_multi,
    _reorganize_diff_leaves_under_prefix_hierarchy,
    _reorganize_diff_both_group_leaves,
    _type_counts_for_multi_diff,
)

def _diff_status_for_exclusive_side(side_index, side_count):
    """Map an exclusive side index to legacy diff_status / diff_group slugs."""
    if side_count == 2:
        return ("only_a", "only-a") if side_index == 0 else ("only_b", "only-b")
    return (f"only_side_{side_index}", f"only-side-{side_index}")


def _rollup_diff_leaves_by_ipam_prefix(leaves, prefix_hierarchy=None):
    """Nest diff rows under IPAM prefixes while preserving individual IP rows."""
    return _reorganize_diff_leaves_under_prefix_hierarchy(
        leaves,
        prefix_hierarchy=prefix_hierarchy,
        assignable_child=lambda child: bool(child.get("diff_status")),
    )


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
            obj for obj in spec.get("objs") or [] if obj and _hub._object_supports_addr_analysis(obj)
        ]
        if supported:
            has_supported = True
        nodes, _lines = _hub._build_addr_tree_nodes(supported, all_copy_prefix="")
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
                    diff_label=label,
                )
            )
        side_prefix_hierarchy = _compute_diff_prefix_hierarchy_multi(
            [prefix_groups_list[side_index]], keys
        )
        leaves = _rollup_diff_leaves_by_ipam_prefix(
            leaves, prefix_hierarchy=side_prefix_hierarchy
        )
        group = _build_addr_diff_group(
            f"Only in {label}", leaves, diff_group=slug, diff_label=label
        )
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
                        diff_label=", ".join(present_labels),
                    )
                )
            present_prefix_hierarchy = _compute_diff_prefix_hierarchy_multi(
                [prefix_groups_list[index] for index in present_indices],
                in_some_by_presence[present_indices],
            )
            leaves = _rollup_diff_leaves_by_ipam_prefix(
                leaves, prefix_hierarchy=present_prefix_hierarchy
            )
            group = _build_addr_diff_group(
                "In some",
                leaves,
                diff_group="in-some",
                diff_present_labels=present_labels,
                diff_label=", ".join(present_labels),
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


