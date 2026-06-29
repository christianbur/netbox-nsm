"""Serialize IP Analyzer payloads to portable YAML for download."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

__all__ = (
    "build_ipa_export_child_objects",
    "build_ipa_export_document",
    "ipa_export_filename",
    "parse_export_context_from_request",
    "serialize_ipa_export_yaml",
)

# v2 splits the document into a primary ``displayed`` block (what the applet
# currently shows for the active tab) and an additional ``ipam_children`` block
# (the full address / IPAM child-object expansion behind lazy tree nodes).
_IPA_EXPORT_VERSION = "2"

# Per-object cap for the additional full-expansion section. Each object drilldown
# is itself bounded (``_IPAM_PREFIX_CHILDREN_MAX`` with lazy placeholders beyond),
# so this only guards against pathological selections with very many objects.
_IPA_EXPORT_MAX_EXPANDED_OBJECTS = 200

# Keys kept on nodes in the additional ``ipam_children`` expansion. Smaller than
# ``_NODE_KEEP_KEYS`` because the expansion only needs identity + structure.
_EXPANSION_KEEP_KEYS = frozenset(
    {
        "name",
        "kind",
        "ip",
        "prefix_display_cidr",
        "prefix_netmask",
        "count",
        "leaf_count",
        "copy_lines",
        "children",
    }
)

_NODE_KEEP_KEYS = frozenset(
    {
        "name",
        "kind",
        "ct",
        "pk",
        "copy_lines",
        "children",
        "ip",
        "prefix_display_cidr",
        "prefix_netmask",
        "leaf_count",
        "count",
        "is_doppelt",
        "is_duplicate",
        "subnet_contained_in",
        "cell_groups",
        "cell_addresses",
        "cell_groups_multi",
        "cell_groups_none",
        "cell_addresses_multi",
        "is_cell_direct",
        "diff_status",
        "diff_side",
        "diff_summary",
        "field_name",
        "field_slug",
        "type_name",
        "types",
        "nodes",
        "all_copy_lines",
        "label",
        "only_a",
        "only_b",
        "both",
    }
)

_CONTEXT_QUERY_MAP = {
    "ctx_rule_index": "rule_index",
    "ctx_rule_name": "rule_name",
    "ctx_col_id": "column_id",
    "ctx_col_position": "column_position",
    "ctx_rules_total": "rules_total",
    "ctx_rules_unfiltered_total": "rules_unfiltered_total",
}


def _simplify_ip_ref(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    text = value.get("str") or value.get("display") or value.get("name")
    return str(text).strip() if text else None


def _simplify_named_refs(items: Any) -> list[dict[str, str]] | None:
    if not isinstance(items, list) or not items:
        return None
    simplified = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("str") or item.get("display")
        if not name:
            continue
        entry = {"name": str(name)}
        simplified.append(entry)
    return simplified or None


def _sanitize_tree_node(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    clean: dict[str, Any] = {}
    for key, value in node.items():
        if key == "children":
            children = [_sanitize_tree_node(child) for child in value or []]
            clean[key] = [child for child in children if child]
            continue
        if key == "nodes":
            nodes = [_sanitize_tree_node(child) for child in value or []]
            clean[key] = [child for child in nodes if child]
            continue
        if key == "types" and isinstance(value, list):
            types = [_sanitize_tree_node(child) for child in value]
            clean[key] = [child for child in types if child]
            continue
        if key not in _NODE_KEEP_KEYS:
            if key == "ip_ref":
                ip_text = _simplify_ip_ref(value)
                if ip_text:
                    clean["ip"] = ip_text
            continue
        if key in ("cell_groups", "cell_addresses"):
            simplified = _simplify_named_refs(value)
            if simplified:
                clean[key] = simplified
            continue
        if key == "copy_lines" and isinstance(value, list):
            clean[key] = [str(line) for line in value if str(line).strip()]
            continue
        if key in ("all_copy_lines",) and isinstance(value, list):
            clean[key] = [str(line) for line in value if str(line).strip()]
            continue
        clean[key] = value
    if not clean:
        return None
    if "ip_ref" in node and "ip" not in clean:
        ip_text = _simplify_ip_ref(node.get("ip_ref"))
        if ip_text:
            clean["ip"] = ip_text
    return clean


def _sanitize_tree(nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(nodes, list):
        return []
    return [item for item in (_sanitize_tree_node(node) for node in nodes) if item]


def _collect_copy_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()

    def _add(raw_lines: Any) -> None:
        for line in raw_lines or []:
            text = str(line).strip()
            if text and text not in seen:
                seen.add(text)
                lines.append(text)

    for section in payload.get("addr_analysis") or []:
        if not isinstance(section, dict):
            continue
        for type_block in section.get("types") or []:
            if not isinstance(type_block, dict):
                continue
            _add(type_block.get("all_copy_lines"))
            for node in type_block.get("nodes") or []:
                if isinstance(node, dict):
                    _add(node.get("copy_lines"))

    for node in payload.get("object_tree") or []:
        if isinstance(node, dict):
            _add(node.get("copy_lines"))

    return lines


def _sanitize_expansion_node(node: Any) -> dict[str, Any] | None:
    """Trim a resolved drilldown node to portable identity + structure keys."""
    if not isinstance(node, dict):
        return None
    clean: dict[str, Any] = {}
    for key, value in node.items():
        if key == "children":
            children = _sanitize_expansion_nodes(value)
            if children:
                clean["children"] = children
            continue
        if key == "ip_ref":
            ip_text = _simplify_ip_ref(value)
            if ip_text:
                clean["ip"] = ip_text
            continue
        if key == "copy_lines" and isinstance(value, list):
            lines = [str(line) for line in value if str(line).strip()]
            if lines:
                clean["copy_lines"] = lines
            continue
        if key in _EXPANSION_KEEP_KEYS:
            clean[key] = value
    if node.get("lazy_load"):
        # Mirror the applet: the slice beyond the page cap stays collapsed.
        clean["truncated"] = True
    return clean or None


def _sanitize_expansion_nodes(nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(nodes, list):
        return []
    return [
        item for item in (_sanitize_expansion_node(node) for node in nodes) if item
    ]


def _collect_object_tree_refs(
    nodes: Any, refs: list[dict[str, Any]], seen: set[tuple[int, int]]
) -> None:
    """Collect ``(ct, pk)`` object references from the visible cell object tree."""
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        ct_raw = node.get("ct")
        pk_raw = node.get("pk")
        if str(ct_raw or "").isdigit() and str(pk_raw or "").isdigit():
            key = (int(ct_raw), int(pk_raw))
            if key not in seen:
                seen.add(key)
                refs.append(
                    {"ct": key[0], "pk": key[1], "name": node.get("name")}
                )
        _collect_object_tree_refs(node.get("children"), refs, seen)


def build_ipa_export_child_objects(
    payload: dict[str, Any],
    *,
    max_objects: int = _IPA_EXPORT_MAX_EXPANDED_OBJECTS,
) -> list[dict[str, Any]]:
    """Resolve the full address / IPAM child expansion for the visible objects.

    Walks the visible ``object_tree`` and, for every referenced object, reuses
    the same lazy drilldown the applet performs on expand
    (``_build_ipa_object_drilldown_nodes``). Requires ORM access, so it is kept
    separate from the pure :func:`build_ipa_export_document`.
    """
    object_tree = payload.get("object_tree") or []
    if not object_tree:
        return []

    refs: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    _collect_object_tree_refs(object_tree, refs, seen)
    if not refs:
        return []

    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.analyzers.ip.ipa_ipam_tree import _build_ipa_object_drilldown_nodes

    entries: list[dict[str, Any]] = []
    for ref in refs[: max(int(max_objects), 0)]:
        try:
            ct = ContentType.objects.get(pk=ref["ct"])
            model_cls = ct.model_class()
            if model_cls is None:
                continue
            obj = model_cls.objects.filter(pk=ref["pk"]).first()
            if obj is None:
                continue
            nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)
        except Exception:
            continue
        if not nodes:
            continue
        entries.append(
            {
                "content_type": ref["ct"],
                "id": ref["pk"],
                "name": ref.get("name") or str(getattr(obj, "name", "") or obj),
                "children": nodes,
                "copy_lines": copy_lines,
            }
        )
    return entries


def parse_export_context_from_request(request) -> dict[str, str]:
    """Optional rulebook/rule context passed from the applet toolbar."""
    context: dict[str, str] = {}
    for query_key, field_name in _CONTEXT_QUERY_MAP.items():
        value = (request.GET.get(query_key) or "").strip()
        if value:
            context[field_name] = value
    title = (request.GET.get("export_title") or "").strip()
    if title:
        context["title"] = title
    return context


def _build_ipam_children_section(
    child_objects: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """Sanitize the resolved child expansion into the additional document block."""
    if not child_objects:
        return None
    objects: list[dict[str, Any]] = []
    for entry in child_objects:
        if not isinstance(entry, dict):
            continue
        children = _sanitize_expansion_nodes(entry.get("children"))
        if not children:
            continue
        item: dict[str, Any] = {}
        for key in ("content_type", "id", "name"):
            value = entry.get(key)
            if value:
                item[key] = value
        item["children"] = children
        copy_lines = [
            str(line)
            for line in entry.get("copy_lines") or []
            if str(line).strip()
        ]
        if copy_lines:
            item["copy_lines"] = copy_lines
        objects.append(item)
    if not objects:
        return None
    return {
        "description": (
            "Full address / IPAM child-object expansion behind the displayed "
            "objects (child prefixes, IP addresses, ranges, and group members). "
            "Large branches are bounded; truncated nodes are flagged."
        ),
        "objects": objects,
    }


def build_ipa_export_document(
    payload: dict[str, Any],
    *,
    export_context: dict[str, str] | None = None,
    child_objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a YAML-friendly document from an IP analysis payload.

    The document has two clearly separated parts:

    * ``displayed`` — the primary section, mirroring exactly what the applet
      shows for the active tab (visible tree rows + summary counts).
    * ``ipam_children`` — the additional/optional section with the full child
      expansion (only present when ``child_objects`` resolves any children).
    """
    export_context = dict(export_context or {})
    title = (export_context.pop("title", None) or "").strip()

    document: dict[str, Any] = {
        "ipa_export_version": _IPA_EXPORT_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "mode": payload.get("mode") or "merge",
    }
    if title:
        document["title"] = title
    if export_context:
        document["context"] = export_context

    displayed: dict[str, Any] = {
        "counts": {
            "leaf_count": payload.get("leaf_count") or 0,
            "subnets": payload.get("count_subnets") or 0,
            "ranges": payload.get("count_ranges") or 0,
            "ips": payload.get("count_ips") or 0,
            "duplicates": payload.get("count_duplicates") or 0,
            "group_duplicates": payload.get("count_group_duplicates") or 0,
        }
    }

    objects = []
    for obj in payload.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        entry = {
            "content_type": obj.get("ct"),
            "id": obj.get("pk"),
            "name": obj.get("name"),
        }
        objects.append({key: value for key, value in entry.items() if value})
    if objects:
        displayed["objects"] = objects

    unsupported = payload.get("unsupported") or []
    if unsupported:
        displayed["unsupported"] = unsupported

    copy_lines = _collect_copy_lines(payload)
    if copy_lines:
        displayed["copy_lines"] = copy_lines

    addr_analysis = _sanitize_tree(payload.get("addr_analysis") or [])
    if addr_analysis:
        displayed["addr_analysis"] = addr_analysis

    object_tree = _sanitize_tree(payload.get("object_tree") or [])
    if object_tree:
        displayed["object_tree"] = object_tree

    if payload.get("diff_summary") is not None:
        displayed["diff_summary"] = payload.get("diff_summary")

    message = (payload.get("message") or "").strip()
    if message:
        displayed["message"] = message

    document["displayed"] = displayed

    ipam_children = _build_ipam_children_section(child_objects)
    if ipam_children:
        document["ipam_children"] = ipam_children

    return document


def serialize_ipa_export_yaml(document: dict[str, Any]) -> str:
    import yaml

    return yaml.dump(
        document,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )


def ipa_export_filename(
    payload: dict[str, Any],
    *,
    export_context: dict[str, str] | None = None,
) -> str:
    export_context = export_context or {}
    title = (export_context.get("title") or "").strip()
    if not title:
        objects = payload.get("objects") or []
        if objects and isinstance(objects[0], dict):
            title = str(objects[0].get("name") or "").strip()
    if not title:
        title = "ipa-export"
    slug = re.sub(r"[^\w.-]+", "-", title.lower()).strip("-._")
    if not slug:
        slug = "ipa-export"
    mode = (payload.get("mode") or "merge").strip().lower()
    return f"{slug}-{mode}.yaml"
