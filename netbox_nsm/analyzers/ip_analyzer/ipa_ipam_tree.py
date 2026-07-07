"""
IPA object-tree IPAM logical drilldown.

Tree shape when expanding an NSM prefix/range node (lazy)::

    NSM prefix/range node (already visible in cell object tree)
      └─ ipam_prefix layer (prefix containers only)
           ├─ child prefix /24
           │    ├─ range → IPs
           │    └─ IP (direct via ``get_child_ips()``)
           └─ IP (direct)
"""
from __future__ import annotations

import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub
from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import _ipa_object_node_presentation
from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import _ipa_object_node_role_from_tree_node
from netbox_nsm.analyzers.ip_analyzer.ipa_tree_dedupe import collapse_sibling_networks
from netbox_nsm.analyzers.ip_analyzer.ipa_tree_dedupe import dedupe_by_network
from netbox_nsm.analyzers.ip_analyzer.ipa_tree_dedupe import strip_redundant_parent_network
from netbox_nsm.analyzers.ip_analyzer.ipa_tree_dedupe import strip_self_referential_redundant_networks


def _resolve_ipam_object_for_drilldown(obj):
    """Return the NetBox Prefix or IPRange linked to a cell object, if any."""
    ip_ref = _hub._addr_ip_ref(obj)
    if ip_ref:
        ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
        if ipam_obj is not None:
            return ipam_obj
    return _hub._ipam_fk_object_for_addr_node(obj)


def _build_ipa_drilldown_source_meta(obj):
    """Summary metadata for the NSM object shown above an IPAM drilldown row."""
    name = str(getattr(obj, "name", None) or obj)
    url = getattr(obj, "get_absolute_url", lambda: "#")()
    meta = {
        "name": name,
        "url": url,
        "tenant_name": "",
        "tenant_url": "",
        "count_subnets": 0,
        "count_ranges": 0,
        "count_ips": 0,
    }
    ipam_obj = _resolve_ipam_object_for_drilldown(obj)
    if ipam_obj is None:
        return meta

    tenant = getattr(ipam_obj, "tenant", None)
    if tenant is not None:
        meta["tenant_name"] = str(tenant)
        if hasattr(tenant, "get_absolute_url"):
            meta["tenant_url"] = tenant.get_absolute_url()

    stats = None
    try:
        from ipam.models import Prefix

        if isinstance(ipam_obj, Prefix):
            stats = _hub._prefix_ipam_stats(ipam_obj)
    except ImportError:
        stats = None
    if stats is None:
        ip_ref = _hub._addr_ip_ref(obj)
        if ip_ref:
            stats = _hub._resolve_ipam_stats_from_ip_ref(ip_ref)
    if stats:
        ordered = (
            _hub._ordered_ipam_stats(stats)
            if isinstance(stats, dict)
            else list(stats)
        )
        meta["count_subnets"] = _hub._ipam_stats_subnet_count(ordered)
        meta["count_ranges"] = _hub._ipam_stats_range_count(ordered)
        meta["count_ips"] = _hub._ipam_stats_ip_count(ordered)
    return meta


def _attach_ipa_drilldown_meta_to_nodes(nodes, meta):
    """Attach parent-object metadata to IPAM prefix layer drilldown roots."""
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            node["ipa_drilldown_meta"] = meta
            return


def _apply_ipam_drilldown_presentation(node):
    """Recursively attach ``node_role`` / ``layer`` hints for IPA drilldown nodes."""
    role = _ipa_object_node_role_from_tree_node(node)
    hints = _ipa_object_node_presentation(
        role, has_member_children=bool(node.get("children"))
    )
    node["node_role"] = hints["node_role"]
    if hints.get("layer"):
        node["layer"] = hints["layer"]
    node.pop("addr_drilldown_lazy", None)
    for child in node.get("children") or []:
        _apply_ipam_drilldown_presentation(child)


def _build_ipa_object_ipam_tree(obj, *, visited=None):
    """
    Build the logical IPAM subtree shown when an IPA object node is expanded.

    Uses NetBox IPAM parent/child prefix relations, ``get_child_ranges()``,
    and ``get_child_ips()`` semantics via ``ipam_drilldown`` helpers.
    """
    if visited is None:
        visited = {obj.pk}

    ipam_obj = _resolve_ipam_object_for_drilldown(obj)
    if ipam_obj is None:
        return []

    try:
        from ipam.models import IPRange, Prefix
    except ImportError:
        return []

    if isinstance(ipam_obj, Prefix):
        return [_hub._build_ipam_prefix_layer_node(ipam_obj, visited)]
    if isinstance(ipam_obj, IPRange):
        node = _hub._build_ipam_range_resolve_nodes(ipam_obj, visited)
        return [node] if node else []
    return []


def _dedupe_ipa_ipam_drilldown_nodes(
    nodes,
    *,
    exclude_network=None,
    seen_keys=None,
    seen_networks=None,
    filter_parent_network=False,
):
    """Drop repeated networks and object identities from the logical IPAM drilldown."""
    return dedupe_by_network(
        nodes,
        exclude_network=exclude_network,
        hoist_children=True,
        seen_keys=seen_keys,
        seen_networks=seen_networks,
        filter_parent_network=filter_parent_network,
    )


