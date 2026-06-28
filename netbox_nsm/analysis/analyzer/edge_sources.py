"""NSM-specific AnalyzerEdge builders (links, rules, groups, IPAM FK, inheritance).

Used by ``all_edges.compose_all_edges`` and registered model resolvers in
``relations``. Distinct from ``analysis/`` (IP/address tree diff for the
Security Panel and IP Analyzer applet).
"""

from __future__ import annotations

_MAX = None  # no cap — object analyzer shows all links


def nsm_link_edges(obj, ct) -> list:
    """Bidirectional AnalyzerEdge list from COT ``nsm_object_link`` rows."""
    from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.objects.object_link_service import iter_links_for_object

    edges = []
    for link, direction in iter_links_for_object(obj):
        linked = link.policy_object if direction == "fwd" else link.netbox_object
        if linked is None:
            continue
        edges.append(
            AnalyzerEdge("Linked", "nsm_link", node_from_object(linked))
        )

    return edges


def rule_object_item_edges(obj, ct) -> list:
    """AnalyzerEdge list from COT rulebook references."""
    from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.security.cot_rule_references import scan_cot_security_references

    edges = []
    for match in scan_cot_security_references(ct, obj.pk):
        rule = match.get("rule")
        field_name = match.get("field_name") or "rule"
        if rule is None:
            continue
        rule_obj = getattr(rule, "_instance", rule)
        try:
            node = node_from_object(rule_obj)
        except Exception:
            continue
        edges.append(
            AnalyzerEdge(
                f"Regel ({field_name})",
                "in_rule",
                node,
            )
        )
    return edges


def group_m2m_edges(obj) -> list:
    """Edges for ``group`` M2M (see ``netbox_nsm.group_m2m``)."""
    from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.objects.group_m2m import iter_group_m2m_relations

    edge_kinds = {
        "Member": "group_member",
        "Member of": "member_of_group",
    }
    edges = []
    for related, label in iter_group_m2m_relations(obj):
        edges.append(AnalyzerEdge(label, edge_kinds[label], node_from_object(related)))
    return edges


def addr_fk_edges(obj) -> list:
    """For IPAM objects: nsm_addresses FK references."""
    from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.addresses.address_ipam_fk import iter_addresses_for_ipam_object

    edges = []
    try:
        for addr_obj, _field_name in iter_addresses_for_ipam_object(obj):
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
    from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, node_from_object
    from netbox_nsm.addresses.ipam_inheritance import iter_inherited_nsm_links

    edges = []
    try:
        seen_linked = set()
        for inherited in iter_inherited_nsm_links(obj):
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
