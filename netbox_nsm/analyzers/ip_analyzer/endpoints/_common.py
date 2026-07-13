"""Shared helpers for IP Analyzer endpoint views."""

from __future__ import annotations


def parse_non_negative_int(value, default=0):
    """Parse non-negative int from query value, fallback to default."""
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return default


def mark_nodes_recursive(nodes, updater):
    """Apply updater to node and descendants."""
    for node in nodes or []:
        updater(node)
        mark_nodes_recursive(node.get("children") or [], updater)


def mark_lazy_loaded_nodes(nodes):
    """Tag rows as loaded via lazy API path."""
    mark_nodes_recursive(nodes, lambda node: node.__setitem__("ipa_lazy_loaded", True))


def mark_lazy_subnet_child_nodes(nodes):
    """Tag rows as lazy subnet child entries."""
    mark_nodes_recursive(nodes, lambda node: node.__setitem__("ipa_lazy_subnet_child", True))