def _collect_ipa_drilldown_parent_networks(obj):
    """Collect candidate networks for redundant drilldown stripping."""
    nets = []

    def _add_net(net):
        if net is not None:
            nets.append(net)

    name = getattr(obj, "name", None)
    if isinstance(name, str):
        stripped_name = name.strip()
        if "/" in stripped_name:
            _add_net(_hub._addr_tree_node_network({"prefix_display_cidr": stripped_name}))

    cidr = _hub._ipa_cidr_from_object_name(name)
    if cidr:
        _add_net(_hub._addr_tree_node_network({"prefix_display_cidr": cidr}))

    ip_ref = _hub._addr_ip_ref(obj)
    if ip_ref and ip_ref.get("str"):
        _add_net(_hub._addr_tree_node_network({"ip_ref": ip_ref}))

    ipam_obj = _resolve_ipam_object_for_drilldown(obj)
    if ipam_obj is not None:
        try:
            from ipam.models import Prefix

            if isinstance(ipam_obj, Prefix):
                cidr = str(getattr(ipam_obj, "prefix", ipam_obj) or ipam_obj)
                _add_net(_hub._addr_tree_node_network({"ip_ref": {"str": cidr}}))
        except ImportError:
            pass

    return nets


def _ipa_drilldown_parent_network(obj):
    """Network whose ipam_prefix shell is redundant for this cell object."""
    nets = _all_ipa_drilldown_redundant_networks(obj)
    if not nets:
        return None
    return max(nets, key=lambda net: net.prefixlen)


def _all_ipa_drilldown_redundant_networks(obj):
    """Every object-network candidate that should not repeat in lazy drilldown."""
    nets = list(_collect_ipa_drilldown_parent_networks(obj))
    seen = {net for net in nets}

    name = getattr(obj, "name", None)
    cidr = _hub._ipa_cidr_from_object_name(name)
    if cidr:
        net = _hub._addr_tree_node_network({"prefix_display_cidr": cidr})
        if net is not None and net not in seen:
            nets.append(net)
            seen.add(net)

    ip_ref = _hub._addr_ip_ref(obj)
    if ip_ref and ip_ref.get("str"):
        net = _hub._addr_tree_node_network({"ip_ref": ip_ref})
        if net is not None and net not in seen:
            nets.append(net)
            seen.add(net)

    return nets


def _finalize_ipa_drilldown_nodes(nodes, obj):
    """
    Strip redundant shells that survive a single parent_network pass.

    When the resolved IPAM container is coarser (e.g. ``/24``) but the cell
    object represents ``/28``, stripping the ``/24`` shell hoists a ``/28``
    row that must be removed in a second pass.
    """
    result = nodes
    redundant_nets = _all_ipa_drilldown_redundant_networks(obj)
    for net in sorted(redundant_nets, key=lambda net: net.prefixlen, reverse=True):
        result = strip_redundant_parent_network(
            result, parent_network=net, recursive=True
        )
    return strip_self_referential_redundant_networks(
        result, redundant_networks=redundant_nets, recursive=True
    )


def _infer_ipa_drilldown_parent_network_from_nodes(nodes):
    """Infer redundant-shell network from a lone IPAM drilldown root."""
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            net = _hub._addr_tree_node_network(node)
            if net is not None:
                return net
    if len(nodes or []) == 1:
        net = _hub._addr_tree_node_network(nodes[0])
        if net is not None:
            return net
    return None


def _strip_redundant_parent_network_drilldown_nodes(nodes, *, parent_network=None):
    """Drop drilldown nodes that repeat the parent object network (any layer)."""
    return strip_redundant_parent_network(
        nodes, parent_network=parent_network, recursive=True
    )


def _collapse_duplicate_network_drilldown_siblings(nodes):
    """Keep one drilldown row per network at each sibling level."""
    return collapse_sibling_networks(nodes)


