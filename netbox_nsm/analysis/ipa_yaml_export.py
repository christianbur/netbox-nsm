"""Serialize IP Analyzer payloads to portable YAML for download."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

__all__ = (
    "build_ipa_export_document",
    "ipa_export_filename",
    "parse_export_context_from_request",
    "serialize_ipa_export_yaml",
)

_IPA_EXPORT_VERSION = "1"

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


def build_ipa_export_document(
    payload: dict[str, Any],
    *,
    export_context: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build a YAML-friendly document from an IP analysis payload."""
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

    document["counts"] = {
        "leaf_count": payload.get("leaf_count") or 0,
        "subnets": payload.get("count_subnets") or 0,
        "ranges": payload.get("count_ranges") or 0,
        "ips": payload.get("count_ips") or 0,
        "duplicates": payload.get("count_duplicates") or 0,
        "group_duplicates": payload.get("count_group_duplicates") or 0,
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
        document["objects"] = objects

    unsupported = payload.get("unsupported") or []
    if unsupported:
        document["unsupported"] = unsupported

    copy_lines = _collect_copy_lines(payload)
    if copy_lines:
        document["copy_lines"] = copy_lines

    addr_analysis = _sanitize_tree(payload.get("addr_analysis") or [])
    if addr_analysis:
        document["addr_analysis"] = addr_analysis

    object_tree = _sanitize_tree(payload.get("object_tree") or [])
    if object_tree:
        document["object_tree"] = object_tree

    if payload.get("diff_summary") is not None:
        document["diff_summary"] = payload.get("diff_summary")

    message = (payload.get("message") or "").strip()
    if message:
        document["message"] = message

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
