"""
Edge-building helpers shared across resolver modules.

Kept in a separate module to avoid circular imports:
  registry.py  (defines AnalyzerEdge / node_from_object)
      ↑ imported by
  _helpers.py  (query logic)
      ↑ imported by
  relations.py (concrete resolvers)
"""

from __future__ import annotations

_MAX = 15  # max related nodes per direction


def nsm_link_edges(obj, ct) -> list:
    """Bidirectional AnalyzerEdge list from NSMObjectLink."""
    from netbox_nsm.models import NSMObjectLink
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    for link in NSMObjectLink.objects.filter(
        object_a_type=ct, object_a_id=obj.pk
    ).select_related("object_b_type")[:_MAX]:
        if link.object_b is not None:
            edges.append(
                AnalyzerEdge("Linked", "nsm_link", node_from_object(link.object_b))
            )

    for link in NSMObjectLink.objects.filter(
        object_b_type=ct, object_b_id=obj.pk
    ).select_related("object_a_type")[:_MAX]:
        if link.object_a is not None:
            edges.append(
                AnalyzerEdge("Linked", "nsm_link", node_from_object(link.object_a))
            )

    return edges


def policy_item_edges(obj, ct) -> list:
    """AnalyzerEdge list from SecurityPolicyRuleObjectItem (one edge per rule)."""
    from netbox_nsm.models import SecurityPolicyRuleObjectItem
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    for item in SecurityPolicyRuleObjectItem.objects.filter(
        content_type=ct, object_id=obj.pk
    ).select_related("rule__rulebook", "field")[:15]:
        edges.append(
            AnalyzerEdge(
                f"Regel ({item.field})", "in_rule", node_from_object(item.rule)
            )
        )
    return edges