def _enrich_ipa_drilldown_nodes(nodes, *, parent_network=None):
    """
    Filter, annotate, and enrich drilldown nodes for the object API.

    Pipeline (order matters for regression parity)::

        +------------------------------+------------------------------------------+
        | Step                         | Function                                 |
        +==============================+==========================================+
        | 1. Parent-network inference  | ``_infer_ipa_drilldown_parent_network_*``|
        | 2. Category filter           | ``_filter_ipam_drilldown_category_nodes``|
        | 3. Network/object dedupe     | ``_dedupe_ipa_ipam_drilldown_nodes``     |
        | 4. Sibling sort              | ``_sort_ipa_object_tree_siblings``       |
        | 5. Presentation + copy/count | per-node enrich helpers                  |
        | 6. Strip parent network      | ``_strip_redundant_parent_network_*``    |
        | 7. Parent-network hoist      | dedupe with ``filter_parent_network``    |
        | 8. Collapse sibling nets     | ``_collapse_duplicate_network_*``        |
        +------------------------------+------------------------------------------+
    """
    if parent_network is None:
        parent_network = _infer_ipa_drilldown_parent_network_from_nodes(nodes)
    nodes = _hub._filter_ipam_drilldown_category_nodes(nodes)
    nodes = _dedupe_ipa_ipam_drilldown_nodes(nodes, exclude_network=parent_network)
    nodes = _hub._sort_ipa_object_tree_siblings(nodes)
    for node in nodes:
        _apply_ipam_drilldown_presentation(node)
        _hub._enrich_addr_tree_copy_lines(node)
        _hub._enrich_addr_tree_leaf_counts(node)
    nodes = _strip_redundant_parent_network_drilldown_nodes(
        nodes, parent_network=parent_network
    )
    if parent_network is not None:
        nodes = _dedupe_ipa_ipam_drilldown_nodes(
            nodes,
            exclude_network=parent_network,
            filter_parent_network=True,
        )
    nodes = _collapse_duplicate_network_drilldown_siblings(nodes)
    nodes = _hub._sort_ipa_object_tree_siblings(nodes)
    from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _attach_ipa_drilldown_meta

    _attach_ipa_drilldown_meta(nodes, {})
    return nodes


def _ipa_drilldown_nodes_are_shell_only(nodes, *, redundant_nets=()):
    """Single IPAM prefix layer or lone self-referential redundant prefix row."""
    if len(nodes or []) != 1:
        return False
    node = nodes[0]
    if node.get("layer") == "ipam_prefix":
        return not node.get("children")
    if redundant_nets:
        net = _hub._addr_tree_node_network(node)
        if net is not None and any(net == redundant for redundant in redundant_nets):
            from netbox_nsm.analyzers.ip_analyzer.ipa_tree_dedupe import _node_renders_self_reference

            if _node_renders_self_reference(node):
                return not node.get("children")
    return False


def _ipa_object_drilldown_has_visible_content(obj):
    """Whether lazy drilldown would render more than a redundant meta shell."""
    if not obj or not _hub._object_supports_addr_analyzer(obj):
        return False
    nodes = _build_ipa_object_ipam_tree(obj)
    if nodes:
        nodes = _enrich_ipa_drilldown_nodes(
            nodes, parent_network=_ipa_drilldown_parent_network(obj)
        )
        nodes = _finalize_ipa_drilldown_nodes(nodes, obj)
        return bool(nodes) and not _ipa_drilldown_nodes_are_shell_only(
            nodes, redundant_nets=_all_ipa_drilldown_redundant_networks(obj)
        )
    node = _hub._build_addr_tree_node(obj, {obj.pk})
    return bool(node)


def _build_ipa_object_drilldown_nodes(obj):
    """
    Return ``(nodes, copy_lines)`` for ``IpAnalyzerObjectDrilldownApiView``.

    Prefix containers resolve to an explicit ``ipam_prefix`` layer node whose
    children follow the NetBox IPAM hierarchy. Host-only objects fall back to
    a single enriched addr-tree leaf.
    """
    if not obj or not _hub._object_supports_addr_analyzer(obj):
        return [], []

    parent_network = _ipa_drilldown_parent_network(obj)
    redundant_nets = _all_ipa_drilldown_redundant_networks(obj)

    nodes = _build_ipa_object_ipam_tree(obj)
    if nodes:
        nodes = _enrich_ipa_drilldown_nodes(nodes, parent_network=parent_network)
        nodes = _finalize_ipa_drilldown_nodes(nodes, obj)
        if not nodes or _ipa_drilldown_nodes_are_shell_only(
            nodes, redundant_nets=redundant_nets
        ):
            return [], []
        return nodes, _hub._flatten_addr_tree_paths(nodes)

    node = _hub._build_addr_tree_node(obj, {obj.pk})
    if not node:
        return [], []

    if node.get("kind") == "leaf":
        leaf_net = _hub._addr_tree_node_network(node)
        if leaf_net is not None and any(leaf_net == net for net in redundant_nets):
            return [], []
        _apply_ipam_drilldown_presentation(node)
        _hub._enrich_addr_tree_copy_lines(node)
        _hub._enrich_addr_tree_leaf_counts(node)
        return [node], _hub._flatten_addr_tree_paths([node])

    nodes = _enrich_ipa_drilldown_nodes(
        node.get("children") or [],
        parent_network=parent_network,
    )
    nodes = _finalize_ipa_drilldown_nodes(nodes, obj)
    return nodes, _hub._flatten_addr_tree_paths(nodes)


__all__ = (
    "_apply_ipam_drilldown_presentation",
    "_attach_ipa_drilldown_meta_to_nodes",
    "_build_ipa_drilldown_source_meta",
    "_build_ipa_object_drilldown_nodes",
    "_build_ipa_object_ipam_tree",
    "_enrich_ipa_drilldown_nodes",
    "_ipa_drilldown_parent_network",
    "_strip_redundant_parent_network_drilldown_nodes",
    "_ipa_drilldown_nodes_are_shell_only",
    "_ipa_object_drilldown_has_visible_content",
    "_resolve_ipam_object_for_drilldown",
)
