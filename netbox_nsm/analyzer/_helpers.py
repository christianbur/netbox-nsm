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
    """Bidirectional AnalyzerEdge list from ObjectLink."""
    from netbox_nsm.models import ObjectLink
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    for link in ObjectLink.objects.filter(
        object_a_type=ct, object_a_id=obj.pk
    ).select_related("object_b_type")[:_MAX]:
        if link.object_b is not None:
            edges.append(
                AnalyzerEdge("Linked", "nsm_link", node_from_object(link.object_b))
            )

    for link in ObjectLink.objects.filter(
        object_b_type=ct, object_b_id=obj.pk
    ).select_related("object_a_type")[:_MAX]:
        if link.object_a is not None:
            edges.append(
                AnalyzerEdge("Linked", "nsm_link", node_from_object(link.object_a))
            )

    return edges


def policy_item_edges(obj, ct) -> list:
    """AnalyzerEdge list from RuleObjectItem (one edge per rule)."""
    from netbox_nsm.models import RuleObjectItem
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    for item in RuleObjectItem.objects.filter(
        content_type=ct, object_id=obj.pk
    ).select_related("rule__rulebook", "field")[:15]:
        edges.append(
            AnalyzerEdge(
                f"Regel ({item.field})", "in_rule", node_from_object(item.rule)
            )
        )
    return edges


def group_m2m_edges(obj) -> list:
    """Edges for ``group`` M2M (see ``netbox_nsm.group_m2m``)."""
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.group_m2m import iter_group_m2m_relations

    edge_kinds = {
        "Member": "group_member",
        "Member of": "member_of_group",
    }
    edges = []
    for related, label in iter_group_m2m_relations(obj):
        if len(edges) >= _MAX:
            break
        edges.append(
            AnalyzerEdge(label, edge_kinds[label], node_from_object(related))
        )
    return edges


def addr_fk_edges(obj) -> list:
    """For IPAM objects (Prefix, IPAddress, IPRange): find Custom Objects nsm_addresses
    that reference this IPAM object via FK (prefix_id / ip_address_id / range_id).
    Mirrors the Security Panel's addr-fk lookup.
    """
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    try:
        from netbox_custom_objects.models import CustomObjectType as _COT
        from django.contrib.contenttypes.models import ContentType

        _addr_cot = _COT.objects.filter(slug="nsm_addresses").first()
        if not _addr_cot:
            return edges
        _AddrModel = _addr_cot.get_model()

        model_name = type(obj).__name__
        fk_map = {
            "IPAddress": "ip_address_id",
            "Prefix": "prefix_id",
            "IPRange": "range_id",
        }
        fk_field = fk_map.get(model_name)
        if fk_field:
            for addr_obj in _AddrModel.objects.filter(**{fk_field: obj.pk})[:_MAX]:
                edges.append(AnalyzerEdge("Address Object", "referenced_by", node_from_object(addr_obj)))
    except Exception:
        pass

    return edges


def inherited_nsm_link_edges(obj) -> list:
    """For IPAM objects (Prefix, IPAddress, IPRange): find ObjectLinks
    attached to containing/parent prefixes (inherited via prefix hierarchy).
    Mirrors the Security Panel's inherited link behaviour.
    """
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.ipam_inheritance import ancestor_prefixes_for_ipam
    from netbox_nsm.models import ObjectLink
    from django.contrib.contenttypes.models import ContentType

    edges = []
    try:
        from ipam.models import Prefix as _Prefix

        ancestors = ancestor_prefixes_for_ipam(obj)
        if not ancestors:
            return edges

        ancestor_pks = [p.pk for p in ancestors]
        pfx_ct = ContentType.objects.get_for_model(_Prefix)

        seen_linked = set()
        for link in ObjectLink.objects.filter(
            object_a_type=pfx_ct, object_a_id__in=ancestor_pks
        ).select_related("object_b_type")[:_MAX]:
            if link.object_b is not None and link.object_b.pk not in seen_linked:
                seen_linked.add(link.object_b.pk)
                edges.append(
                    AnalyzerEdge(
                        "Inherited", "inherited_link", node_from_object(link.object_b)
                    )
                )

        for link in ObjectLink.objects.filter(
            object_b_type=pfx_ct, object_b_id__in=ancestor_pks
        ).select_related("object_a_type")[:_MAX]:
            if link.object_a is not None and link.object_a.pk not in seen_linked:
                seen_linked.add(link.object_a.pk)
                edges.append(
                    AnalyzerEdge(
                        "Inherited", "inherited_link", node_from_object(link.object_a)
                    )
                )

    except Exception:
        pass

    return edges

