"""Batched link-tree builder for the Object Analyzer "+" link picker.

The link picker needs two levels of relations for a node:

* **L1** — the direct links of the clicked node.
* **L2** — for every L1 child, its own direct links (used for the secondary
  link count badge and for cloud/child expansion when an L1 row is selected).

Previously the frontend fetched this with ``1 + N`` separate HTTP requests
(one for L1, then one per L1 child for its L2). Each request re-resolved the
object and ran the full :func:`registry.get_edges` resolver
(``reverse_fk_edges`` scans every installed model), so a node with many links
produced a request storm and a long picker-open delay.

``build_picker_tree`` computes the whole tree in a single pass:

* child objects are hydrated in bulk (one ``in_bulk`` query per content type
  instead of one ``get`` per child),
* ``get_edges`` is run at most once per object,
* the result is returned in one JSON payload.

Logic lives here (Python); the JS only renders/interacts with the payload.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Any

__all__ = (
    "build_picker_tree",
    "filter_already_linked_picker_edges",
    "filter_picker_children_for_canvas",
    "filter_picker_edges_by_target_ids",
    "filter_picker_tree_for_canvas",
    "group_picker_children",
    "parent_neighbor_ids",
    "picker_edge_exists_on_canvas",
    "picker_edge_key",
    "picker_group_check_state",
    "picker_l1_keys_for_group",
    "picker_l1_row_key",
    "picker_sync_all_checkbox",
    "picker_toggle_group",
)


def _dedupe_edges(edges: list) -> list:
    """Drop duplicate edges that point at the same target node id."""
    seen: set[str] = set()
    out = []
    for edge in edges:
        nid = edge.node.id
        if nid in seen:
            continue
        seen.add(nid)
        out.append(edge)
    return out


def _serialize_edge(edge) -> dict:
    return {
        "edge_label": edge.edge_label,
        "edge_type": edge.edge_type,
        "node": dataclasses.asdict(edge.node),
    }


def _bulk_resolve(refs: list[tuple[int, int]]) -> dict[tuple[int, int], Any]:
    """Resolve ``(ct_id, object_id)`` refs to model instances in bulk.

    Groups by content type and issues one ``in_bulk`` query per type instead of
    one query per object.
    """
    from django.contrib.contenttypes.models import ContentType

    by_ct: dict[int, list[int]] = defaultdict(list)
    for ct_id, object_id in refs:
        by_ct[ct_id].append(object_id)

    resolved: dict[tuple[int, int], Any] = {}
    for ct_id, object_ids in by_ct.items():
        try:
            ct = ContentType.objects.get_for_id(ct_id)
            model_class = ct.model_class()
        except Exception:
            model_class = None
        if model_class is None:
            continue
        try:
            objects = model_class.objects.in_bulk(object_ids)
        except Exception:
            objects = {}
        for object_id in object_ids:
            obj = objects.get(object_id)
            if obj is not None:
                resolved[(ct_id, object_id)] = obj
    return resolved


def _group_key(edge_label: str) -> str:
    """Stable slug for grouping picker rows by relation category."""
    return edge_label.lower().replace("-", "_").replace(" ", "_")


def picker_edge_key(source: str, target: str) -> str:
    """Stable edge id for canvas dedupe (mirrors frontend ``source|target``)."""
    return f"{source}|{target}"


def picker_edge_exists_on_canvas(
    parent_id: str,
    target_id: str,
    existing_edges: set[str],
) -> bool:
    """True when *parent*→*target* or the reverse is already on the canvas."""
    parent = str(parent_id)
    target = str(target_id)
    return (
        picker_edge_key(parent, target) in existing_edges
        or picker_edge_key(target, parent) in existing_edges
    )


def _already_linked_target_ids(obj) -> frozenset[str]:
    """Node ids structurally linked to *obj* in NetBox (not addable in picker)."""
    from netbox_nsm.analysis.analyzer import node_from_object
    from netbox_nsm.core.interface_parent import get_interface_parent_host

    ids: set[str] = set()
    parent_host = get_interface_parent_host(obj)
    if parent_host is not None:
        ids.add(node_from_object(parent_host).id)

    assigned = getattr(obj, "assigned_object", None)
    if assigned is not None:
        ids.add(node_from_object(assigned).id)

    return frozenset(ids)


def filter_already_linked_picker_edges(obj, edges: list) -> list:
    """Drop edges whose target is already linked to *obj* in NetBox."""
    if obj is None or not edges:
        return edges
    skip = _already_linked_target_ids(obj)
    if not skip:
        return edges
    return [edge for edge in edges if edge.node.id not in skip]


def parent_neighbor_ids(obj, mode=None) -> frozenset[str]:
    """Node ids of every direct link of *obj* from the edge resolver."""
    from netbox_nsm.analysis.analyzer.modes import get_filtered_edges, parse_analyzer_mode

    analyzer_mode = parse_analyzer_mode(mode)
    edges = _dedupe_edges(get_filtered_edges(obj, analyzer_mode))
    return frozenset(edge.node.id for edge in edges)


def filter_picker_edges_by_target_ids(edges: list, skip_ids: frozenset[str]) -> list:
    """Drop edges whose target node id is in *skip_ids*."""
    if not edges or not skip_ids:
        return edges
    return [edge for edge in edges if edge.node.id not in skip_ids]


def picker_l1_row_key(node_id: str | int) -> str:
    """Stable row key for an L1 picker item (mirrors frontend ``l1:{id}``)."""
    return f"l1:{node_id}"


def filter_picker_children_for_canvas(
    children: list[dict],
    parent_id: str,
    existing_edges: set[str],
    linked_neighbor_ids: frozenset[str] | set[str] | None = None,
) -> list[dict]:
    """Drop picker rows already on canvas or already linked to the parent object."""
    linked = frozenset(linked_neighbor_ids or ())
    out = []
    for child in children:
        node = child.get("node") or {}
        target_id = node.get("id")
        if target_id is None:
            out.append(child)
            continue
        if picker_edge_exists_on_canvas(parent_id, target_id, existing_edges):
            continue
        if "l2" in child and isinstance(child["l2"], list):
            l1_id = str(target_id)
            l2 = []
            for l2c in child["l2"]:
                tid = (l2c.get("node") or {}).get("id")
                if tid is None:
                    l2.append(l2c)
                    continue
                if picker_edge_exists_on_canvas(l1_id, tid, existing_edges):
                    continue
                if tid in linked:
                    continue
                l2.append(l2c)
            child = {**child, "l2": l2, "l2_count": len(l2)}
        out.append(child)
    return out


def filter_picker_tree_for_canvas(
    tree: dict,
    parent_id: str,
    existing_edges: set[str],
    linked_neighbor_ids: frozenset[str] | set[str] | None = None,
) -> dict:
    """Filter L1 (+ embedded L2) picker payload for canvas + parent links."""
    neighbors = linked_neighbor_ids
    if neighbors is None:
        neighbors = tree.get("linked_neighbor_ids")
    children = filter_picker_children_for_canvas(
        tree.get("children") or [],
        parent_id,
        existing_edges,
        neighbors,
    )
    return {
        **tree,
        "children": children,
        "groups": group_picker_children(children),
    }


def picker_l1_keys_for_group(group: dict) -> list[str]:
    """Row keys for every L1 item inside a serialized picker group."""
    return [
        picker_l1_row_key((child.get("node") or {}).get("id"))
        for child in group.get("items", [])
        if (child.get("node") or {}).get("id") is not None
    ]


def picker_group_check_state(checked: set[str], l1_keys: list[str]) -> str:
    """Tri-state group checkbox: ``all``, ``partial``, or ``none``."""
    if not l1_keys:
        return "none"
    selected = sum(1 for key in l1_keys if key in checked)
    if selected == 0:
        return "none"
    if selected == len(l1_keys):
        return "all"
    return "partial"


def picker_toggle_group(checked: set[str], l1_keys: list[str], on: bool) -> set[str]:
    """Select or deselect every L1 row in a group."""
    out = set(checked)
    for key in l1_keys:
        if on:
            out.add(key)
        else:
            out.discard(key)
    return out


def picker_sync_all_checkbox(
    checked: set[str],
    all_l1_keys: list[str],
    *,
    all_key: str = "__all__",
) -> set[str]:
    """Keep the ``-- all --`` row in sync with every visible L1 key."""
    out = set(checked)
    if all_l1_keys and all(key in out for key in all_l1_keys):
        out.add(all_key)
    else:
        out.discard(all_key)
    return out


def group_picker_children(children: list[dict]) -> list[dict]:
    """Group serialized L1 children by ``edge_label`` (relation category).

    Each group becomes ``{"key", "label", "items"}`` where *label* is the
    human-readable category (e.g. "Cable Termination", "Interface") and *items*
    retain the full child payload (including optional ``l2`` / ``l2_count``).
    """
    buckets: dict[str, dict] = {}
    for child in children:
        label = child.get("edge_label") or "Other"
        key = _group_key(label)
        if key not in buckets:
            buckets[key] = {"key": key, "label": label, "items": []}
        buckets[key]["items"].append(child)

    groups = list(buckets.values())
    for group in groups:
        group["items"].sort(
            key=lambda c: str(
                (c.get("node") or {}).get("label") or "",
            ).lower(),
        )
    groups.sort(key=lambda g: g["label"].lower())
    return groups


def build_picker_tree(
    obj: Any,
    *,
    depth: int = 2,
    mode=None,
    exclude_targets: frozenset[str] | set[str] | None = None,
) -> dict:
    """Build the root node + L1 (+ optional L2) link tree for *obj*.

    ``depth=1`` returns only the direct links (fast — one ``get_edges`` call).
    ``depth=2`` also embeds each L1 child's links so the picker can show the
    secondary-link count and expand without further round-trips.

    ``mode`` (``all`` / ``security``) filters edges server-side; defaults to
    ``all``.

    ``exclude_targets`` — optional extra node ids to omit from L1/L2 (e.g.
    canvas-only targets passed by the client). Parent direct neighbors are
    always excluded from embedded L2 rows via ``linked_neighbor_ids``.
    """
    from netbox_nsm.analysis.analyzer import node_from_object
    from netbox_nsm.analysis.analyzer.modes import get_filtered_edges, parse_analyzer_mode

    analyzer_mode = parse_analyzer_mode(mode)
    root_node = node_from_object(obj)
    root_l1_raw = _dedupe_edges(get_filtered_edges(obj, analyzer_mode))
    root_neighbor_ids = frozenset(edge.node.id for edge in root_l1_raw)
    extra_exclude = frozenset(exclude_targets or ())
    l1_edges = filter_picker_edges_by_target_ids(
        filter_already_linked_picker_edges(obj, root_l1_raw),
        extra_exclude,
    )

    children = [_serialize_edge(edge) for edge in l1_edges]

    if depth >= 2 and l1_edges:
        refs = [(edge.node.ct_id, edge.node.object_id) for edge in l1_edges]
        resolved = _bulk_resolve(refs)
        for serialized, edge in zip(children, l1_edges):
            child_obj = resolved.get((edge.node.ct_id, edge.node.object_id))
            if child_obj is None:
                serialized["l2"] = []
                serialized["l2_count"] = 0
                continue
            l2_edges = filter_picker_edges_by_target_ids(
                filter_already_linked_picker_edges(
                    child_obj,
                    _dedupe_edges(get_filtered_edges(child_obj, analyzer_mode)),
                ),
                root_neighbor_ids | extra_exclude,
            )
            serialized["l2"] = [_serialize_edge(e) for e in l2_edges]
            serialized["l2_count"] = len(l2_edges)

    return {
        "node": dataclasses.asdict(root_node),
        "children": children,
        "groups": group_picker_children(children),
        "linked_neighbor_ids": sorted(root_neighbor_ids),
    }
