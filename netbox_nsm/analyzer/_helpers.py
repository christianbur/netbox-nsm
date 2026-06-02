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


def group_m2m_edges(obj) -> list:
    """Edges for 'group' M2M field (Custom Objects):
    - Forward: members contained in this group (obj.group.all())
    - Reverse: parent groups that contain this object (filter(group=obj))
    Works for any model that has a 'group' M2M field (nsm_addresses, nsm_services).
    """
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []

    # Forward: members of this group
    group_rel = getattr(obj, "group", None)
    if group_rel is not None and hasattr(group_rel, "all"):
        try:
            for member in group_rel.all()[:_MAX]:
                edges.append(AnalyzerEdge("Member", "group_member", node_from_object(member)))
        except Exception:
            pass

    # Reverse: parent groups containing this object
    try:
        parent_groups = list(type(obj).objects.filter(group=obj)[:_MAX])
        for grp in parent_groups:
            edges.append(AnalyzerEdge("Member of", "member_of_group", node_from_object(grp)))
    except Exception:
        pass

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
    """For IPAM objects (Prefix, IPAddress, IPRange): find NSMObjectLinks
    attached to containing/parent prefixes (inherited via prefix hierarchy).
    Mirrors the Security Panel's inherited link behaviour.
    """
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.models import NSMObjectLink
    from django.contrib.contenttypes.models import ContentType

    edges = []
    try:
        from ipam.models import Prefix as _Prefix

        # Collect ancestor prefix PKs
        ancestor_pks = []
        model_name = type(obj).__name__

        if model_name == "Prefix":
            ip_str = str(obj.prefix)
        elif model_name == "IPAddress":
            ip_str = str(obj.address).split("/")[0]
        elif model_name == "IPRange":
            ip_str = str(getattr(obj, "start_address", "")).split("/")[0]
        else:
            return edges

        pfx_ct = ContentType.objects.get_for_model(_Prefix)
        # All prefixes that contain this obj's address
        ancestors = list(
            _Prefix.objects.filter(prefix__net_contains=ip_str)
            .exclude(pk=getattr(obj, "pk", None) if model_name == "Prefix" else None)
            .values_list("pk", flat=True)[:20]
        )

        if not ancestors:
            return edges

        seen_linked = set()
        for link in NSMObjectLink.objects.filter(
            object_a_type=pfx_ct, object_a_id__in=ancestors
        ).select_related("object_b_type")[:_MAX]:
            if link.object_b is not None and link.object_b.pk not in seen_linked:
                seen_linked.add(link.object_b.pk)
                edges.append(AnalyzerEdge("Inherited", "inherited_link", node_from_object(link.object_b)))

        for link in NSMObjectLink.objects.filter(
            object_b_type=pfx_ct, object_b_id__in=ancestors
        ).select_related("object_a_type")[:_MAX]:
            if link.object_a is not None and link.object_a.pk not in seen_linked:
                seen_linked.add(link.object_a.pk)
                edges.append(AnalyzerEdge("Inherited", "inherited_link", node_from_object(link.object_a)))

    except Exception:
        pass

    return edges

