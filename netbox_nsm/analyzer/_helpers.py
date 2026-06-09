"""Edge-building helpers shared across resolver modules."""

from __future__ import annotations

_MAX = 15


def nsm_link_edges(obj, ct) -> list:
    """Bidirectional AnalyzerEdge list from COT ``nsm_object_link`` rows."""
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.objects.object_link_service import iter_links_for_object

    edges = []
    for link, direction in iter_links_for_object(obj):
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        if len(edges) >= _MAX:
            break
        edges.append(
            AnalyzerEdge("Linked", "nsm_link", node_from_object(linked))
        )

    return edges


def rule_object_item_edges(obj, ct) -> list:
    """AnalyzerEdge list from COT rulebook references."""
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.cot_security_panel import scan_cot_security_references

    edges = []
    for match in scan_cot_security_references(ct, obj.pk)[:15]:
        rule = match.get("rule")
        field_name = match.get("field_name") or "rule"
        if rule is None:
            continue
        edges.append(
            AnalyzerEdge(
                f"Regel ({field_name})",
                "in_rule",
                node_from_object(rule),
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
        edges.append(AnalyzerEdge(label, edge_kinds[label], node_from_object(related)))
    return edges


def addr_fk_edges(obj) -> list:
    """For IPAM objects: nsm_addresses FK references."""
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object

    edges = []
    try:
        from netbox_custom_objects.models import CustomObjectType as _COT

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
                edges.append(
                    AnalyzerEdge(
                        "Address Object", "referenced_by", node_from_object(addr_obj)
                    )
                )
    except Exception:
        pass

    return edges


def inherited_nsm_link_edges(obj) -> list:
    """Inherited COT object links from containing prefixes."""
    from netbox_nsm.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.objects.ipam_inheritance import iter_inherited_nsm_links

    edges = []
    try:
        seen_linked = set()
        for inherited in iter_inherited_nsm_links(obj):
            if len(edges) >= _MAX:
                break
            linked = inherited.linked
            if linked is None or linked.pk in seen_linked:
                continue
            seen_linked.add(linked.pk)
            edges.append(
                AnalyzerEdge(
                    "Inherited",
                    "inherited_link",
                    node_from_object(linked),
                )
            )
    except Exception:
        pass

    return edges
