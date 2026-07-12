
"""IP Analyzer cell object tree (rule-cell hierarchy)."""
from __future__ import annotations
from django.contrib.contenttypes.models import ContentType
import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub
from netbox_nsm.analyzers.ip_analyzer.addr_ip_refs import _FIELD_TYPE_LABELS
from netbox_nsm.analyzers.ip_analyzer.addr_netmask import sync_prefix_display_netmask
from netbox_nsm.core.nsm_object_status import (
    NSM_OBJECT_STATUS_DEPRECATED,
    NSM_OBJECT_STATUS_RESERVED,
    get_nsm_object_status,
    normalize_nsm_object_status,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree import _ipa_object_drilldown_has_visible_content
from netbox_nsm.analyzers.ip_analyzer.ipa_perf import ipa_lazy_load_enabled
from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import (
    IPA_NODE_ROLE_EMPTY,
    IPA_NODE_ROLE_GROUP,
    IPA_NODE_ROLE_HOST,
    IPA_NODE_ROLE_PREFIX,
    IPA_NODE_ROLE_RANGE,
    _ipa_object_expands_members,
    _ipa_object_group_members,
    _ipa_object_has_addr_drilldown,
    _ipa_object_node_apply_presentation,
    _ipa_object_node_presentation,
    _ipa_object_node_role_from_cidr_hint,
    _ipa_object_node_role_from_ip_ref,
    _ipa_object_node_role_from_obj,
    _ipa_object_node_role_from_tree_node,
    _ipa_object_node_should_drilldown,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_network_identity import (
    host_network_from_value,
    values_equal as _ipa_values_equal,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_cell_merge import (
    collapse_siblings_by_network as _ipa_collapse_siblings_by_network,
    merge_nodes_by_network as _ipa_merge_nodes_by_network,
)

IPA_TREE_NODE_CELL_SELECTED = "cell_selected"
IPA_TREE_NODE_IPAM_FILLER = "ipam_filler"
IPA_TREE_NODE_INFO_GAP = "info_gap"

# Groups with more members expand only co-selected addresses (bench-scale safety).
IPA_CELL_GROUP_FULL_EXPAND_MAX = 32
# Skip full IPAM child-IP enumeration above this count (memory/timeout guard).
IPA_IPAM_CHILD_IP_ENUM_MAX = 4096
# Membership pills collapse to an expandable summary when many groups apply.
IPA_CELL_GROUPS_COLLAPSE_THRESHOLD = 4
# Multiple collapsed root-level group selections fold into one summary section.
IPA_CELL_ROOT_GROUPS_COLLAPSE_THRESHOLD = 3

IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS = "collapsed_root_groups"

def _build_ipa_object_columns(selections, objs):
    """IP Analyzer: one table column per selected object (name + counter in header)."""
    columns = []
    for sel, obj in zip(selections, objs):
        analysis = _hub._build_multi_object_addr_analyzer([obj]) if obj else []
        columns.append(
            {
                "name": sel["name"],
                "ct": sel["ct"],
                "pk": sel["pk"],
                "leaf_count": _hub._leaf_count_for_addr_analyzer(analysis),
                "addr_analyzer": analysis,
            }
        )
    return columns


def _parse_ipa_column_selections(request, col_suffix=""):
    """
    Parse repeated ip_ct/ip_pk/ip_name (or ip2_*) query params.
    Returns (selections, addr_analyzer) where selections is
    [{"ct", "pk", "name"}, ...].
    """
    from django.contrib.contenttypes.models import ContentType as _CT

    prefix = f"ip{col_suffix}_"
    ct_list = request.GET.getlist(prefix + "ct")
    pk_list = request.GET.getlist(prefix + "pk")
    name_list = request.GET.getlist(prefix + "name")

    selections = []
    objs = []
    seen: set = set()

    for i, ct_str in enumerate(ct_list):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        name_hint = name_list[i] if i < len(name_list) else ""
        if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
            continue
        key = (int(ct_str), int(pk_str))
        if key in seen:
            continue
        try:
            ct = _CT.objects.get(pk=key[0])
            mc = ct.model_class()
            if not mc:
                continue
            obj = mc.objects.filter(pk=key[1]).first()
            if not obj:
                continue
            seen.add(key)
            name = getattr(obj, "name", None) or name_hint or str(obj)
            selections.append({"ct": str(key[0]), "pk": str(key[1]), "name": str(name)})
            objs.append(obj)
        except Exception:
            continue

    return selections, _build_ipa_object_columns(selections, objs)


def _ipa_object_expands_members(obj) -> bool:
    """Re-export from ``ipa_object_node`` (stable ``@patch`` target)."""
    from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import _ipa_object_expands_members as _impl

    return _impl(obj)


def _ipa_object_has_addr_drilldown(obj) -> bool:
    """Re-export from ``ipa_object_node`` (stable ``@patch`` target)."""
    from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import _ipa_object_has_addr_drilldown as _impl

    return _impl(obj)


def _ipa_cell_tree_has_visible_address_children(node):
    """True when the cell tree already shows address rows under a prefix/range."""
    for child in node.get("children") or []:
        if child.get("ipa_tree_node_type") == IPA_TREE_NODE_INFO_GAP:
            continue
        if (
            child.get("is_ipam_filler")
            or child.get("ipam_synthetic")
            or child.get("is_ipam_synthesized")
        ):
            if _ipa_cell_tree_has_visible_address_children(child):
                return True
            continue
        role = _ipa_object_node_role_from_tree_node(child)
        if role in (IPA_NODE_ROLE_HOST, IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE):
            return True
    return False


def _refresh_ipa_cell_tree_inventory_roles(nodes, obj_by_key=None):
    """Re-apply prefix/host/range roles after CIDR enrichment."""
    del obj_by_key  # reserved for stable signature / future ORM hints
    for node in nodes or []:
        if node.get("node_role") == IPA_NODE_ROLE_EMPTY:
            role = _ipa_object_node_role_from_tree_node(node)
            if role != IPA_NODE_ROLE_EMPTY:
                hints = _ipa_object_node_presentation(
                    role, has_member_children=bool(node.get("children"))
                )
                node["node_role"] = hints["node_role"]
                node["kind"] = hints["kind"]
        _refresh_ipa_cell_tree_inventory_roles(node.get("children") or [])


def _ipa_prefix_broadcast_ip_int(prefix):
    """Return the broadcast host integer for gap rows (ipaddress or netaddr)."""
    if prefix is None:
        return None
    try:
        net = prefix.prefix
    except Exception:
        return None
    try:
        if hasattr(net, "broadcast_address"):
            return int(net.broadcast_address)
        if hasattr(net, "broadcast"):
            return int(net.broadcast)
    except (TypeError, ValueError):
        return None
    return None


def _ipa_tree_cache_bucket(resolve_cache, name):
    if resolve_cache is None:
        return None
    return resolve_cache.setdefault(name, {})


def _ipa_tree_ref_cache_key(ip_ref):
    if not isinstance(ip_ref, dict):
        return None
    ct_raw = ip_ref.get("ct")
    pk_raw = ip_ref.get("pk")
    if str(ct_raw or "").isdigit() and str(pk_raw or "").isdigit():
        return ("ctpk", int(ct_raw), int(pk_raw))
    ref_type = str(ip_ref.get("type") or "").strip().casefold()
    ref_str = str(ip_ref.get("str") or "").strip().casefold()
    if ref_str:
        return ("ref", ref_type, ref_str)
    return None


def _ipa_tree_prefix_cache_key(prefix):
    if prefix is None:
        return None
    try:
        pk = getattr(prefix, "pk", None)
        if pk is not None:
            return ("prefix", int(pk))
    except (TypeError, ValueError):
        pass
    try:
        cidr = str(prefix.prefix).strip().casefold()
    except Exception:
        cidr = ""
    return ("prefix-cidr", cidr) if cidr else None


def _ipa_cached_resolve_ipam_stats(ip_ref, *, resolve_cache=None):
    cache = _ipa_tree_cache_bucket(resolve_cache, "ipam_stats")
    cache_key = _ipa_tree_ref_cache_key(ip_ref)
    if cache is None or cache_key is None:
        return _hub._resolve_ipam_stats_from_ip_ref(ip_ref)
    if cache_key not in cache:
        cache[cache_key] = _hub._resolve_ipam_stats_from_ip_ref(ip_ref)
    return cache[cache_key]


def _ipa_cached_lookup_prefix(ip_ref, *, resolve_cache=None):
    cache = _ipa_tree_cache_bucket(resolve_cache, "prefix_lookup")
    cache_key = _ipa_tree_ref_cache_key(ip_ref)
    if cache is None or cache_key is None:
        return _hub._lookup_ipam_prefix_from_ip_ref(ip_ref)
    if cache_key not in cache:
        cache[cache_key] = _hub._lookup_ipam_prefix_from_ip_ref(ip_ref)
    return cache[cache_key]


def _ipa_cached_prefix_stats(prefix, *, resolve_cache=None):
    cache = _ipa_tree_cache_bucket(resolve_cache, "prefix_stats")
    cache_key = _ipa_tree_prefix_cache_key(prefix)
    if cache is None or cache_key is None:
        return _hub._prefix_ipam_stats(prefix)
    if cache_key not in cache:
        cache[cache_key] = _hub._prefix_ipam_stats(prefix)
    return cache[cache_key]


def _attach_ipa_object_tree_ipam_stats(nodes, obj_by_key=None, resolve_cache=None):
    """Attach NetBox prefix/range tab counts to object-tree nodes for summary badges."""
    for node in nodes or []:
        if not node.get("ipam_stats"):
            ip_ref = node.get("ip_ref") or {}
            stats = None
            if ip_ref:
                stats = _ipa_cached_resolve_ipam_stats(
                    ip_ref, resolve_cache=resolve_cache
                )
            if stats is None and node.get("prefix_display_cidr"):
                stats = _ipa_cached_resolve_ipam_stats(
                    {"str": node["prefix_display_cidr"]},
                    resolve_cache=resolve_cache,
                )
            if stats is None:
                cidr = _ipa_cidr_from_object_name(node.get("name"))
                if cidr:
                    stats = _ipa_cached_resolve_ipam_stats(
                        {"str": cidr}, resolve_cache=resolve_cache
                    )
            if stats is None and obj_by_key:
                key = _ipa_object_tree_node_key(node)
                obj = obj_by_key.get(key) if key else None
                if obj is not None:
                    full_ref = _hub._addr_ip_ref(obj)
                    if full_ref is not None:
                        stats = _ipa_cached_resolve_ipam_stats(
                            full_ref, resolve_cache=resolve_cache
                        )
                    if stats is None:
                        prefix = _ipa_prefix_for_cell_object(obj)
                        if prefix is not None:
                            stats = _ipa_cached_prefix_stats(
                                prefix, resolve_cache=resolve_cache
                            )
            if stats:
                _hub._attach_ipam_stats_meta(node, stats)
        _attach_ipa_object_tree_ipam_stats(
            node.get("children") or [], obj_by_key, resolve_cache=resolve_cache
        )


def _ipa_drilldown_meta_from_ipam_stats(node, stats=None):
    """Build compact prefix/range/IP counters for the IP/Range/Prefix column."""
    if stats is not None:
        ordered = (
            _hub._ordered_ipam_stats(stats)
            if isinstance(stats, dict)
            else list(stats)
        )
    elif node.get("ipam_stats"):
        ordered = node["ipam_stats"]
    else:
        return None
    return {
        "count_subnets": _hub._ipam_stats_subnet_count(ordered),
        "count_ranges": _hub._ipam_stats_range_count(ordered),
        "count_ips": _hub._ipam_stats_ip_count(ordered),
    }


def _resolve_ipa_drilldown_meta_for_node(node, obj_by_key=None, resolve_cache=None):
    """Return drilldown counters for a prefix/range tree node."""
    from netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree import _build_ipa_drilldown_source_meta
    from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import (
        _ipa_object_node_role_from_cidr_hint,
    )

    role = _ipa_object_node_role_from_tree_node(node)
    cidr = node.get("prefix_display_cidr") or (node.get("ip_ref") or {}).get("str")
    cidr_role = _ipa_object_node_role_from_cidr_hint(cidr)
    ip_ref = node.get("ip_ref") or {}
    has_explicit_host_ref = ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]
    cidr_looks_host = cidr_role == IPA_NODE_ROLE_HOST
    lock_host_role = role == IPA_NODE_ROLE_HOST and (has_explicit_host_ref or cidr_looks_host)
    if not lock_host_role and cidr_role in {IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE}:
        role = cidr_role
    if role not in {IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE}:
        return None
    key = _ipa_object_tree_node_key(node)
    obj = obj_by_key.get(key) if key and obj_by_key else None
    if obj is not None:
        return _build_ipa_drilldown_source_meta(obj)
    meta = _ipa_drilldown_meta_from_ipam_stats(node)
    if meta is not None:
        return meta
    ip_ref = node.get("ip_ref") or {}
    candidates = [ip_ref]
    cidr = node.get("prefix_display_cidr")
    if cidr and cidr != ip_ref.get("str"):
        candidates.append({"str": cidr})
    name_cidr = _ipa_cidr_from_object_name(node.get("name"))
    if name_cidr and name_cidr not in {ref.get("str") for ref in candidates}:
        candidates.append({"str": name_cidr})
    for ref in candidates:
        if not ref or not ref.get("str"):
            continue
        stats = _ipa_cached_resolve_ipam_stats(ref, resolve_cache=resolve_cache)
        if stats is not None:
            return _ipa_drilldown_meta_from_ipam_stats(node, stats)
    return None


def _attach_ipa_drilldown_meta(nodes, obj_by_key=None, resolve_cache=None):
    """Attach NetBox child counters to prefix/range rows in the cell tree."""
    for node in nodes or []:
        if not node.get("ipa_drilldown_meta"):
            meta = _resolve_ipa_drilldown_meta_for_node(
                node, obj_by_key, resolve_cache=resolve_cache
            )
            if meta is not None:
                node["ipa_drilldown_meta"] = meta
        _attach_ipa_drilldown_meta(
            node.get("children") or [], obj_by_key, resolve_cache=resolve_cache
        )


def _ensure_ipa_cell_tree_network_links(nodes, obj_by_key=None, resolve_cache=None):
    """Ensure the network column can link rows backed by NSM or IPAM objects."""
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            _ensure_ipa_cell_tree_network_links(
                node.get("children") or [], obj_by_key, resolve_cache=resolve_cache
            )
            continue
        if node.get("is_ipam_filler") or node.get("ipam_synthetic"):
            cidr = node.get("prefix_display_cidr")
            ip_ref = node.get("ip_ref") or {}
            if cidr and not ip_ref.get("url"):
                prefix = _ipa_cached_lookup_prefix(
                    {"str": cidr}, resolve_cache=resolve_cache
                )
                if prefix is not None:
                    _enrich_ipa_node_from_resolved_prefix(node, prefix)
            _ensure_ipa_cell_tree_network_links(
                node.get("children") or [], obj_by_key, resolve_cache=resolve_cache
            )
            continue

        cidr = node.get("prefix_display_cidr") or (node.get("ip_ref") or {}).get("str")
        if cidr:
            ip_ref = dict(node.get("ip_ref") or {})
            if not ip_ref.get("str"):
                ip_ref["str"] = cidr
            if not ip_ref.get("url"):
                key = _ipa_object_tree_node_key(node)
                obj = obj_by_key.get(key) if key and obj_by_key else None
                if obj is not None:
                    full_ref = _hub._addr_ip_ref(obj)
                    if full_ref and full_ref.get("url"):
                        ip_ref["url"] = full_ref["url"]
                    elif getattr(obj, "get_absolute_url", None):
                        ip_ref["url"] = obj.get_absolute_url()
                if not ip_ref.get("url") and node.get("url"):
                    ip_ref["url"] = node["url"]
                if not ip_ref.get("url"):
                    prefix = _ipa_cached_lookup_prefix(
                        ip_ref, resolve_cache=resolve_cache
                    )
                    if prefix is not None:
                        ip_ref["url"] = prefix.get_absolute_url()
                        ip_ref.setdefault("type", _FIELD_TYPE_LABELS["prefix"])
            if ip_ref.get("str") and ip_ref.get("url"):
                node["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
            elif ip_ref.get("str"):
                node["ip_ref"] = ip_ref
        _ensure_ipa_cell_tree_network_links(
            node.get("children") or [], obj_by_key, resolve_cache=resolve_cache
        )


def _attach_ipa_cell_address_fields(nodes, obj_by_key=None):
    """
    Ensure the flat cell-tree **Address** column can render NSM address names.

    - Collapsed address-group rows get ``cell_group_anchor_address`` from their subnet
      anchor member (same pick as ``_enrich_ipa_collapsed_group_networks_from_members``).
    - Group members and cell-direct address rows keep resolvable ``name``/``url`` pairs.
    """
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            _attach_ipa_cell_address_fields(node.get("children") or [], obj_by_key)
            continue
        if _ipa_tree_node_is_structural(node):
            _attach_ipa_cell_address_fields(node.get("children") or [], obj_by_key)
            continue

        key = _ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        role = _ipa_object_node_role_from_tree_node(node)

        if (
            role == IPA_NODE_ROLE_GROUP
            and obj is not None
            and _ipa_object_expands_members(obj)
            and not node.get("cell_group_anchor_address")
        ):
            anchor = _ipa_resolve_group_anchor_member(obj)
            if anchor is not None:
                node["cell_group_anchor_address"] = _cell_address_ref_from_obj(anchor)
        elif role != IPA_NODE_ROLE_GROUP and (
            node.get("cell_groups")
            or node.get("is_cell_direct")
            or node.get("in_cell")
        ):
            if node.get("name") and not node.get("url") and obj is not None:
                node["url"] = obj.get_absolute_url()

        _attach_ipa_cell_address_fields(node.get("children") or [], obj_by_key)


def _attach_ipa_object_tree_ip_meta(node, obj):
    """Attach IP/CIDR display; keep kind/role from ``_ipa_object_node_apply_presentation``."""
    if _ipa_object_expands_members(obj):
        return node
    ip_ref = _hub._addr_ip_ref(obj)
    if not ip_ref:
        from netbox_nsm.addresses.address_literal import attach_literal_prefix_display

        return attach_literal_prefix_display(node, obj)
    node["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
    _hub._attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)
    return node


def _build_ipa_object_tree_node(obj, *, ct_id=None, member_visited=None, group_depth=0):
    """
    Shallow object hierarchy for the IP analyzer cell object tree.

    - Groups expand members recursively (groups-in-groups).
    - Prefix/range addresses become expandable IPAM containers (lazy drilldown).
    - Host IPs stay leaves; counts come from parent prefix/range in merge view.
    """
    if member_visited is None:
        member_visited = set()

    if obj.pk in member_visited:
        return None
    member_visited = set(member_visited)
    member_visited.add(obj.pk)

    if ct_id is None:
        from django.contrib.contenttypes.models import ContentType

        ct_id = ContentType.objects.get_for_model(obj).pk

    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        name = str(obj)
    name = str(name or obj)
    url = getattr(obj, "get_absolute_url", lambda: "#")()

    if _ipa_object_expands_members(obj):
        child_visited = set(member_visited)
        children = []
        for sub in _ipa_object_group_members(obj):
            child = _build_ipa_object_tree_node(
                sub,
                member_visited=child_visited,
                group_depth=group_depth + 1,
            )
            if child:
                children.append(child)
        node = {
            "name": name,
            "url": url,
            "ct": str(ct_id),
            "pk": str(obj.pk),
            "kind": "group",
            "children": [],
        }
        _ipa_object_node_apply_presentation(
            node,
            obj,
            group_depth=group_depth,
            member_children=children,
        )
        return _attach_ipa_object_tree_ip_meta(node, obj)

    node = {
        "name": name,
        "url": url,
        "ct": str(ct_id),
        "pk": str(obj.pk),
        "kind": "leaf",
        "children": [],
    }
    node = _ipa_object_node_apply_presentation(node, obj, group_depth=group_depth)
    return _attach_ipa_object_tree_ip_meta(node, obj)


def _ipa_object_tree_node_key(node):
    try:
        return (int(node.get("ct") or 0), int(node.get("pk") or 0))
    except (TypeError, ValueError):
        return None


def _collect_ipa_object_tree_keys(nodes):
    keys = set()
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        if key and key != (0, 0):
            keys.add(key)
        keys.update(_collect_ipa_object_tree_keys(node.get("children") or []))
    return keys


def _collapse_ipa_cell_object_tree_roots(nodes):
    """Drop root entries already shown under another root's member subtree."""
    if len(nodes) <= 1:
        return nodes
    covered = set()
    for root in nodes:
        for child in root.get("children") or []:
            covered.update(_collect_ipa_object_tree_keys([child]))
    return [
        node
        for node in nodes
        if _ipa_object_tree_node_key(node) not in covered
    ]


def _cell_group_ref_key(ref):
    return (ref.get("name"), ref.get("url"))


def _cell_group_none_ref():
    """Synthetic group for addresses listed directly in the cell."""
    return {"name": "none", "url": "", "is_none": True}


def _is_cell_group_none_ref(ref):
    """True for the synthetic ungrouped marker (never shown in the UI)."""
    if not ref:
        return False
    if ref.get("is_none"):
        return True
    return str(ref.get("name") or "").strip().casefold() == "none"


def _display_cell_group_refs(refs):
    """Real ADDRESS_GROUP refs only; ``none`` is internal and must not render."""
    return [ref for ref in (refs or []) if not _is_cell_group_none_ref(ref)]


def _apply_node_cell_groups(node, refs, *, is_cell_direct=False):
    """Attach visible ``cell_groups`` metadata; append ``none`` when also cell-direct."""
    display = _display_cell_group_refs(refs)
    if _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP:
        display = [
            ref for ref in display if not _cell_group_ref_matches_node(ref, node)
        ]
    if is_cell_direct and len(display) > 1:
        display = display + [_cell_group_none_ref()]
    if display:
        node["cell_groups"] = display
        node["cell_groups_multi"] = len(display) > 1
        node.pop("cell_groups_none", None)
        return
    node.pop("cell_groups", None)
    node.pop("cell_groups_multi", None)
    if is_cell_direct or not refs:
        node["cell_groups_none"] = True
    else:
        node.pop("cell_groups_none", None)


def _append_cell_group_ref(refs, ref):
    """Append a group ref when not already present (stable order)."""
    if not ref or not ref.get("name") or _is_cell_group_none_ref(ref):
        return refs
    seen = {_cell_group_ref_key(item) for item in refs}
    key = _cell_group_ref_key(ref)
    if key in seen:
        return refs
    return refs + [ref]


def _ipa_object_member_key(obj):
    """Return ``(content_type_id, pk)`` for an ORM object."""
    try:
        ct_id = ContentType.objects.get_for_model(obj).pk
    except Exception:
        return None
    try:
        return int(ct_id), int(obj.pk)
    except (TypeError, ValueError):
        return None


def _build_ipa_cell_group_selection_node(obj, *, ct_id=None):
    """Collapsed group row for a cell-selected address group (no member expansion)."""
    if ct_id is None:
        ct_id = ContentType.objects.get_for_model(obj).pk

    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        name = str(obj)
    name = str(name or obj)
    url = getattr(obj, "get_absolute_url", lambda: "#")()

    node = {
        "name": name,
        "url": url,
        "ct": str(ct_id),
        "pk": str(obj.pk),
        "kind": "group",
        "children": [],
        "is_cell_direct": True,
    }
    node = _ipa_object_node_apply_presentation(
        node, obj, group_depth=0, member_children=[]
    )
    node["kind"] = "group"
    node["node_role"] = IPA_NODE_ROLE_GROUP
    status = get_nsm_object_status(obj)
    if status:
        node["status"] = status
    return node


def _build_ipa_cell_flat_address_node(obj, *, ct_id=None):
    """Build one address node for the flattened cell tree (no group expansion)."""
    if ct_id is None:
        ct_id = ContentType.objects.get_for_model(obj).pk

    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        name = str(obj)
    name = str(name or obj)
    url = getattr(obj, "get_absolute_url", lambda: "#")()

    node = {
        "name": name,
        "url": url,
        "ct": str(ct_id),
        "pk": str(obj.pk),
        "kind": "leaf",
        "children": [],
    }
    node = _ipa_object_node_apply_presentation(node, obj, group_depth=0)
    status = get_nsm_object_status(obj)
    if status:
        node["status"] = status
    return _attach_ipa_object_tree_ip_meta(node, obj)


def _yield_flat_cell_addresses(
    obj,
    *,
    ct_id,
    group_refs=None,
    member_visited=None,
):
    """
    Expand a cell object to address nodes with ancestor group refs from selections.

    Groups are not emitted as tree nodes; each member address carries ``cell_groups``.
    """
    if member_visited is None:
        member_visited = set()

    if obj.pk in member_visited:
        return
    member_visited = set(member_visited)
    member_visited.add(obj.pk)

    group_refs = list(group_refs or [])

    if _ipa_object_expands_members(obj):
        members = list(_ipa_object_group_members(obj))
        if members:
            grp_ref = {
                "name": str(getattr(obj, "name", None) or obj),
                "url": getattr(obj, "get_absolute_url", lambda: "#")(),
            }
            status = get_nsm_object_status(obj)
            if status:
                grp_ref["status"] = status
            expanded_refs = _append_cell_group_ref(group_refs, grp_ref)
            for member in members:
                try:
                    member_ct = ContentType.objects.get_for_model(member).pk
                except Exception:
                    member_ct = ct_id
                yield from _yield_flat_cell_addresses(
                    member,
                    ct_id=member_ct,
                    group_refs=expanded_refs,
                    member_visited=member_visited,
                )
            return

    node = _build_ipa_cell_flat_address_node(obj, ct_id=ct_id)
    if node:
        yield node, list(group_refs)


def _cell_group_ref_for_object(obj):
    ref = {
        "name": str(getattr(obj, "name", None) or obj),
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
    }
    status = get_nsm_object_status(obj)
    if status:
        ref["status"] = status
    return ref


def _merge_flat_cell_address_entry(
    merged,
    *,
    node,
    group_refs,
    is_cell_direct=False,
):
    addr_key = _ipa_object_tree_node_key(node)
    if not addr_key:
        return
    entry = merged.get(addr_key)
    if entry is None:
        entry = {
            "node": node,
            "group_refs": [],
            "is_cell_direct": False,
        }
        merged[addr_key] = entry
    for ref in group_refs or []:
        entry["group_refs"] = _append_cell_group_ref(entry["group_refs"], ref)
    if is_cell_direct:
        entry["is_cell_direct"] = True


def _flatten_cell_selections_to_address_nodes(raw_selections, obj_by_key):
    """
    Merge cell selections into unique address nodes with ``cell_groups`` metadata.

    Large address groups (bench-scale) do not expand every member: only addresses
    also selected in the cell are flattened; otherwise the group stays a collapsed row.
    """
    cell_object_keys: set[tuple[int, int]] = set()
    for sel in raw_selections or []:
        try:
            cell_object_keys.add((int(sel["ct"]), int(sel["pk"])))
        except (KeyError, TypeError, ValueError):
            continue

    merged: dict[tuple[int, int], dict] = {}
    root_counts: dict[tuple[int, int], int] = {}

    for sel in raw_selections or []:
        try:
            sel_key = (int(sel["ct"]), int(sel["pk"]))
        except (KeyError, TypeError, ValueError):
            continue
        obj = obj_by_key.get(sel_key)
        if not obj:
            continue
        root_counts[sel_key] = root_counts.get(sel_key, 0) + 1
        is_group_sel = _ipa_object_expands_members(obj)

        if is_group_sel:
            members = list(_ipa_object_group_members(obj))
            group_expand_max = IPA_CELL_GROUP_FULL_EXPAND_MAX
            if len(members) > group_expand_max:
                grp_ref = _cell_group_ref_for_object(obj)
                direct_members = [
                    member
                    for member in members
                    if _ipa_object_member_key(member) in cell_object_keys
                ]
                if direct_members:
                    for member in direct_members:
                        member_key = _ipa_object_member_key(member)
                        member_ct = member_key[0] if member_key else sel_key[0]
                        for node, group_refs in _yield_flat_cell_addresses(
                            member,
                            ct_id=member_ct,
                            group_refs=[grp_ref],
                        ):
                            _merge_flat_cell_address_entry(
                                merged,
                                node=node,
                                group_refs=group_refs,
                                is_cell_direct=member_key in cell_object_keys,
                            )
                elif sel_key not in merged:
                    merged[sel_key] = {
                        "node": _build_ipa_cell_group_selection_node(
                            obj, ct_id=sel_key[0]
                        ),
                        "group_refs": [],
                        "is_cell_direct": True,
                    }
                continue

        for node, group_refs in _yield_flat_cell_addresses(obj, ct_id=sel_key[0]):
            _merge_flat_cell_address_entry(
                merged,
                node=node,
                group_refs=group_refs,
                is_cell_direct=not is_group_sel
                and _ipa_object_tree_node_key(node) == sel_key,
            )

    nodes = []
    for entry in merged.values():
        node = entry["node"]
        refs = entry["group_refs"]
        _apply_node_cell_groups(node, refs, is_cell_direct=entry["is_cell_direct"])
        if entry["is_cell_direct"]:
            node["is_cell_direct"] = True
        addr_key = _ipa_object_tree_node_key(node)
        if addr_key and root_counts.get(addr_key, 0) > 1:
            node["is_doppelt"] = True
        nodes.append(node)
    return nodes


def _ipa_network_from_cidr_text(text):
    """Parse a CIDR/range hint to ``ip_network`` (``None`` when not a network)."""
    import ipaddress

    if not text:
        return None
    try:
        return ipaddress.ip_network(str(text).strip(), strict=False)
    except ValueError:
        return None


def _ipa_std_network(net):
    """Normalize ipaddress / NetBox netaddr networks for containment checks."""
    import ipaddress

    if net is None:
        return None
    if isinstance(net, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
        return net
    try:
        return ipaddress.ip_network(str(net).strip(), strict=False)
    except ValueError:
        return None


def _ipa_net_subnet_of(child_net, parent_net):
    """True when *child_net* is a strict subnet of *parent_net*."""
    child = _ipa_std_network(child_net)
    parent = _ipa_std_network(parent_net)
    if child is None or parent is None:
        return False
    return child.subnet_of(parent) and child != parent


def _ipa_tree_node_is_structural(node):
    """True for synthetic IPA rows (IPAM filler or host-gap summary)."""
    if node.get("ipa_tree_node_type") in (
        IPA_TREE_NODE_INFO_GAP,
        IPA_TREE_NODE_IPAM_FILLER,
        IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS,
    ):
        return True
    if node.get("kind") == "ipa_info_gap" or node.get("info_summary"):
        return True
    return False


def _ipa_resolve_netbox_prefix_for_tree_node(node, obj_by_key=None, *, prefix_cache=None):
    """Return the NetBox Prefix best matching a cell-tree node, if any."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
    try:
        from ipam.models import Prefix

        if isinstance(ipam_obj, Prefix):
            return ipam_obj
    except ImportError:
        pass

    if obj_by_key:
        key = _ipa_object_tree_node_key(node)
        if key:
            obj = obj_by_key.get(key)
            if obj is not None:
                prefix = _ipa_prefix_for_cell_object(obj)
                if prefix is not None:
                    return prefix
    return _lookup_containing_prefix_for_ipa_cell_node(
        node, obj_by_key, prefix_cache=prefix_cache
    )


def _ipa_intermediate_ipam_prefix_chain(parent_net, child_prefix):
    """NetBox parent prefixes strictly between *parent_net* and *child_prefix*."""
    if child_prefix is None:
        return []
    try:
        desc_net = _ipa_std_network(child_prefix.prefix)
        parents = list(child_prefix.get_parents())
    except Exception:
        return []
    if desc_net is None:
        return []
    parent_net = _ipa_std_network(parent_net)
    chain = []
    for ancestor in sorted(parents, key=lambda item: item.prefix.prefixlen):
        anet = _ipa_std_network(ancestor.prefix)
        if anet is None or anet == desc_net:
            continue
        if not _ipa_net_subnet_of(desc_net, anet):
            continue
        if parent_net is not None:
            if anet == parent_net:
                continue
            if not _ipa_net_subnet_of(anet, parent_net):
                continue
        chain.append(ancestor)
    return chain


def _build_ipa_ipam_filler_prefix_node(prefix):
    """Grey IPAM hierarchy row — completes the tree but is not in the rule cell."""
    node = _build_ipa_synthesized_parent_prefix_node(prefix)
    node["ipa_tree_node_type"] = IPA_TREE_NODE_IPAM_FILLER
    node["is_ipam_filler"] = True
    node["ipam_synthetic"] = True
    node["is_ipam_synthesized"] = True
    node.pop("is_ipam_parent_prefix", None)
    return node


def _insert_ipam_filler_prefixes(nodes, obj_by_key, *, prefix_cache=None):
    """Insert missing NetBox IPAM parent prefixes between hierarchy edges."""
    result = []
    for node in nodes or []:
        children = node.get("children") or []
        if children:
            node["children"] = _insert_ipam_filler_prefixes(
                children, obj_by_key, prefix_cache=prefix_cache
            )
            parent_net = _ipa_object_tree_containment_network(node)
            reparented = []
            for child in node["children"]:
                if _ipa_tree_node_is_structural(child):
                    reparented.append(child)
                    continue
                child_prefix = _ipa_resolve_netbox_prefix_for_tree_node(
                    child, obj_by_key, prefix_cache=prefix_cache
                )
                chain = _ipa_intermediate_ipam_prefix_chain(parent_net, child_prefix)
                if chain:
                    existing_nets = {
                        _ipa_object_tree_network_key(sibling)
                        for sibling in node["children"]
                        if not _ipa_tree_node_is_structural(sibling)
                    }
                    chain = [
                        prefix
                        for prefix in chain
                        if _ipa_object_tree_network_key(
                            {"prefix_display_cidr": str(prefix.prefix)}
                        )
                        not in existing_nets
                    ]
                if not chain:
                    reparented.append(child)
                    continue
                target = child
                for prefix in sorted(
                    chain, key=lambda item: item.prefix.prefixlen, reverse=True
                ):
                    filler = _build_ipa_ipam_filler_prefix_node(prefix)
                    filler["children"] = [target]
                    filler["kind"] = "group"
                    target = filler
                reparented.append(target)
            node["children"] = _sort_ipa_object_tree_siblings(reparented)
        result.append(node)
    return result


def _ipa_host_ip_int(node):
    """Host address as integer for sibling gap math."""
    net = _ipa_object_tree_containment_network(node)
    if net is None:
        return None
    try:
        if net.prefixlen != net.max_prefixlen:
            return None
        return int(net.network_address)
    except (TypeError, ValueError):
        return None


def _ipa_count_used_ips_in_open_interval(prefix, low_ip_int, high_ip_int):
    """Count NetBox child IPs strictly between two host integers."""
    if prefix is None or low_ip_int is None or high_ip_int is None:
        return None
    if high_ip_int <= low_ip_int + 1:
        return 0
    try:
        import ipaddress

        low = ipaddress.ip_address(low_ip_int)
        high = ipaddress.ip_address(high_ip_int)
        count = 0
        for ip_obj in prefix.get_child_ips():
            addr = ipaddress.ip_address(str(ip_obj.address).split("/")[0])
            if low < addr < high:
                count += 1
        return count
    except Exception:
        return None


def _ipa_format_gap_label(used, unused=None):
    if unused is not None and unused > 0:
        return f"[{used} used / {unused} unused ip]"
    return f"[{used} used ip]"


def _is_ipa_ipam_filler_node(node):
    """True for IPAM hierarchy filler/synthetic prefix rows (not in the rule cell)."""
    return (
        node.get("ipa_tree_node_type") == IPA_TREE_NODE_IPAM_FILLER
        or node.get("is_ipam_filler")
        or node.get("ipam_synthetic")
        or node.get("is_ipam_synthesized")
    )


def _ipa_cell_tree_flat_row_is_visible(node):
    """True when a node should render as a row in the flat IPA cell-tree table."""
    if _is_ipa_info_gap_node(node):
        return False
    if _is_ipa_ipam_filler_node(node):
        return False
    return True


def _is_ipa_info_gap_node(node):
    """True for IPAM host-gap summary rows (structural, not NSM objects)."""
    return (
        node.get("ipa_tree_node_type") == IPA_TREE_NODE_INFO_GAP
        or node.get("kind") == "ipa_info_gap"
        or node.get("info_summary")
    )


def _ipa_info_gap_display_label(node):
    """Human-readable IPAM gap summary for templates (Us column)."""
    for key in ("ipa_gap_display_label", "ipa_gap_label"):
        raw = (node or {}).get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    raw = (node or {}).get("info_summary_label")
    if raw is not None:
        text = str(raw).strip()
        if text:
            if text.startswith("[") and text.endswith("]"):
                return text
            return f"[{text}]"
    return ""


def _ipa_info_gap_row_is_visible(node):
    """True when an info-gap row has text to show in the cell tree."""
    if not _is_ipa_info_gap_node(node):
        return False
    return bool(_ipa_info_gap_display_label(node))


def _scrub_stale_ipa_info_gap_node(node):
    """Drop gap markers on nodes that no longer have display text."""
    if not _is_ipa_info_gap_node(node):
        return
    if _ipa_info_gap_display_label(node):
        return
    node.pop("info_summary", None)
    node.pop("ipa_tree_node_type", None)
    node.pop("ipa_gap_display_label", None)
    node.pop("ipa_gap_label", None)
    node.pop("info_summary_label", None)
    if node.get("kind") == "ipa_info_gap":
        node.pop("kind", None)


def _collapse_consecutive_ipa_info_gap_nodes(nodes):
    """Drop label-less gaps and duplicate consecutive gap summaries in sibling lists."""
    pruned = []
    for node in nodes or []:
        children = node.get("children")
        if children:
            node["children"] = _collapse_consecutive_ipa_info_gap_nodes(children)
        if _is_ipa_info_gap_node(node) and not _ipa_info_gap_display_label(node):
            continue
        pruned.append(node)

    if not pruned:
        return pruned

    merged = []
    prev_gap_label = None
    for node in pruned:
        if _is_ipa_info_gap_node(node):
            label = _ipa_info_gap_display_label(node)
            if label and label == prev_gap_label:
                continue
            prev_gap_label = label
        else:
            prev_gap_label = None
        merged.append(node)
    return merged


def _attach_ipa_info_gap_display_labels(nodes):
    """Set ``ipa_gap_display_label`` on visible gap rows; clear on others."""
    for node in nodes or []:
        if _ipa_info_gap_row_is_visible(node):
            node["ipa_gap_display_label"] = _ipa_info_gap_display_label(node)
        else:
            node.pop("ipa_gap_display_label", None)
        _attach_ipa_info_gap_display_labels(node.get("children") or [])


def _prune_empty_ipa_info_gap_nodes(nodes):
    """Drop info-gap rows that have no display label (avoid blank table rows)."""
    pruned = []
    for node in nodes or []:
        if _is_ipa_info_gap_node(node) and not _ipa_info_gap_display_label(node):
            continue
        children = node.get("children")
        if children:
            node["children"] = _prune_empty_ipa_info_gap_nodes(children)
        _scrub_stale_ipa_info_gap_node(node)
        pruned.append(node)
    return pruned


def _prune_ipa_info_gap_nodes(nodes):
    """Drop all IPAM info-gap rows from the cell-tree (not shown in the flat table)."""
    pruned = []
    for node in nodes or []:
        children = node.get("children")
        if children:
            node["children"] = _prune_ipa_info_gap_nodes(children)
        if _is_ipa_info_gap_node(node):
            continue
        pruned.append(node)
    return pruned


def _build_ipa_info_gap_node(*, label, used, unused=None, sort_key):
    display = str(label or "").strip()
    return {
        "kind": "ipa_info_gap",
        "info_summary": True,
        "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
        "name": display,
        "info_summary_label": display.strip("[]"),
        "info_summary_used": used,
        "info_summary_unused": unused,
        "ipa_gap_label": display,
        "ipa_gap_display_label": display,
        "ipa_gap_used": used,
        "ipa_gap_unused": unused,
        "ipa_gap_sort_key": int(sort_key),
        "children": [],
    }


def _insert_ipa_host_gap_info_rows(nodes, obj_by_key, *, prefix_cache=None):
    """Insert muted gap summaries between shown host siblings under a prefix."""
    for node in nodes or []:
        children = node.get("children") or []
        if children:
            node["children"] = _insert_ipa_host_gap_info_rows(
                children, obj_by_key, prefix_cache=prefix_cache
            )
            children = node.get("children") or []

        role = _ipa_object_node_role_from_tree_node(node)
        if role != IPA_NODE_ROLE_PREFIX:
            continue

        prefix = _ipa_resolve_netbox_prefix_for_tree_node(
            node, obj_by_key, prefix_cache=prefix_cache
        )
        if prefix is None:
            continue

        host_children = [
            child
            for child in children
            if not _ipa_tree_node_is_structural(child)
            and _ipa_object_node_role_from_tree_node(child) == IPA_NODE_ROLE_HOST
        ]
        if len(host_children) < 1:
            continue

        new_children = []
        prev_host = None
        for child in children:
            if child.get("ipa_tree_node_type") == IPA_TREE_NODE_INFO_GAP:
                continue
            if _ipa_object_node_role_from_tree_node(child) == IPA_NODE_ROLE_HOST:
                host_ip = _ipa_host_ip_int(child)
                if (
                    prev_host is not None
                    and host_ip is not None
                    and (prev_ip := _ipa_host_ip_int(prev_host)) is not None
                    and host_ip > prev_ip + 1
                ):
                    gap_total = host_ip - prev_ip - 1
                    used = _ipa_count_used_ips_in_open_interval(
                        prefix, prev_ip, host_ip
                    )
                    if used is None:
                        used = gap_total
                    unused = max(gap_total - used, 0)
                    label = _ipa_format_gap_label(
                        used, unused if unused > 0 else None
                    )
                    if str(label).strip() and gap_total > 0:
                        new_children.append(
                            _build_ipa_info_gap_node(
                                label=label,
                                used=used,
                                unused=unused if unused > 0 else None,
                                sort_key=prev_ip + 1,
                            )
                        )
                new_children.append(child)
                prev_host = child
            else:
                new_children.append(child)

        if prev_host is not None:
            last_ip = _ipa_host_ip_int(prev_host)
            if last_ip is not None:
                broadcast_ip = _ipa_prefix_broadcast_ip_int(prefix)
                if broadcast_ip is not None and last_ip < broadcast_ip:
                    gap_total = broadcast_ip - last_ip
                    used = _ipa_count_used_ips_in_open_interval(
                        prefix, last_ip, broadcast_ip + 1
                    )
                    if used is None:
                        used = 0
                    unused = max(gap_total - used, 0)
                    if gap_total > 0:
                        label = _ipa_format_gap_label(
                            used, unused if unused > 0 else None
                        )
                        if str(label).strip():
                            new_children.append(
                                _build_ipa_info_gap_node(
                                    label=label,
                                    used=used,
                                    unused=unused if unused > 0 else None,
                                    sort_key=last_ip + 1,
                                )
                            )

        node["children"] = _sort_ipa_object_tree_siblings(new_children)
    return nodes


def _ipa_object_tree_sort_key(node):
    """IPAM sibling order: network address (numeric), then prefix length, then name."""
    if node.get("ipa_tree_node_type") == IPA_TREE_NODE_INFO_GAP:
        sort_key = node.get("ipa_gap_sort_key")
        try:
            return (0, 4, int(sort_key), 31, node.get("name") or "")
        except (TypeError, ValueError):
            return (0, 4, 0, 31, node.get("name") or "")
    net = _ipa_object_tree_containment_network(node)
    if net is None:
        return (1, 0, 0, 0, node.get("name") or "")
    return (
        0,
        net.version,
        int(net.network_address),
        net.prefixlen,
        node.get("name") or "",
    )


def _sort_ipa_object_tree_siblings(nodes):
    """Sort every sibling list in the object/IPAM tree using IPAM order."""
    sorted_nodes = sorted(nodes or [], key=_ipa_object_tree_sort_key)
    for node in sorted_nodes:
        children = node.get("children")
        if children:
            node["children"] = _sort_ipa_object_tree_siblings(children)
    return sorted_nodes


def _ipa_cidr_from_host_object_name(name):
    """Parse bench/demo host names like ``h-10.112.134.44`` to ``/32`` CIDR."""
    import re

    if not isinstance(name, str):
        return None
    match = re.match(r"^h-(.+)$", name.strip(), re.I)
    if not match:
        return None
    host = match.group(1).strip()
    if not re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host):
        return None
    return f"{host}/32"


def _ipa_object_tree_containment_network(node):
    """
    Network used for merge/nesting.

    Host IPs stay ``/32`` even when display metadata carries a parent ``/24``.
    """
    import ipaddress

    role = _ipa_object_node_role_from_tree_node(node or {})
    ip_ref = (node or {}).get("ip_ref") or {}

    # Prefer canonical data from the referenced IPAM object (ct/pk) so host
    # merging stays stable even when display strings contain FQDN/domain labels.
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref) if ip_ref else None
    if ipam_obj is not None:
        ipam_model = _ipa_ipam_model_name(ipam_obj)
        ipam_address = getattr(ipam_obj, "address", None)
        ipam_prefix = getattr(ipam_obj, "prefix", None)
        ipam_start = getattr(ipam_obj, "start_address", None)
        looks_like_ipaddress = (
            ipam_address is not None and ipam_prefix is None and ipam_start is None
        )
        force_host = (
            role == IPA_NODE_ROLE_HOST
            or ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]
            or ipam_model == "ipaddress"
            or looks_like_ipaddress
        )
        for candidate in (
            getattr(ipam_obj, "address", None),
            getattr(ipam_obj, "prefix", None),
        ):
            if not candidate:
                continue
            try:
                net = ipaddress.ip_network(str(candidate).strip(), strict=False)
            except ValueError:
                continue
            if force_host:
                host_net = host_network_from_value(candidate)
                if host_net is not None:
                    return host_net
                continue
            return net

        start_address = getattr(ipam_obj, "start_address", None)
        if start_address:
            try:
                host_ip = ipaddress.ip_address(str(start_address).strip())
                return ipaddress.ip_network(
                    f"{host_ip}/{host_ip.max_prefixlen}", strict=False
                )
            except ValueError:
                pass

    if role == IPA_NODE_ROLE_HOST or ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]:
        for candidate in (
            _ipa_cidr_from_host_object_name(node.get("name")),
            ip_ref.get("str"),
        ):
            if not candidate:
                continue
            host_net = host_network_from_value(candidate)
            if host_net is None:
                continue
            return host_net
        # Do not fall back to prefix-scale hints (/24, /16, ...) for host rows.
        # Otherwise unrelated host-like entries can collapse into one row and
        # incorrectly show MERGE/DUP badges.
        return None
    net = _hub._addr_tree_node_network(node)
    if net is not None:
        normalized = _ipa_std_network(net)
        if normalized is not None:
            return normalized
    for candidate in (
        node.get("prefix_display_cidr"),
        ip_ref.get("str"),
        _ipa_cidr_from_object_name(node.get("name")),
        _ipa_cidr_from_host_object_name(node.get("name")),
    ):
        net = _ipa_network_from_cidr_text(candidate)
        if net is not None:
            return net
    return None


def _ipa_object_tree_network_key(node):
    """Stable network identity for deduplicating cell-tree rows."""
    if _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP:
        return None
    net = _ipa_object_tree_containment_network(node)
    if net is None:
        return None
    return (net.version, int(net.network_address), net.prefixlen)


def _ipa_cell_tree_summary_network_key(node):
    """Network identity for visible cell-tree summary badges, including group rows."""
    net = _ipa_object_tree_containment_network(node)
    if net is None:
        return None
    return (net.version, int(net.network_address), net.prefixlen)


def _cell_address_ref(node):
    """One address identity for the ADDRESS pill."""
    name = node.get("name") if isinstance(node, dict) else None
    if not name:
        return None
    ref = {"name": str(name), "url": str(node.get("url") or "#")}
    status = node.get("status") if isinstance(node, dict) else None
    if status:
        ref["status"] = status
    return ref


def _cell_address_ref_from_obj(obj, *, ct_id=None):
    """Build one address ref dict from an ORM object."""
    if obj is None:
        return None
    if ct_id is None:
        try:
            ct_id = ContentType.objects.get_for_model(obj).pk
        except Exception:
            ct_id = None
    name = getattr(obj, "name", None)
    if not isinstance(name, str):
        name = str(obj)
    name = str(name or obj).strip()
    if not name:
        return None
    ref = {
        "name": name,
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
    }
    if ct_id is not None:
        ref["ct"] = str(ct_id)
        ref["pk"] = str(obj.pk)
    status = get_nsm_object_status(obj)
    if status:
        ref["status"] = status
    return ref


def _attach_status_to_cell_ref(ref, obj=None):
    """Attach reserved/deprecated status to a cell pill ref when not active."""
    if not ref or ref.get("is_none"):
        return ref
    status = ref.get("status")
    if not status and obj is not None:
        status = get_nsm_object_status(obj)
        if status:
            ref["status"] = status
    return ref


def _lookup_obj_for_cell_ref(ref, obj_by_key):
    if not ref or not obj_by_key:
        return None
    ct = ref.get("ct")
    pk = ref.get("pk")
    if ct is not None and pk is not None:
        try:
            return obj_by_key.get((int(ct), int(pk)))
        except (TypeError, ValueError):
            pass
    name = str(ref.get("name") or "").strip()
    if not name:
        return None
    for obj in obj_by_key.values():
        if str(getattr(obj, "name", None) or obj) == name:
            return obj
    return None


def _attach_ipa_object_tree_status(nodes, obj_by_key=None):
    """Mark non-active NSM objects for italic pill text and info icons."""
    for node in nodes or []:
        obj = None
        key = _ipa_object_tree_node_key(node)
        if key and obj_by_key:
            obj = obj_by_key.get(key)
        if obj is not None:
            status = get_nsm_object_status(obj)
            if status:
                node["status"] = status
        for ref in node.get("cell_addresses") or []:
            _attach_status_to_cell_ref(ref, _lookup_obj_for_cell_ref(ref, obj_by_key))
        for ref in node.get("cell_groups") or []:
            _attach_status_to_cell_ref(ref, _lookup_obj_for_cell_ref(ref, obj_by_key))
        anchor_ref = node.get("cell_group_anchor_address")
        if anchor_ref:
            _attach_status_to_cell_ref(
                anchor_ref, _lookup_obj_for_cell_ref(anchor_ref, obj_by_key)
            )
        _attach_ipa_object_tree_status(node.get("children") or [], obj_by_key)


_DUP_CELL_STATUS_ORDER = (
    NSM_OBJECT_STATUS_DEPRECATED,
    NSM_OBJECT_STATUS_RESERVED,
)


def _collect_ipa_dup_cell_statuses(node):
    """Unique non-active NSM statuses for the Dup column (row object + cell refs)."""
    seen: set[str] = set()
    found: list[str] = []

    def _add(raw):
        status = normalize_nsm_object_status(raw)
        if not status or status in seen:
            return
        seen.add(status)
        found.append(status)

    _add(node.get("status"))
    primary = node.get("cell_address_primary") or {}
    _add(primary.get("status"))
    for ref in node.get("cell_addresses") or []:
        _add(ref.get("status"))
    for ref in node.get("cell_groups") or []:
        if ref.get("is_none"):
            continue
        _add(ref.get("status"))

    order = {value: index for index, value in enumerate(_DUP_CELL_STATUS_ORDER)}
    return sorted(found, key=lambda value: order.get(value, len(order)))


def _attach_ipa_dup_cell_statuses(nodes):
    """Attach ``dup_cell_statuses`` for compact non-active badges in the Dup column."""
    for node in nodes or []:
        statuses = _collect_ipa_dup_cell_statuses(node)
        if statuses:
            node["dup_cell_statuses"] = statuses
        else:
            node.pop("dup_cell_statuses", None)
        _attach_ipa_dup_cell_statuses(node.get("children") or [])


def _append_cell_address_ref(refs, node):
    """Append an address ref when not already present (stable order)."""
    ref = _cell_address_ref(node)
    if not ref:
        return refs
    key = (ref.get("name"), ref.get("url"))
    if any((item.get("name"), item.get("url")) == key for item in (refs or [])):
        return refs
    return list(refs or []) + [ref]


def _sync_cell_addresses(node):
    """Ensure ``cell_addresses`` reflects the visible ADDRESS pill entries."""
    refs = list(node.get("cell_addresses") or [])
    refs = _append_cell_address_ref(refs, node)
    if len(refs) <= 1:
        node.pop("cell_addresses", None)
        node.pop("cell_addresses_multi", None)
        return
    node["cell_addresses"] = refs
    node["cell_addresses_multi"] = True


def _merge_ipa_cell_node_metadata(keeper, other):
    """Merge ``other`` into ``keeper`` when both resolve to the same network."""
    merged_refs = list(keeper.get("cell_groups") or [])
    for ref in other.get("cell_groups") or []:
        merged_refs = _append_cell_group_ref(merged_refs, ref)

    address_refs = list(keeper.get("cell_addresses") or [])
    address_refs = _append_cell_address_ref(address_refs, keeper)
    address_refs = _append_cell_address_ref(address_refs, other)
    if len(address_refs) > 1:
        keeper["cell_addresses"] = address_refs
        keeper["cell_addresses_multi"] = True

    if other.get("is_doppelt"):
        keeper["is_doppelt"] = True

    for field in ("ip_ref", "prefix_display_cidr", "prefix_display_netmask"):
        if not keeper.get(field) and other.get(field):
            keeper[field] = other[field]

    other_children = other.get("children") or []
    if other_children:
        keeper["children"] = (keeper.get("children") or []) + other_children

    is_cell_direct = bool(keeper.get("is_cell_direct") or other.get("is_cell_direct"))
    if other.get("is_cell_direct") and not keeper.get("is_cell_direct"):
        keeper["is_cell_direct"] = True
        keeper["name"] = other.get("name") or keeper.get("name")
        keeper["url"] = other.get("url") or keeper.get("url")
        keeper["ct"] = other.get("ct") or keeper.get("ct")
        keeper["pk"] = other.get("pk") or keeper.get("pk")
    elif other.get("is_cell_direct"):
        keeper["is_cell_direct"] = True

    _apply_node_cell_groups(keeper, merged_refs, is_cell_direct=is_cell_direct)


def _merge_ipa_cell_nodes_by_network(nodes):
    """Collapse distinct address objects that resolve to the same network."""
    return _ipa_merge_nodes_by_network(
        nodes,
        network_key_fn=_ipa_object_tree_network_key,
        sort_fn=_sort_ipa_object_tree_siblings,
        merge_metadata_fn=_merge_ipa_cell_node_metadata,
        sync_addresses_fn=_sync_cell_addresses,
    )


def _collapse_ipa_cell_siblings_by_network(nodes):
    """Merge same-network siblings at every tree level (one row per CIDR)."""
    return _ipa_collapse_siblings_by_network(
        nodes,
        merge_nodes_fn=_merge_ipa_cell_nodes_by_network,
    )


def _ipa_cidr_from_dashed_octet_tail(name):
    """Parse trailing ``a-b-c-d-plen`` from bench/test address names."""
    import re

    if not isinstance(name, str):
        return None
    match = re.search(
        r"(?<![0-9])(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,3})-(\d{1,2})$",
        name.strip(),
    )
    if not match:
        return None
    octets = match.groups()[:4]
    prefixlen = int(match.group(5))
    if not 0 <= prefixlen <= 128:
        return None
    if not all(0 <= int(part) <= 255 for part in octets):
        return None
    return f"{'.'.join(octets)}/{prefixlen}"


def _ipa_cidr_from_object_name(name):
    """Extract CIDR from NSM names (``g-10.0.0.0/8``, ``dm-addr-10-112-148-0-28``, …)."""
    import re

    if not isinstance(name, str):
        return None
    text = name.strip()
    match = re.match(r"^[gn]-(.+)$", text, re.I)
    if match:
        cidr = match.group(1).strip()
        return cidr if "/" in cidr else None
    match = re.match(r"^dm-addr-(.+)$", text, re.I)
    if match:
        tail = match.group(1).strip()
        dotted = re.match(r"^(\d{1,3}(?:\.\d{1,3}){3})[-/](\d{1,3})$", tail)
        if dotted:
            octets = dotted.group(1).split(".")
            prefixlen = int(dotted.group(2))
            if (
                0 <= prefixlen <= 128
                and len(octets) == 4
                and all(part.isdigit() and 0 <= int(part) <= 255 for part in octets)
            ):
                return f"{dotted.group(1)}/{prefixlen}"
        parts = tail.split("-")
        if len(parts) >= 5 and parts[-1].isdigit():
            prefixlen = int(parts[-1])
            octets = parts[:-1]
            if len(octets) == 4 and all(
                part.isdigit() and 0 <= int(part) <= 255 for part in octets
            ):
                return f"{'.'.join(octets)}/{prefixlen}"
    host_cidr = _ipa_cidr_from_host_object_name(text)
    if host_cidr:
        return host_cidr
    return _ipa_cidr_from_dashed_octet_tail(text)


def _enrich_ipa_object_tree_networks_from_objects(nodes, obj_by_key):
    """Attach missing ``ip_ref`` / ``prefix_display_cidr`` from cell objects before merge/sort."""
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        if obj is not None:
            ip_ref = _hub._addr_ip_ref(obj)
            if ip_ref:
                if not node.get("ip_ref"):
                    node["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
                if not node.get("prefix_display_cidr"):
                    _hub._attach_addr_node_prefix_display(
                        node,
                        obj=obj,
                        ip_ref=node.get("ip_ref") or ip_ref,
                    )
            elif not node.get("prefix_display_cidr"):
                from netbox_nsm.addresses.address_literal import (
                    attach_literal_prefix_display,
                )

                attach_literal_prefix_display(node, obj)
            prefix = _ipa_prefix_for_cell_object(obj)
            if prefix is not None and ip_ref:
                _enrich_ipa_node_from_resolved_prefix(node, prefix)
        _enrich_ipa_object_tree_networks_from_objects(
            node.get("children") or [], obj_by_key
        )


def _ipa_member_containment_network(member):
    """Resolve one member object's network for group IPAM placement."""
    from netbox_nsm.addresses.address_literal import policy_address_network

    policy_net = policy_address_network(member)
    if policy_net is not None:
        return policy_net
    ip_ref = _hub._addr_ip_ref(member)
    if ip_ref and ip_ref.get("str"):
        net = _ipa_network_from_cidr_text(ip_ref.get("str"))
        if net is not None:
            return net
    prefix = _ipa_prefix_for_cell_object(member)
    if prefix is not None:
        net = _ipa_network_from_cidr_text(str(prefix.prefix))
        if net is not None:
            return net
    for candidate in (
        _ipa_cidr_from_object_name(getattr(member, "name", None)),
        _ipa_cidr_from_host_object_name(getattr(member, "name", None)),
    ):
        net = _ipa_network_from_cidr_text(candidate)
        if net is not None:
            return net
    return None


def _ipa_networks_equal(left, right):
    """True when IP/prefix/range values represent the same endpoint set."""
    return _ipa_values_equal(left, right)


def _ipa_resolve_group_containment_network_from_members(obj):
    """
    Pick a subnet anchor for a collapsed address group from its members.

    Prefers prefix-scale member networks (/24, …) over host /32 rows so the
    group nests under the containing prefix in the IPAM hierarchy.
    """
    networks = []
    for member in _ipa_object_group_members(obj):
        net = _ipa_member_containment_network(member)
        if net is not None:
            networks.append(net)
    if not networks:
        return None
    non_host = [net for net in networks if net.prefixlen < net.max_prefixlen]
    if non_host:
        return min(non_host, key=lambda net: net.prefixlen)
    return min(networks, key=lambda net: net.prefixlen)


def _ipa_resolve_group_anchor_member(obj):
    """
    Return the member address object that anchors a collapsed group row.

    Uses the same subnet selection as ``_ipa_resolve_group_containment_network_from_members``;
    prefers prefix-scale members over host /32 rows.
    """
    target_net = _ipa_resolve_group_containment_network_from_members(obj)
    if target_net is None:
        return None
    prefix_members = []
    host_members = []
    for member in _ipa_object_group_members(obj):
        net = _ipa_member_containment_network(member)
        if not _ipa_networks_equal(net, target_net):
            continue
        if net.prefixlen < net.max_prefixlen:
            prefix_members.append(member)
        else:
            host_members.append(member)
    if prefix_members:
        return prefix_members[0]
    if host_members:
        return host_members[0]
    return None


def _enrich_ipa_collapsed_group_networks_from_members(nodes, obj_by_key):
    """
    Attach ``prefix_display_cidr`` to collapsed address-group rows from members.

    Runs after network merge so groups are not deduplicated with address rows
    that share the same CIDR, but before IPAM reorganization so groups nest under
    the prefix where their member subnets live.
    """
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        if (
            obj is not None
            and _ipa_object_expands_members(obj)
            and _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP
            and not _hub._addr_tree_node_network(node)
        ):
            net = _ipa_resolve_group_containment_network_from_members(obj)
            if net is not None:
                node["prefix_display_cidr"] = str(net)
                sync_prefix_display_netmask(node)
        _enrich_ipa_collapsed_group_networks_from_members(
            node.get("children") or [], obj_by_key
        )


def _enrich_ipa_object_tree_cidr_from_names(nodes):
    """Infer ``prefix_display_cidr`` / prefix role from object names (e.g. ``dm-addr-*``)."""
    for node in nodes or []:
        if not node.get("prefix_display_cidr"):
            cidr = _ipa_cidr_from_host_object_name(node.get("name"))
            if not cidr:
                cidr = _ipa_cidr_from_object_name(node.get("name"))
            if cidr:
                node["prefix_display_cidr"] = cidr
        sync_prefix_display_netmask(node)
        if not node.get("ip_ref") and node.get("prefix_display_cidr"):
            role = _ipa_object_node_role_from_cidr_hint(node["prefix_display_cidr"])
            if role in (
                IPA_NODE_ROLE_PREFIX,
                IPA_NODE_ROLE_RANGE,
                IPA_NODE_ROLE_HOST,
            ):
                hints = _ipa_object_node_presentation(
                    role, has_member_children=bool(node.get("children"))
                )
                node["node_role"] = hints["node_role"]
                node["kind"] = hints["kind"]
        _enrich_ipa_object_tree_cidr_from_names(node.get("children") or [])


def _cell_group_ref_matches_node(ref, node):
    """True when *ref* identifies the same NSM object as *node*."""
    if not ref or not node:
        return False
    node_key = _ipa_object_tree_node_key(node)
    ref_ct = ref.get("ct")
    ref_pk = ref.get("pk")
    if node_key and ref_ct is not None and ref_pk is not None:
        try:
            return (int(ref_ct), int(ref_pk)) == node_key
        except (TypeError, ValueError):
            pass
    return _cell_group_ref_key(ref) == (
        node.get("name"),
        node.get("url"),
    )


def _scrub_ipa_cell_group_self_refs(nodes):
    """
    Remove a node's own group identity from ``cell_groups``.

    Directly selected address groups render an ADDRESS_GROUP self pill
    (``cell_pill_group``). Membership pills list ancestor groups only.
    """
    for node in nodes or []:
        if node.get("cell_pill_group") or (
            node.get("is_cell_direct")
            and _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP
        ):
            refs = node.get("cell_groups")
            if refs:
                filtered = [
                    ref
                    for ref in refs
                    if not _cell_group_ref_matches_node(ref, node)
                ]
                _apply_node_cell_groups(
                    node,
                    filtered,
                    is_cell_direct=bool(node.get("is_cell_direct")),
                )
        _scrub_ipa_cell_group_self_refs(node.get("children") or [])


def _ipa_prefix_contains_host(prefix_obj, host_str):
    """True when *host_str* lies inside *prefix_obj* (stdlib ipaddress)."""
    import ipaddress

    try:
        net = ipaddress.ip_network(str(prefix_obj.prefix).strip(), strict=False)
        addr = ipaddress.ip_address(str(host_str).strip())
    except ValueError:
        return False
    return addr in net


def _ipa_most_specific_prefix_for_host(host_str, prefixes):
    """Pick the longest matching prefix from an in-memory list."""
    matches = [
        prefix
        for prefix in prefixes or []
        if _ipa_prefix_contains_host(prefix, host_str)
    ]
    if not matches:
        return None
    matches.sort(key=lambda prefix: prefix.prefix.prefixlen, reverse=True)
    return matches[0]


def _ipa_query_prefixes_containing_hosts(hosts):
    """Single ORM query for all prefixes containing any of *hosts*."""
    hosts = {str(host).strip() for host in (hosts or []) if str(host).strip()}
    if not hosts:
        return []
    try:
        from django.db.models import Q
        from ipam.models import Prefix
    except ImportError:
        return []
    query = Q()
    for host in hosts:
        query |= Q(prefix__net_contains=host)
    return list(Prefix.objects.filter(query))


def _ipa_cell_node_host_lookup_key(node, obj_by_key=None):
    """
    Return a host address string for batched ``prefix__net_contains`` lookup.

    Returns ``None`` when the node resolves to a Prefix directly (via ip_ref or
    cell object) and no host containment query is needed.
    """
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
    try:
        from ipam.models import IPAddress, Prefix

        if isinstance(ipam_obj, Prefix):
            return None
        if isinstance(ipam_obj, IPAddress):
            return str(ipam_obj.address).split("/")[0]
    except ImportError:
        pass

    if obj_by_key:
        key = _ipa_object_tree_node_key(node)
        if key:
            obj = obj_by_key.get(key)
            if obj is not None and _ipa_prefix_for_cell_object(obj) is not None:
                return None

    cidr = node.get("prefix_display_cidr") or ip_ref.get("str")
    if not cidr:
        return None
    try:
        import ipaddress

        net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        if net.prefixlen == net.max_prefixlen:
            return str(net.network_address)
    except ValueError:
        return None
    return None


class _IpaContainingPrefixCache:
    """Batch NetBox Prefix containment lookups for IPA cell-tree walks."""

    _IS_PREFIX = object()

    def __init__(self):
        self._host_to_prefix: dict[str, object | None] = {}
        self._node_results: dict[int, object | None] = {}
        self._pending_hosts: set[str] = set()
        self._batch_loaded = False

    def register_tree(self, nodes, obj_by_key=None):
        """Collect host keys under *nodes*; batch query runs on first ``resolve()``."""
        self._collect_host_keys(nodes, obj_by_key, self._pending_hosts)

    def _collect_host_keys(self, nodes, obj_by_key, hosts):
        for node in nodes or []:
            host = _ipa_cell_node_host_lookup_key(node, obj_by_key)
            if host:
                hosts.add(host)
            self._collect_host_keys(node.get("children") or [], obj_by_key, hosts)

    def _resolve_hosts_batch(self, hosts):
        prefixes = _ipa_query_prefixes_containing_hosts(hosts)
        return {
            host: _ipa_most_specific_prefix_for_host(host, prefixes)
            for host in hosts
        }

    def _ensure_batch_loaded(self):
        if self._batch_loaded or not self._pending_hosts:
            return
        self._batch_loaded = True
        try:
            self._host_to_prefix.update(self._resolve_hosts_batch(self._pending_hosts))
        except Exception:
            pass

    def _lookup_host(self, host_str):
        host = str(host_str).strip()
        if not host:
            return None
        self._ensure_batch_loaded()
        if host not in self._host_to_prefix:
            try:
                self._host_to_prefix.update(self._resolve_hosts_batch({host}))
            except Exception:
                self._host_to_prefix.setdefault(host, None)
        return self._host_to_prefix.get(host)

    def resolve(self, node, obj_by_key=None):
        """Return the most specific containing Prefix for *node*, using cache."""
        node_id = id(node)
        if node_id in self._node_results:
            cached = self._node_results[node_id]
            return None if cached is self._IS_PREFIX else cached

        ip_ref = node.get("ip_ref") or {}
        ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
        try:
            from ipam.models import IPAddress, Prefix

            if isinstance(ipam_obj, Prefix):
                self._node_results[node_id] = self._IS_PREFIX
                return ipam_obj
            if isinstance(ipam_obj, IPAddress):
                prefix = self._lookup_host(str(ipam_obj.address).split("/")[0])
                if prefix is not None:
                    self._node_results[node_id] = prefix
                    return prefix
        except ImportError:
            pass

        if obj_by_key:
            key = _ipa_object_tree_node_key(node)
            if key:
                obj = obj_by_key.get(key)
                if obj is not None:
                    prefix = _ipa_prefix_for_cell_object(obj)
                    if prefix is not None:
                        self._node_results[node_id] = prefix
                        return prefix

        host = _ipa_cell_node_host_lookup_key(node, obj_by_key)
        if host:
            prefix = self._lookup_host(host)
            if prefix is not None:
                self._node_results[node_id] = prefix
                return prefix

        prefix = _lookup_containing_prefix_for_ipa_cell_node_impl(node, obj_by_key)
        self._node_results[node_id] = prefix
        return prefix


def _lookup_containing_prefix_for_ipa_cell_node_impl(node, obj_by_key=None):
    """Uncached NetBox Prefix containment lookup for a cell-tree node."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
    try:
        from ipam.models import IPAddress, Prefix

        if isinstance(ipam_obj, Prefix):
            return ipam_obj
        if isinstance(ipam_obj, IPAddress):
            ip_str = str(ipam_obj.address).split("/")[0]
            matches = list(Prefix.objects.filter(prefix__net_contains=ip_str))
            matches.sort(key=lambda prefix: prefix.prefix.prefixlen, reverse=True)
            return matches[0] if matches else None
    except Exception:
        pass

    if obj_by_key:
        key = _ipa_object_tree_node_key(node)
        if key:
            obj = obj_by_key.get(key)
            if obj is not None:
                prefix = _ipa_prefix_for_cell_object(obj)
                if prefix is not None:
                    return prefix

    cidr = node.get("prefix_display_cidr") or ip_ref.get("str")
    if not cidr:
        return None
    try:
        import ipaddress

        from ipam.models import Prefix

        net = ipaddress.ip_network(str(cidr).strip(), strict=False)
        host = str(net.network_address)
        matches = list(Prefix.objects.filter(prefix__net_contains=host))
        matches.sort(key=lambda prefix: prefix.prefix.prefixlen, reverse=True)
        return matches[0] if matches else None
    except Exception:
        return None


def _lookup_containing_prefix_for_ipa_cell_node(
    node, obj_by_key=None, *, prefix_cache=None
):
    """Most specific NetBox Prefix containing a cell-tree host/prefix node."""
    if prefix_cache is not None:
        return prefix_cache.resolve(node, obj_by_key)
    return _lookup_containing_prefix_for_ipa_cell_node_impl(node, obj_by_key)


def _build_ipa_synthesized_parent_prefix_node(prefix):
    """Structural IPAM ancestor row (``ipam_synthetic``: grey CIDR, not in cell)."""
    node = {
        "kind": "group",
        "name": str(prefix),
        "url": prefix.get_absolute_url(),
        "ipam_synthetic": True,
        "is_ipam_synthesized": True,
        "children": [],
    }
    _enrich_ipa_node_from_resolved_prefix(node, prefix)
    if not node.get("prefix_display_cidr"):
        try:
            node["prefix_display_cidr"] = str(prefix.prefix)
        except Exception:
            node["prefix_display_cidr"] = str(prefix)
    sync_prefix_display_netmask(node)
    hints = _ipa_object_node_presentation(
        IPA_NODE_ROLE_PREFIX, has_member_children=True
    )
    node["node_role"] = hints["node_role"]
    node["kind"] = hints["kind"]
    return node


def _synthesize_ipa_cell_ipam_parent_prefixes(nodes, obj_by_key, *, prefix_cache=None):
    """
    Insert missing IPAM parent prefix rows when hosts are in the cell but the
    containing prefix object is not (NetBox IPAM hierarchy parent synthesis).
    """
    if not nodes:
        return nodes

    for node in nodes:
        children = node.get("children") or []
        if children:
            node["children"] = _synthesize_ipa_cell_ipam_parent_prefixes(
                children, obj_by_key, prefix_cache=prefix_cache
            )

    assigned: set[int] = set()
    prefix_nodes: dict[str, dict] = {}
    existing_by_net: dict[tuple, dict] = {}
    for node in nodes:
        net_key = _ipa_object_tree_network_key(node)
        if net_key is not None:
            existing_by_net[net_key] = node

    for node in nodes:
        if node.get("children"):
            continue
        role = _ipa_object_node_role_from_tree_node(node)
        if role not in (IPA_NODE_ROLE_HOST, IPA_NODE_ROLE_GROUP):
            continue
        if role == IPA_NODE_ROLE_GROUP and not node.get("is_cell_direct"):
            continue
        net = _ipa_object_tree_containment_network(node)
        if net is None:
            continue

        prefix = _lookup_containing_prefix_for_ipa_cell_node(
            node, obj_by_key, prefix_cache=prefix_cache
        )
        if prefix is None:
            continue
        try:
            prefix_net_key = (
                prefix.prefix.version,
                int(prefix.prefix.network_address),
                prefix.prefix.prefixlen,
            )
        except Exception:
            continue
        if prefix_net_key == _ipa_object_tree_network_key(node):
            continue

        parent_node = existing_by_net.get(prefix_net_key)
        if parent_node is None:
            prefix_key = str(prefix.prefix).strip().lower()
            parent_node = prefix_nodes.get(prefix_key)
            if parent_node is None:
                parent_node = _build_ipa_synthesized_parent_prefix_node(prefix)
                parent_node["is_ipam_synthesized"] = True
                prefix_nodes[prefix_key] = parent_node
        parent_node.setdefault("children", []).append(node)
        parent_node["kind"] = "group"
        assigned.add(id(node))

    forest = [node for node in nodes if id(node) not in assigned]
    for parent in prefix_nodes.values():
        if parent.get("children"):
            forest.append(parent)

    if not assigned:
        return nodes

    forest = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(forest, obj_by_key)
    return _sort_ipa_object_tree_siblings(forest)


def _sync_ipa_cell_tree_node_flags(nodes):
    """
    Canonical IPA cell-tree presentation flags (also keep legacy aliases).

    - ``in_cell`` / ``is_cell_direct`` / ``ipa_tree_node_type=cell_selected``
    - ``ipam_synthetic`` / ``is_ipam_synthesized`` / ``is_ipam_filler``
    - ``info_summary`` / ``ipa_tree_node_type=info_gap``
    """
    for node in nodes or []:
        node_type = node.get("ipa_tree_node_type")

        if (
            node_type == IPA_TREE_NODE_CELL_SELECTED
            or node.get("is_cell_direct")
            or node.get("in_cell")
        ):
            node["in_cell"] = True
            node["is_cell_direct"] = True
        elif not _ipa_tree_node_is_structural(node):
            node.pop("in_cell", None)
            node.pop("is_cell_direct", None)

        if (
            node_type == IPA_TREE_NODE_IPAM_FILLER
            or node.get("is_ipam_filler")
            or node.get("is_ipam_synthesized")
            or node.get("ipam_synthetic")
        ):
            node["ipam_synthetic"] = True
            node["is_ipam_synthesized"] = True
            node["is_ipam_filler"] = True
            node.pop("is_ipam_parent_prefix", None)
            node.pop("in_cell", None)
            node.pop("is_cell_direct", None)
        elif node_type != IPA_TREE_NODE_IPAM_FILLER:
            node.pop("ipam_synthetic", None)
            node.pop("is_ipam_synthesized", None)

        if _is_ipa_info_gap_node(node):
            display = _ipa_info_gap_display_label(node)
            if display:
                node["info_summary"] = True
                node["ipa_tree_node_type"] = IPA_TREE_NODE_INFO_GAP
                node["kind"] = "ipa_info_gap"
                node["ipa_gap_display_label"] = display
            else:
                _scrub_stale_ipa_info_gap_node(node)

        _sync_ipa_cell_tree_node_flags(node.get("children") or [])


def _mark_ipa_cell_pill_roles(nodes):
    """
    Tag NSM address-group rows so the cell pill renders ``ADDRESS_GROUP`` (not ``ADDRESS``).

    The cell row template (``ipa_cell_object_row_labels.html``) renders an ``ADDRESS``
    pill by default. A node whose own object is an NSM address group — e.g. a collapsed
    ``bench-grp-*`` selection row or an empty group — must instead expose an
    ``ADDRESS_GROUP`` pill. Structural rows (IPAM filler, synthetic parents, info gaps)
    are never NSM objects and keep their grey CIDR rendering.
    """
    for node in nodes or []:
        if _ipa_tree_node_is_structural(node):
            node.pop("cell_pill_group", None)
        elif _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP:
            node["cell_pill_group"] = True
        else:
            node.pop("cell_pill_group", None)
        _mark_ipa_cell_pill_roles(node.get("children") or [])


def _mark_ipa_ipam_parent_prefix_flags(nodes):
    """Mark in-cell prefix rows that contain nested addresses (bright expandable group)."""
    for node in nodes or []:
        children = node.get("children") or []
        if children:
            _mark_ipa_ipam_parent_prefix_flags(children)
        if node.get("ipam_synthetic") or node.get("is_ipam_synthesized"):
            continue
        role = _ipa_object_node_role_from_tree_node(node)
        in_cell = node.get("in_cell") or node.get("is_cell_direct")
        if role == IPA_NODE_ROLE_PREFIX and children and in_cell:
            node["is_ipam_parent_prefix"] = True
            node["kind"] = "group"


def _ipa_prefix_for_cell_object(obj):
    """Return the NetBox IPAM Prefix associated with a rules-cell object, if any."""
    from ipam.models import Prefix

    try:
        if isinstance(obj, Prefix):
            return obj
        related = _hub._ipam_fk_object_for_addr_node(obj)
        if isinstance(related, Prefix):
            return related
    except Exception:
        pass

    cidr = _ipa_cidr_from_object_name(getattr(obj, "name", None))
    if not cidr:
        return None
    try:
        return Prefix.objects.filter(prefix=cidr).order_by("pk").first()
    except Exception:
        return None


def _enrich_ipa_node_from_resolved_prefix(node, prefix):
    """Attach ``ip_ref``/CIDR display when a prefix was inferred outside ``ip_ref``."""
    if not prefix or node.get("ip_ref"):
        return node
    try:
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(prefix)
        ip_ref = {
            "str": str(getattr(prefix, "prefix", None) or prefix),
            "url": prefix.get_absolute_url(),
            "type": _FIELD_TYPE_LABELS["prefix"],
            "ct": ct.pk,
            "pk": prefix.pk,
        }
        node["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
        _hub._attach_addr_node_prefix_display(node, ip_ref=ip_ref)
    except Exception:
        pass
    return node


def _ipa_deepest_cell_ancestor_node(prefix, prefix_pk_to_node):
    """Return the deepest cell node whose prefix is an IPAM parent of *prefix*."""
    if not prefix or not prefix_pk_to_node:
        return None
    try:
        parents = list(prefix.get_parents())
    except Exception:
        return None
    if not parents:
        return None
    best = None
    best_prefixlen = -1
    for ancestor in parents:
        ancestor_node = prefix_pk_to_node.get(ancestor.pk)
        if ancestor_node is None:
            continue
        try:
            prefixlen = ancestor.prefix.prefixlen
        except Exception:
            continue
        if prefixlen > best_prefixlen:
            best = ancestor_node
            best_prefixlen = prefixlen
    return best


def _ipa_find_deepest_containing_node(nodes, net):
    """Return the deepest node in *nodes* whose network strictly contains *net*."""
    best = None
    best_prefixlen = -1
    for node in nodes or []:
        parent_net = _ipa_object_tree_containment_network(node)
        if not parent_net or not net.subnet_of(parent_net) or net == parent_net:
            continue
        deeper = _ipa_find_deepest_containing_node(node.get("children") or [], net)
        if deeper:
            return deeper
        if parent_net.prefixlen > best_prefixlen:
            best = node
            best_prefixlen = parent_net.prefixlen
    return best


def _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(nodes, obj_by_key):
    """
    Nest sibling nodes using NetBox IPAM Prefix parent chains among cell objects.
    Falls back to pure CIDR containment when no IPAM parent match exists.
    """
    if not nodes:
        return nodes

    for node in nodes:
        children = node.get("children") or []
        if children:
            node["children"] = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(
                children, obj_by_key
            )

    if len(nodes) < 2:
        return nodes

    prefix_pk_to_node = {}
    node_prefix = {}

    for node in nodes:
        key = _ipa_object_tree_node_key(node)
        if not key:
            continue
        obj = obj_by_key.get(key)
        if obj is None:
            continue
        prefix = _ipa_prefix_for_cell_object(obj)
        if prefix is None:
            continue
        _enrich_ipa_node_from_resolved_prefix(node, prefix)
        node_prefix[id(node)] = prefix
        prefix_pk_to_node.setdefault(prefix.pk, node)

    sorted_nodes = sorted(nodes, key=_ipa_object_tree_sort_key)
    parent_for: dict[int, dict] = {}

    for node in sorted_nodes:
        net = _ipa_object_tree_containment_network(node)
        parent = _ipa_deepest_cell_ancestor_node(
            node_prefix.get(id(node)), prefix_pk_to_node
        )
        if parent is None and net is not None:
            best = None
            best_prefixlen = -1
            node_role = _ipa_object_node_role_from_tree_node(node)
            for candidate in sorted_nodes:
                if candidate is node:
                    continue
                cand_net = _ipa_object_tree_containment_network(candidate)
                if cand_net is None:
                    continue
                cand_role = _ipa_object_node_role_from_tree_node(candidate)
                if (
                    net.subnet_of(cand_net)
                    and net != cand_net
                    and cand_net.prefixlen > best_prefixlen
                ):
                    best = candidate
                    best_prefixlen = cand_net.prefixlen
                elif (
                    net == cand_net
                    and node_role == IPA_NODE_ROLE_GROUP
                    and cand_role != IPA_NODE_ROLE_GROUP
                    and cand_net.prefixlen > best_prefixlen
                ):
                    best = candidate
                    best_prefixlen = cand_net.prefixlen
            parent = best
        if parent is not None:
            parent_for[id(node)] = parent

    forest = []
    for node in sorted_nodes:
        parent = parent_for.get(id(node))
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["kind"] = "group"
        else:
            forest.append(node)

    for node in sorted_nodes:
        children = node.get("children") or []
        if children:
            node["children"] = sorted(children, key=_ipa_object_tree_sort_key)
    return sorted(forest, key=_ipa_object_tree_sort_key)


def _renest_ipa_contained_cell_siblings(nodes):
    """
    Final containment guard: never leave an inventory row beside a sibling whose
    network strictly contains it.

    Depth bullets in the flat cell tree come from structural nesting
    (``ipa_object_tree_node.html`` increments ``depth`` for every non-filler
    level). A host or prefix that lingers *next to* — instead of *inside* — its
    containing prefix therefore renders with fewer depth markers than its true
    siblings (e.g. ``10.128.1.1/32`` showing ``••`` while ``10.128.1.2/32``
    shows ``•••``). Re-home such rows under the deepest containing sibling so a
    child's depth is always its parent's depth + 1.

    Nodes are only moved *deeper* (into a strictly containing sibling), never
    up, so already-correct trees are left untouched (idempotent).
    """
    if not nodes:
        return nodes

    for node in nodes:
        children = node.get("children")
        if children:
            node["children"] = _renest_ipa_contained_cell_siblings(children)

    if len(nodes) < 2:
        return nodes

    movable_roles = (IPA_NODE_ROLE_HOST, IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE)
    container_roles = (IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE)

    containers = []
    for node in nodes:
        if _ipa_tree_node_is_structural(node):
            continue
        if _ipa_object_node_role_from_tree_node(node) not in container_roles:
            continue
        net = _ipa_object_tree_containment_network(node)
        if net is not None:
            containers.append((node, net))
    if not containers:
        return nodes

    remaining = []
    for node in nodes:
        if _ipa_tree_node_is_structural(node):
            remaining.append(node)
            continue
        if _ipa_object_node_role_from_tree_node(node) not in movable_roles:
            remaining.append(node)
            continue
        net = _ipa_object_tree_containment_network(node)
        parent = None
        best_prefixlen = -1
        if net is not None:
            for cand, cand_net in containers:
                if cand is node:
                    continue
                if (
                    net.version == cand_net.version
                    and net != cand_net
                    and cand_net.prefixlen > best_prefixlen
                    and net.subnet_of(cand_net)
                ):
                    parent = cand
                    best_prefixlen = cand_net.prefixlen
        if parent is None:
            remaining.append(node)
            continue
        parent.setdefault("children", []).append(node)
        parent["kind"] = "group"

    return _sort_ipa_object_tree_siblings(remaining)


def _ipa_object_tree_containment_cidr(node):
    """Resolved CIDR string for containment warnings."""
    return (
        node.get("prefix_display_cidr")
        or (node.get("ip_ref") or {}).get("str")
        or ""
    )


def _ipa_subnet_containment_display_net(node):
    """Human-readable network label for subnet containment INFO pill."""
    net = _hub._addr_tree_node_network(node)
    if not net:
        return _ipa_object_tree_containment_cidr(node)
    if net.prefixlen == net.max_prefixlen:
        return str(net.network_address)
    return str(net)


def _iter_ipa_object_tree_nodes(nodes):
    for node in nodes or []:
        yield node
        yield from _iter_ipa_object_tree_nodes(node.get("children") or [])


def _iter_ipa_object_tree_nodes_with_ancestors(nodes, ancestors=None):
    if ancestors is None:
        ancestors = []
    for node in nodes or []:
        yield node, ancestors
        next_ancestors = ancestors
        if _hub._addr_tree_node_network(node) or _ipa_tree_node_is_ipam_prefix_container(
            node
        ):
            next_ancestors = ancestors + [node]
        yield from _iter_ipa_object_tree_nodes_with_ancestors(
            node.get("children") or [], next_ancestors
        )


def _ipa_node_has_containing_tree_ancestor(node, net, ancestors) -> bool:
    """True when a visible tree ancestor already structurally contains *net*."""
    for anc in ancestors or []:
        anc_net = _hub._addr_tree_node_network(anc)
        if _ipa_subnet_containment_ancestor_match(node, net, anc, anc_net):
            return True
    return False


def _ipa_tree_node_is_ipam_prefix_container(node):
    """True when a structural row still represents an IPAM prefix container."""
    if not node:
        return False
    if not _ipa_tree_node_is_structural(node):
        return True
    return bool(node.get("is_ipam_filler") or node.get("ipam_synthetic"))


def _ipa_nearest_prefix_tree_ancestor(ancestors):
    """Deepest tree ancestor that carries a parent prefix (for Parent column hints)."""
    for anc in reversed(ancestors or []):
        if not _ipa_tree_node_is_ipam_prefix_container(anc):
            continue
        net = _hub._addr_tree_node_network(anc)
        if net is None or net.prefixlen >= 31:
            continue
        return anc
    return None


def _ipa_object_tree_prefix_container_nodes(nodes):
    """Tree nodes that can act as a parent prefix for subnet containment warnings."""
    containers = []
    for node in _iter_ipa_object_tree_nodes(nodes):
        if _ipa_tree_node_is_structural(node) and not _ipa_tree_node_is_ipam_prefix_container(
            node
        ):
            continue
        net = _hub._addr_tree_node_network(node)
        if net is None or net.prefixlen >= 31:
            continue
        containers.append(node)
    return containers


def _mark_ipa_cell_tree_parent_hints(nodes, ancestors=None):
    """
    Attach ``ipa_tree_parent_*`` when the row has a prefix ancestor in the cell tree
    but no ``subnet_contained_in`` duplicate marker (e.g. IPAM-synthesized parents).
    """
    if ancestors is None:
        ancestors = []

    for node in nodes or []:
        if not node.get("subnet_contained_in"):
            parent = _ipa_nearest_prefix_tree_ancestor(ancestors)
            if parent is not None:
                node["ipa_tree_parent_cidr"] = _ipa_object_tree_containment_cidr(parent)
                node["ipa_tree_parent_name"] = parent.get("name") or ""
                node["ipa_tree_parent_url"] = parent.get("url") or ""

        next_ancestors = ancestors
        if _hub._addr_tree_node_network(node) or _ipa_tree_node_is_ipam_prefix_container(
            node
        ):
            next_ancestors = ancestors + [node]
        _mark_ipa_cell_tree_parent_hints(node.get("children") or [], next_ancestors)


def _ipa_subnet_containment_ancestor_match(node, net, anc, anc_net):
    """True when *net* is redundant under prefix ancestor *anc* in the cell tree."""
    if not net or not anc_net:
        return False
    if net.subnet_of(anc_net) and net != anc_net:
        return True
    return (
        net == anc_net
        and _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP
        and _ipa_object_node_role_from_tree_node(anc) != IPA_NODE_ROLE_GROUP
    )


def _mark_ipa_subnet_containment_warnings(nodes, ancestors=None):
    """
    Flag nodes whose resolved prefix is contained in an ancestor supernet.
    ``subnet_contained_in`` stores the root-most enclosing ancestor CIDR.
    """
    if ancestors is None:
        ancestors = []

    for node in nodes or []:
        net = _hub._addr_tree_node_network(node)
        if net and ancestors:
            for anc in ancestors:
                anc_net = _hub._addr_tree_node_network(anc)
                if _ipa_subnet_containment_ancestor_match(node, net, anc, anc_net):
                    node["subnet_contained_in"] = _ipa_object_tree_containment_cidr(anc)
                    node["subnet_contained_in_name"] = anc.get("name") or ""
                    node["subnet_contained_in_url"] = anc.get("url") or ""
                    node["subnet_containment_display_net"] = (
                        _ipa_subnet_containment_display_net(node)
                    )
                    break

        next_ancestors = ancestors
        if _hub._addr_tree_node_network(node) or _ipa_tree_node_is_ipam_prefix_container(
            node
        ):
            next_ancestors = ancestors + [node]
        _mark_ipa_subnet_containment_warnings(
            node.get("children") or [], next_ancestors
        )


def _mark_ipa_subnet_containment_peer_fallback(nodes):
    """
    Fill ``subnet_contained_in`` when the hierarchy walk missed a containing prefix.

    Flat cell trees (bench overlap rules) can expose hosts and their /24 prefixes as
    root siblings; the ancestor walk only sees nested children. Pick the root-most
    (widest) containing prefix already present in the tree.
    """
    containers = _ipa_object_tree_prefix_container_nodes(nodes)
    if not containers:
        return

    for node, ancestors in _iter_ipa_object_tree_nodes_with_ancestors(nodes):
        if node.get("subnet_contained_in") or _ipa_tree_node_is_structural(node):
            continue
        net = _hub._addr_tree_node_network(node)
        if net is None:
            continue
        if _ipa_node_has_containing_tree_ancestor(node, net, ancestors):
            continue

        best = None
        best_prefixlen = 999
        for container in containers:
            if container is node:
                continue
            container_net = _hub._addr_tree_node_network(container)
            if container_net is None:
                continue
            contained = net.subnet_of(container_net) and net != container_net
            same_cidr_group = (
                net == container_net
                and _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP
                and _ipa_object_node_role_from_tree_node(container)
                != IPA_NODE_ROLE_GROUP
            )
            if (
                (contained or same_cidr_group)
                and container_net.prefixlen < best_prefixlen
            ):
                best = container
                best_prefixlen = container_net.prefixlen

        if best is None:
            continue
        node["subnet_contained_in"] = _ipa_object_tree_containment_cidr(best)
        node["subnet_contained_in_name"] = best.get("name") or ""
        node["subnet_contained_in_url"] = best.get("url") or ""
        node["subnet_containment_display_net"] = _ipa_subnet_containment_display_net(
            node
        )


def _mark_ipa_object_tree_duplicate_flags(
    nodes, *, is_root=False, seen=None, first_names=None, first_urls=None
):
    """
    Mark nodes whose object identity already appeared elsewhere in the tree.
    Root-level ``is_doppelt`` entries keep only the red marker (no duplicate badge).
    """
    if seen is None:
        seen = {}
        first_names = {}
        first_urls = {}

    for node in nodes or []:
        if _ipa_tree_node_is_structural(node):
            _mark_ipa_object_tree_duplicate_flags(
                node.get("children") or [],
                is_root=False,
                seen=seen,
                first_names=first_names,
                first_urls=first_urls,
            )
            continue
        try:
            key = (int(node.get("ct") or 0), int(node.get("pk") or 0))
        except (TypeError, ValueError):
            key = None

        if key and key != (0, 0) and key in seen:
            if not (is_root and node.get("is_doppelt")):
                node["object_duplicate"] = True
                node["object_duplicate_of"] = first_names.get(key, "")
                node["object_duplicate_of_url"] = first_urls.get(key, "")
        elif key and key != (0, 0):
            seen[key] = True
            first_names[key] = node.get("name") or ""
            first_urls[key] = node.get("url") or ""

        _mark_ipa_object_tree_duplicate_flags(
            node.get("children") or [],
            is_root=False,
            seen=seen,
            first_names=first_names,
            first_urls=first_urls,
        )


def _collect_ipa_tree_network_keys(nodes):
    """Collect all non-structural network keys in a subtree."""
    keys = set()
    for node in nodes or []:
        if not _ipa_tree_node_is_structural(node):
            net_key = _ipa_object_tree_network_key(node)
            if net_key is not None:
                keys.add(net_key)
        keys.update(_collect_ipa_tree_network_keys(node.get("children") or []))
    return keys


def _prune_ipa_object_tree_duplicate_nodes(nodes, *, ancestor_nets=None):
    """Remove repeated object identities and networks; one row per network."""
    if ancestor_nets is None:
        ancestor_nets = set()
    pruned = []
    seen_nets: set[tuple] = set(ancestor_nets)
    nested_nets = set()
    for node in nodes or []:
        nested_nets.update(_collect_ipa_tree_network_keys(node.get("children") or []))
    for node in nodes or []:
        if node.get("object_duplicate"):
            continue
        if _ipa_tree_node_is_structural(node):
            children = node.get("children")
            if children:
                node["children"] = _prune_ipa_object_tree_duplicate_nodes(
                    children, ancestor_nets=ancestor_nets
                )
            pruned.append(node)
            continue
        net_key = _ipa_object_tree_network_key(node)
        if net_key is not None:
            if net_key in seen_nets:
                continue
            if (
                not (node.get("children") or [])
                and net_key in nested_nets
                and not ancestor_nets
            ):
                continue
            seen_nets.add(net_key)
        children = node.get("children")
        if children:
            node["children"] = _prune_ipa_object_tree_duplicate_nodes(
                children, ancestor_nets=seen_nets
            )
            seen_nets.update(_collect_ipa_tree_network_keys(node["children"]))
        pruned.append(node)
    return pruned


def _ipa_cell_object_tree_visible(nodes, raw_count, *, prefer_logical_merge=False):
    """
    Whether to render the cell object tree (NSM layer + lazy IPAM drilldown).

    Always prefer the object tree when nodes were built: users expand prefixes via
    ``addr_drilldown_lazy`` and need ``ipam_stats`` on NSM objects. The merged
    addr_analyzer tree remains available for counts/CSV fallback only.
    """
    del prefer_logical_merge, raw_count  # kept for stable call/patch signatures
    return bool(nodes)


def _mark_ipa_cell_direct_flags(nodes, cell_object_keys, *, is_root=True):
    """
    Mark explicit cell selections as ``cell_selected`` (bright row) at any depth.

    ``ipam_filler`` and ``info_gap`` rows are never cell-direct.
    """
    del is_root  # kept for stable call/patch signatures
    for node in nodes or []:
        if _ipa_tree_node_is_structural(node):
            node.pop("is_cell_direct", None)
        else:
            key = _ipa_object_tree_node_key(node)
            if key and key in cell_object_keys:
                node["is_cell_direct"] = True
                node["in_cell"] = True
                node["ipa_tree_node_type"] = IPA_TREE_NODE_CELL_SELECTED
            else:
                node.pop("is_cell_direct", None)
                node.pop("in_cell", None)
                if node.get("ipa_tree_node_type") == IPA_TREE_NODE_CELL_SELECTED:
                    node.pop("ipa_tree_node_type", None)
        _mark_ipa_cell_direct_flags(node.get("children") or [], cell_object_keys)


def _ipa_node_renders_as_details(node):
    """True when ``addr_tree_node.html`` renders this node as ``<details>`` (IPA context)."""
    if node.get("kind") == "info_summary":
        return False
    in_cell = node.get("in_cell") or node.get("is_cell_direct")
    ipam_synthetic = node.get("ipam_synthetic") or node.get("is_ipam_synthesized")
    if node.get("kind") == "group" or ipam_synthetic:
        return bool(
            node.get("children")
            or node.get("ipam_stats")
            or node.get("addr_drilldown_lazy")
            or in_cell
            or ipam_synthetic
        )
    return bool(node.get("ct") and node.get("addr_drilldown_lazy")) or bool(
        in_cell and node.get("ipa_drilldown_meta")
    )


def _attach_ipa_cell_group_collapse_hints(nodes):
    """Collapse large membership group lists into an expandable summary (display only)."""
    for node in nodes or []:
        if node.get("ipa_tree_node_type") == IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS:
            # Root wrapper uses ``collapsed_group_count`` for child group rows; do
            # not clear it when this synthetic node has no ``cell_groups``.
            _attach_ipa_cell_group_collapse_hints(node.get("children") or [])
            continue
        display = _display_cell_group_refs(node.get("cell_groups"))
        count = len(display)
        if count >= IPA_CELL_GROUPS_COLLAPSE_THRESHOLD:
            node["cell_groups_collapsed"] = True
            node["collapsed_group_count"] = count
        else:
            node.pop("cell_groups_collapsed", None)
            node.pop("collapsed_group_count", None)
        _attach_ipa_cell_group_collapse_hints(node.get("children") or [])


def _pick_cell_address_primary(node, addrs):
    """Prefer the cell-direct name; otherwise keep stable list order."""
    node_name = str(node.get("name") or "").strip()
    for ref in addrs:
        if str(ref.get("name") or "").strip() == node_name:
            return ref
    if node.get("is_cell_direct"):
        for ref in addrs:
            if ref.get("url") == node.get("url"):
                return ref
    return addrs[0]


def _attach_ipa_cell_address_compact_hints(nodes):
    """Compact alias/dup peers into secondary hints instead of stacked orange pills."""
    for node in nodes or []:
        addrs = list(node.get("cell_addresses") or [])
        if node.get("cell_addresses_multi") and len(addrs) > 1:
            primary = _pick_cell_address_primary(node, addrs)
            alternates = [
                ref
                for ref in addrs
                if (ref.get("name"), ref.get("url"))
                != (primary.get("name"), primary.get("url"))
            ]
            node["cell_address_primary"] = primary
            node["cell_address_alternates"] = alternates
            node["cell_addresses_compact"] = True
            node["collapsed_address_alt_count"] = len(alternates)
        else:
            node.pop("cell_address_primary", None)
            node.pop("cell_address_alternates", None)
            node.pop("cell_addresses_compact", None)
            node.pop("collapsed_address_alt_count", None)

        _attach_ipa_cell_address_compact_hints(node.get("children") or [])


def _is_collapsed_root_group_selection(node):
    """True for a collapsed bench-scale address-group row at tree root."""
    if not node or node.get("children"):
        return False
    return bool(
        node.get("cell_pill_group")
        and node.get("is_cell_direct")
        and _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP
    )


def _annotate_ipa_cell_tree_depth(nodes, depth=0):
    """Attach ``ipa_depth`` on each node for flat table rendering."""
    for node in nodes or []:
        node["ipa_depth"] = depth
        child_depth = depth if _is_ipa_ipam_filler_node(node) else depth + 1
        _annotate_ipa_cell_tree_depth(node.get("children") or [], child_depth)


def _wrap_collapsed_root_group_nodes(nodes):
    """Fold many root-level collapsed group rows into one expandable summary."""
    if len(nodes or []) < IPA_CELL_ROOT_GROUPS_COLLAPSE_THRESHOLD:
        return nodes
    group_nodes = [n for n in nodes if _is_collapsed_root_group_selection(n)]
    if len(group_nodes) < IPA_CELL_ROOT_GROUPS_COLLAPSE_THRESHOLD:
        return nodes
    other_nodes = [n for n in nodes if not _is_collapsed_root_group_selection(n)]
    count = len(group_nodes)
    wrapper = {
        "kind": "group",
        "name": "",
        "url": "#",
        "ipa_tree_node_type": IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS,
        "collapsed_group_count": count,
        "children": group_nodes,
        "ipa_open_by_default": False,
    }
    return other_nodes + [wrapper]


def _attach_ipa_cell_display_hints(nodes):
    """Attach presentation-only hints consumed by IPA cell templates/CSS."""
    _attach_ipa_cell_group_collapse_hints(nodes)
    _attach_ipa_cell_address_compact_hints(nodes)


def _mark_ipa_cell_open_by_default(nodes):
    """Mark IPA ``<details>`` nodes that should render open for cell-direct visibility."""
    for node in nodes or []:
        children = node.get("children") or []
        if node.get("ipa_tree_node_type") == IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS:
            node.pop("ipa_open_by_default", None)
            _mark_ipa_cell_open_by_default(children)
            continue
        _mark_ipa_cell_open_by_default(children)
        child_exposes_cell_direct = any(
            c.get("in_cell")
            or c.get("is_cell_direct")
            or c.get("ipa_open_by_default")
            for c in children
        )
        in_cell = node.get("in_cell") or node.get("is_cell_direct")
        if _ipa_node_renders_as_details(node) and (
            in_cell or child_exposes_cell_direct
        ):
            if (
                node.get("node_role") == IPA_NODE_ROLE_GROUP
                and not children
                and not node.get("addr_drilldown_lazy")
            ):
                node.pop("ipa_open_by_default", None)
            else:
                node["ipa_open_by_default"] = True
        else:
            node.pop("ipa_open_by_default", None)


def _collect_ipa_tree_member_obj_by_key(obj_by_key):
    """Extend cell object lookup with every address/group member in the tree."""
    from django.contrib.contenttypes.models import ContentType

    merged = dict(obj_by_key or {})
    seen = set(merged.keys())
    stack = list(merged.values())
    while stack:
        obj = stack.pop()
        if not _ipa_object_expands_members(obj):
            continue
        for member in _ipa_object_group_members(obj):
            try:
                ct = ContentType.objects.get_for_model(member)
                key = (ct.pk, member.pk)
            except Exception:
                continue
            if key in seen:
                continue
            seen.add(key)
            merged[key] = member
            stack.append(member)
    return merged


def _ipa_cell_tree_node_inventory_class(node):
    """Classify a cell-tree row for summary badges (``ip`` / ``subnet`` / ``range``)."""
    net_key = _ipa_cell_tree_summary_network_key(node)
    if net_key is None:
        return None
    prefixlen = net_key[2]
    if prefixlen >= 31:
        return "ip"
    ip_ref = node.get("ip_ref") or {}
    ref_type = str(ip_ref.get("type") or "")
    if "Range" in ref_type or "range" in ref_type.casefold():
        return "range"
    return "subnet"


def _ipa_ipam_model_name(obj):
    """Return the NetBox IPAM model name for resolved IPAM objects."""
    try:
        meta = obj._meta
        if getattr(meta, "app_label", "") == "ipam":
            return str(getattr(meta, "model_name", "") or "")
    except Exception:
        return ""
    return ""


def _ipa_nsm_object_description(nsm_obj):
    """Return a stripped NSM policy-object description when present."""
    if nsm_obj is None:
        return ""
    return str(getattr(nsm_obj, "description", "") or "").strip()


def _ipa_ipam_object_display_ref(ipam_obj, nsm_obj=None):
    """Build IPAM metadata for the cell-tree DNS/description column."""
    model_name = _ipa_ipam_model_name(ipam_obj)
    if model_name == "prefix":
        kind = "prefix"
    elif model_name == "ipaddress":
        kind = "ipaddress"
    elif model_name == "iprange":
        kind = "iprange"
    else:
        return None

    description = str(getattr(ipam_obj, "description", "") or "").strip()
    if not description:
        description = _ipa_nsm_object_description(nsm_obj)
    dns_name = ""
    if kind == "ipaddress":
        dns_name = str(getattr(ipam_obj, "dns_name", "") or "").strip()

    if kind == "ipaddress":
        if not dns_name and not description:
            return None
    elif not description:
        return None

    url = None
    if hasattr(ipam_obj, "get_absolute_url"):
        try:
            url = ipam_obj.get_absolute_url()
        except Exception:
            url = None
    return {
        "kind": kind,
        "description": description,
        "dns_name": dns_name,
        "url": url,
    }


def _attach_ipa_cell_ipam_object_refs(nodes, obj_by_key=None):
    """Attach resolved IPAM DNS/description metadata for the flat cell-tree."""
    for node in nodes or []:
        if node.get("layer") == "ipam_prefix":
            _attach_ipa_cell_ipam_object_refs(node.get("children") or [], obj_by_key)
            continue
        if _ipa_tree_node_is_structural(node):
            _attach_ipa_cell_ipam_object_refs(node.get("children") or [], obj_by_key)
            continue

        key = _ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        ipam_obj = _ipa_cell_tree_ipam_object_for_node(node, obj=obj)
        if ipam_obj is not None:
            ipam_ref = _ipa_ipam_object_display_ref(ipam_obj, nsm_obj=obj)
            if ipam_ref is not None:
                node["ipam_object_ref"] = ipam_ref

        try:
            _hub._attach_addr_navigation_refs(node, obj=obj, ipam_obj=ipam_obj)
        except Exception:
            pass
        _attach_ipa_cell_ipam_object_refs(node.get("children") or [], obj_by_key)


def _ipa_is_django_queryset(obj) -> bool:
    try:
        from django.db.models.query import QuerySet

        return isinstance(obj, QuerySet)
    except Exception:
        return False


def _ipa_queryset_count_safe(queryset) -> int | None:
    """Return queryset ``count()`` when cheap, else ``None``."""
    if not _ipa_is_django_queryset(queryset):
        return None
    try:
        return int(queryset.count())
    except Exception:
        pass
    return None


def _ipa_queryset_pk_set(queryset, *, max_rows=None):
    """Resolve primary keys from a QuerySet/list without assuming a concrete ORM type."""
    try:
        if max_rows is not None and _ipa_is_django_queryset(queryset):
            total = _ipa_queryset_count_safe(queryset)
            if total is not None and total > max_rows:
                return set()
        if hasattr(queryset, "values_list"):
            qs = queryset
            if max_rows is not None:
                qs = queryset[:max_rows]
            return set(qs.values_list("pk", flat=True))
        items = queryset
        if max_rows is not None:
            items = list(queryset)[:max_rows]
        return {
            getattr(item, "pk")
            for item in items
            if type(getattr(item, "pk", None)) is int
        }
    except Exception:
        return set()


def _ipa_lookup_ipam_ipaddress_from_ref(ip_ref):
    """Resolve a host ``IPAddress`` from an analyzer ref when ct/pk is missing."""
    cidr = str((ip_ref or {}).get("str") or "").strip()
    if not cidr:
        return None
    try:
        from ipam.models import IPAddress

        return IPAddress.objects.filter(address=cidr).order_by("pk").first()
    except Exception:
        return None


def _ipa_cell_tree_ipam_object_for_node(node, obj=None):
    """Resolve the IPAM object represented by one cell-tree row, if available."""
    ip_ref = node.get("ip_ref") or {}
    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
    if ipam_obj is not None:
        return ipam_obj

    if obj is not None:
        ipam_obj = _hub._ipam_fk_object_for_addr_node(obj)
        if ipam_obj is not None:
            return ipam_obj

    role = _ipa_object_node_role_from_tree_node(node)
    is_host = role == IPA_NODE_ROLE_HOST or ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]

    candidates = []
    for candidate in (
        ip_ref.get("str"),
        node.get("prefix_display_cidr"),
        _ipa_cidr_from_object_name(node.get("name")),
        _ipa_cidr_from_host_object_name(node.get("name")),
    ):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    if is_host:
        for cidr in candidates:
            ipam_obj = _ipa_lookup_ipam_ipaddress_from_ref({"str": cidr})
            if ipam_obj is not None:
                return ipam_obj

    for cidr in candidates:
        if role == IPA_NODE_ROLE_RANGE or ip_ref.get("type") == _FIELD_TYPE_LABELS["range"]:
            ipam_obj = _hub._lookup_ipam_range_from_ip_ref(
                {"str": cidr, "type": _FIELD_TYPE_LABELS["range"]}
            )
            if ipam_obj is not None:
                return ipam_obj
        if is_host:
            continue
        if role in (IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_GROUP) or "/" in str(cidr):
            ipam_obj = _hub._lookup_ipam_prefix_from_ip_ref(
                {"str": cidr, "type": _FIELD_TYPE_LABELS["prefix"]}
            )
            if ipam_obj is not None:
                return ipam_obj
    return None


def _ipa_ipam_ip_keys_for_object(ipam_obj):
    """Unique IPAM IPAddress keys represented by one Prefix/Range/IPAddress object."""
    if ipa_lazy_load_enabled():
        return set(), False
    model_name = _ipa_ipam_model_name(ipam_obj)
    if model_name == "ipaddress":
        pk = getattr(ipam_obj, "pk", None)
        return ({("ipam.ipaddress", pk)} if type(pk) is int else set()), True
    if model_name == "prefix":
        try:
            child_qs = ipam_obj.get_child_ips()
            child_count = _ipa_queryset_count_safe(child_qs)
            if child_count is None:
                try:
                    raw_count = child_qs.count()
                    child_count = int(raw_count)
                except Exception:
                    child_count = None
            if child_count is not None and child_count > IPA_IPAM_CHILD_IP_ENUM_MAX:
                return set(), False
            if child_count is None and not _ipa_is_django_queryset(child_qs):
                # Unknown-size non-queryset sources are treated as unresolved to
                # avoid expensive/incorrect full enumeration on large objects.
                return set(), False
            keys = _ipa_queryset_pk_set(
                child_qs, max_rows=IPA_IPAM_CHILD_IP_ENUM_MAX + 1
            )
            if len(keys) > IPA_IPAM_CHILD_IP_ENUM_MAX:
                return set(), False
            return keys, True
        except Exception:
            return set(), False
    if model_name == "iprange":
        try:
            from ipam.models import IPAddress

            child_qs = IPAddress.objects.filter(
                address__gte=ipam_obj.start_address,
                address__lte=ipam_obj.end_address,
            )
            child_count = _ipa_queryset_count_safe(child_qs)
            if child_count is None:
                try:
                    raw_count = child_qs.count()
                    child_count = int(raw_count)
                except Exception:
                    child_count = None
            if child_count is not None and child_count > IPA_IPAM_CHILD_IP_ENUM_MAX:
                return set(), False
            if child_count is None and not _ipa_is_django_queryset(child_qs):
                return set(), False
            keys = _ipa_queryset_pk_set(
                child_qs, max_rows=IPA_IPAM_CHILD_IP_ENUM_MAX + 1
            )
            if len(keys) > IPA_IPAM_CHILD_IP_ENUM_MAX:
                return set(), False
            return keys, True
        except Exception:
            return set(), False
    return set(), False


def _ipa_network_is_covered_by_any(net, ancestors):
    """True when a node's network is already covered by an IPAM-counted ancestor."""
    if net is None:
        return False
    for ancestor in ancestors or []:
        if net == ancestor or _ipa_net_subnet_of(net, ancestor):
            return True
    return False


def _ipa_cell_object_tree_type_counts(nodes):
    """
    Summary counts for the IPA cell object tree.

    Subnet/range counts use the visible networks represented by the cell tree.
    IP counts prefer distinct NetBox IPAM ``IPAddress`` objects represented by
    those Prefix/Range/IP rows, so overlapping groups do not inflate the badge.
    If no IPAM objects can be resolved (for example in pure fixture data), the
    IP badge falls back to the legacy visible host-row count.
    """
    subnet_keys: set[tuple] = set()
    range_keys: set[tuple] = set()
    visible_ip_keys: set[tuple] = set()
    ipam_ip_keys: set[tuple] = set()
    resolved_ipam_inventory = False

    def _walk(ns, ipam_counted_ancestors=None):
        nonlocal resolved_ipam_inventory
        if ipam_counted_ancestors is None:
            ipam_counted_ancestors = []
        for node in ns or []:
            if _ipa_tree_node_is_structural(node):
                _walk(node.get("children") or [], ipam_counted_ancestors)
                continue
            if node.get("count_duplicate"):
                _walk(node.get("children") or [], ipam_counted_ancestors)
                continue

            bucket = _ipa_cell_tree_node_inventory_class(node)

            net_key = _ipa_cell_tree_summary_network_key(node)
            if net_key is not None and bucket == "ip":
                visible_ip_keys.add(net_key)
            elif net_key is not None and bucket == "subnet":
                subnet_keys.add(net_key)
            elif net_key is not None and bucket == "range":
                range_keys.add(net_key)

            next_ipam_counted_ancestors = ipam_counted_ancestors
            net = _ipa_object_tree_containment_network(node)
            if not _ipa_network_is_covered_by_any(net, ipam_counted_ancestors):
                ipam_obj = _ipa_cell_tree_ipam_object_for_node(node)
                if ipam_obj is not None:
                    keys, resolved = _ipa_ipam_ip_keys_for_object(ipam_obj)
                    if resolved:
                        resolved_ipam_inventory = True
                        ipam_ip_keys.update(keys)
                        if net is not None and bucket in {"subnet", "range"}:
                            next_ipam_counted_ancestors = list(ipam_counted_ancestors)
                            next_ipam_counted_ancestors.append(net)
            _walk(node.get("children") or [], next_ipam_counted_ancestors)

    _walk(nodes)
    return {
        "count_subnets": len(subnet_keys),
        "count_ranges": len(range_keys),
        "count_ips": len(ipam_ip_keys) if resolved_ipam_inventory else len(visible_ip_keys),
    }


def _ipa_cell_tree_visible_nodes(nodes):
    """Yield nodes that render as rows in the flat cell-tree table."""
    for node in nodes or []:
        if _ipa_cell_tree_flat_row_is_visible(node):
            yield node
        yield from _ipa_cell_tree_visible_nodes(node.get("children") or [])


def _ipa_node_has_non_active_status(node):
    """True when a rendered row carries any reserved/deprecated marker."""
    if normalize_nsm_object_status(node.get("status")):
        return True
    if node.get("dup_cell_statuses"):
        return True
    refs = (
        list(node.get("cell_addresses") or [])
        + list(node.get("cell_groups") or [])
        + [
            node.get("cell_address_primary") or {},
            node.get("cell_group_anchor_address") or {},
        ]
    )
    for ref in refs:
        if ref.get("is_none"):
            continue
        if normalize_nsm_object_status(ref.get("status")):
            return True
    return False


def _ipa_cell_tree_extended_summary_counts(nodes, group_coverage=None):
    """Extra counters for the IPA summary bar (coverage/debug oriented)."""
    visible = list(_ipa_cell_tree_visible_nodes(nodes))
    address_keys = set()
    direct = indirect = non_active = 0
    for node in visible:
        if node.get("in_cell") or node.get("is_cell_direct"):
            direct += 1
        else:
            indirect += 1
        if _ipa_node_has_non_active_status(node):
            non_active += 1
        role = _ipa_object_node_role_from_tree_node(node)
        if role != IPA_NODE_ROLE_GROUP:
            key = _ipa_object_tree_node_key(node)
            if key and key != (0, 0):
                address_keys.add(key)
        for ref in node.get("cell_addresses") or []:
            try:
                address_keys.add((int(ref.get("ct")), int(ref.get("pk"))))
            except (TypeError, ValueError):
                pass

    coverage = group_coverage or {}
    coverage_summary = coverage.get("summary") or {}
    return {
        "count_groups": int(coverage_summary.get("total") or 0),
        "count_addresses": len(address_keys),
        "count_hidden_merged": int(coverage_summary.get("membership") or 0),
        "count_non_active": non_active,
        "count_direct": direct,
        "count_indirect": indirect,
    }


def _ipa_group_coverage_node_maps(nodes):
    """Collect visible group rows and membership refs from a rendered cell tree."""
    rows_by_key: dict[tuple[int, int], dict] = {}
    refs_by_name_url: set[tuple[str, str]] = set()
    for node in _ipa_cell_tree_visible_nodes(nodes):
        if _ipa_object_node_role_from_tree_node(node) == IPA_NODE_ROLE_GROUP:
            key = _ipa_object_tree_node_key(node)
            if key:
                rows_by_key[key] = node
        for ref in node.get("cell_groups") or []:
            if ref.get("is_none"):
                continue
            refs_by_name_url.add(
                (str(ref.get("name") or ""), str(ref.get("url") or ""))
            )
    return rows_by_key, refs_by_name_url


def _ipa_group_coverage_anchor_cidr(obj, row=None):
    """Return the network shown for a selected group, when resolvable."""
    if row:
        cidr = row.get("prefix_display_cidr") or (row.get("ip_ref") or {}).get("str")
        if cidr:
            return str(cidr)
    net = _ipa_resolve_group_containment_network_from_members(obj)
    return str(net) if net is not None else ""


def _build_ipa_group_coverage(raw_selections, obj_by_key, object_tree):
    """Explain where each directly selected address group went in the flat table."""
    rows_by_key, refs_by_name_url = _ipa_group_coverage_node_maps(object_tree)
    groups = []
    seen = set()
    for sel in raw_selections or []:
        try:
            key = (int(sel["ct"]), int(sel["pk"]))
        except (KeyError, TypeError, ValueError):
            continue
        if key in seen:
            continue
        obj = (obj_by_key or {}).get(key)
        if obj is None or not _ipa_object_expands_members(obj):
            continue
        seen.add(key)
        name = str(getattr(obj, "name", None) or sel.get("name") or obj)
        url = getattr(obj, "get_absolute_url", lambda: "")()
        row = rows_by_key.get(key)
        ref_key = (name, url)
        members = list(_ipa_object_group_members(obj))
        if row is not None:
            state = "visible"
            state_label = "visible row"
        elif ref_key in refs_by_name_url:
            state = "membership"
            state_label = "merged into member row"
        else:
            state = "missing"
            state_label = "not shown"
        status = get_nsm_object_status(obj)
        groups.append(
            {
                "name": name,
                "url": url,
                "state": state,
                "state_label": state_label,
                "member_count": len(members),
                "anchor_cidr": _ipa_group_coverage_anchor_cidr(obj, row),
                "status": status or "",
            }
        )

    summary = {
        "total": len(groups),
        "visible": sum(1 for item in groups if item["state"] == "visible"),
        "membership": sum(1 for item in groups if item["state"] == "membership"),
        "missing": sum(1 for item in groups if item["state"] == "missing"),
    }
    return {"summary": summary, "groups": groups}


def _format_ipa_explain_reasons(node):
    """Human-readable explanation for why a row appears in the cell tree."""
    reasons = []
    if node.get("in_cell") or node.get("is_cell_direct"):
        reasons.append("direct in rule cell")
    else:
        reasons.append("indirect via IPAM/group expansion")
    groups = _display_cell_group_refs(node.get("cell_groups"))
    if groups:
        reasons.append(
            "group member: " + ", ".join(str(g.get("name") or "") for g in groups)
        )
    if node.get("cell_addresses_multi"):
        reasons.append("alias/duplicate address names share this network")
    if node.get("subnet_contained_in"):
        reasons.append(f"contained by {node.get('subnet_contained_in')}")
    elif node.get("ipa_tree_parent_cidr"):
        reasons.append(f"IPAM parent {node.get('ipa_tree_parent_cidr')}")
    if node.get("diff_group"):
        reasons.append(f"diff group: {node.get('diff_group')}")
    if node.get("diff_status") and not node.get("diff_suppress_status"):
        reasons.append(f"diff status: {node.get('diff_status')}")
    if node.get("diff_present_labels"):
        reasons.append(
            "diff present in: "
            + ", ".join(str(label) for label in node.get("diff_present_labels") or [])
        )
    if node.get("dup_cell_statuses"):
        reasons.append("non-active: " + ", ".join(node["dup_cell_statuses"]))
    return reasons


def _attach_ipa_explain_fields(nodes):
    """Attach compact Explain tooltip fields consumed by the flat table."""
    for node in nodes or []:
        reasons = _format_ipa_explain_reasons(node)
        if reasons:
            node["ipa_explain_reasons"] = reasons
            node["ipa_explain_title"] = "Why: " + " | ".join(reasons)
        else:
            node.pop("ipa_explain_reasons", None)
            node.pop("ipa_explain_title", None)
        _attach_ipa_explain_fields(node.get("children") or [])


def _ipa_subnet_contained_dup_visible(node):
    """True when subnet containment should render as DUP (computed via ipaddress)."""
    if not node.get("subnet_contained_in"):
        return False
    net = _ipa_object_tree_containment_network(node)
    if net is None:
        return False
    if net.prefixlen >= net.max_prefixlen:
        return False
    return _ipa_object_node_role_from_tree_node(node) != IPA_NODE_ROLE_HOST


def _ipa_dup_groups_label(node):
    """Comma-separated list of group names that place this row in duplicate context."""
    names = []
    for ref in _display_cell_group_refs(node.get("cell_groups")):
        name = str(ref.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return ", ".join(names)


def _attach_ipa_dup_context_fields(nodes):
    """Attach render-ready duplicate tooltip/context fields for Dup column."""
    for node in nodes or []:
        node["subnet_contained_dup"] = _ipa_subnet_contained_dup_visible(node)

        reasons = []
        if node.get("subnet_contained_dup"):
            target = str(
                node.get("subnet_contained_in_name")
                or node.get("subnet_contained_in")
                or ""
            ).strip()
            if target:
                reasons.append(f"contained in parent prefix: {target}")
            else:
                reasons.append("contained in parent prefix")
        if node.get("object_duplicate"):
            target = str(node.get("object_duplicate_of") or "").strip()
            reasons.append(
                f"same object already shown in: {target}" if target else "same object already shown elsewhere"
            )
        if node.get("count_duplicate"):
            target = str(node.get("count_duplicate_of") or "").strip()
            reasons.append(
                f"excluded from total IP count (covered by: {target})"
                if target
                else "excluded from total IP count"
            )
        if node.get("is_doppelt"):
            reasons.append("duplicate cell entry")
        if node.get("cell_addresses_multi") and len(node.get("cell_addresses") or []) > 1:
            reasons.append(
                f"multiple address names share this network (+{len(node.get('cell_addresses') or []) - 1})"
            )
        if node.get("cell_groups_multi"):
            groups_label = _ipa_dup_groups_label(node)
            reasons.append(
                f"member of multiple groups: {groups_label}" if groups_label else "member of multiple groups"
            )

        if reasons:
            node["dup_reason_title"] = " | ".join(reasons)
        else:
            node.pop("dup_reason_title", None)

        _attach_ipa_dup_context_fields(node.get("children") or [])


def _mark_ipa_object_addr_drilldown_flags_lazy(nodes, obj_by_key=None):
    """Mark IPAM drilldown only for prefix nodes (no empty spacer rows)."""
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        obj = obj_by_key.get(key) if key and obj_by_key else None
        if obj is not None:
            role = _ipa_object_node_role_from_tree_node(node)
            obj_role = _ipa_object_node_role_from_obj(obj)
            cidr_hint = node.get("prefix_display_cidr") or (node.get("ip_ref") or {}).get("str")
            cidr_role = _ipa_object_node_role_from_cidr_hint(cidr_hint)
            if (
                role == IPA_NODE_ROLE_PREFIX
                or obj_role == IPA_NODE_ROLE_PREFIX
                or cidr_role == IPA_NODE_ROLE_PREFIX
            ):
                if _ipa_object_has_addr_drilldown(obj):
                    node["addr_drilldown_lazy"] = True
        _mark_ipa_object_addr_drilldown_flags_lazy(
            node.get("children") or [], obj_by_key
        )


def _finalize_ipa_cell_object_tree_lazy(nodes, cell_object_keys, obj_by_key):
    """Minimal cell-tree enrichment for lazy-first IPA loads (rules cells)."""
    _enrich_ipa_object_tree_cidr_from_names(nodes)
    _enrich_ipa_object_tree_networks_from_objects(nodes, obj_by_key)
    nodes = _merge_ipa_cell_nodes_by_network(nodes)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    nodes = _collapse_ipa_cell_siblings_by_network(nodes)
    nodes = _renest_ipa_contained_cell_siblings(nodes)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    _mark_ipa_subnet_containment_warnings(nodes)
    _mark_ipa_subnet_containment_peer_fallback(nodes)
    _refresh_ipa_cell_tree_inventory_roles(nodes, obj_by_key)
    _mark_ipa_object_addr_drilldown_flags_lazy(nodes, obj_by_key)
    _mark_ipa_cell_direct_flags(nodes, cell_object_keys)
    _attach_ipa_object_tree_status(nodes, obj_by_key)
    _attach_ipa_cell_address_fields(nodes, obj_by_key)
    _attach_ipa_drilldown_meta(nodes, obj_by_key)
    _attach_ipa_cell_ipam_object_refs(nodes, obj_by_key)
    from netbox_nsm.analyzers.ip_analyzer.ipa_zone_label import (
        attach_ipa_cell_zone_label_refs,
        attach_ipa_cell_tenant_ref,
    )

    attach_ipa_cell_zone_label_refs(nodes, obj_by_key)
    attach_ipa_cell_tenant_ref(nodes, obj_by_key)
    _attach_ipa_cell_display_hints(nodes)
    _attach_ipa_dup_context_fields(nodes)
    _mark_ipa_cell_open_by_default(nodes)
    _annotate_ipa_cell_tree_depth(nodes)
    return nodes


def _build_ipa_cell_object_tree(raw_selections, obj_by_key):
    """
    Build ordered root nodes for objects referenced in a rules cell.
    ``raw_selections`` preserves duplicate ct/pk pairs (doppelt).
    """
    cell_object_keys: set[tuple[int, int]] = set()
    for sel in raw_selections or []:
        try:
            cell_object_keys.add((int(sel["ct"]), int(sel["pk"])))
        except (KeyError, TypeError, ValueError):
            continue

    nodes = _flatten_cell_selections_to_address_nodes(raw_selections, obj_by_key)
    if ipa_lazy_load_enabled():
        return _finalize_ipa_cell_object_tree_lazy(nodes, cell_object_keys, obj_by_key)
    _enrich_ipa_object_tree_cidr_from_names(nodes)
    _enrich_ipa_object_tree_networks_from_objects(nodes, obj_by_key)
    nodes = _merge_ipa_cell_nodes_by_network(nodes)
    _enrich_ipa_collapsed_group_networks_from_members(nodes, obj_by_key)
    nodes = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(nodes, obj_by_key)
    lazy = ipa_lazy_load_enabled()
    if not lazy:
        prefix_cache = _IpaContainingPrefixCache()
        prefix_cache.register_tree(nodes, obj_by_key)
        nodes = _insert_ipam_filler_prefixes(nodes, obj_by_key, prefix_cache=prefix_cache)
        nodes = _synthesize_ipa_cell_ipam_parent_prefixes(
            nodes, obj_by_key, prefix_cache=prefix_cache
        )
    nodes = _sort_ipa_object_tree_siblings(nodes)
    nodes = _collapse_ipa_cell_siblings_by_network(nodes)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    nodes = _renest_ipa_contained_cell_siblings(nodes)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    _refresh_ipa_cell_tree_inventory_roles(nodes, obj_by_key)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    _mark_ipa_subnet_containment_warnings(nodes)
    _mark_ipa_subnet_containment_peer_fallback(nodes)
    _mark_ipa_cell_tree_parent_hints(nodes)
    _mark_ipa_object_tree_duplicate_flags(nodes, is_root=True)
    nodes = _prune_ipa_object_tree_duplicate_nodes(nodes)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    tree_obj_by_key = _collect_ipa_tree_member_obj_by_key(obj_by_key)
    resolve_cache: dict[str, dict] = {}
    _mark_ipa_object_addr_drilldown_flags(nodes, tree_obj_by_key)
    _attach_ipa_object_tree_ipam_stats(
        nodes, tree_obj_by_key, resolve_cache=resolve_cache
    )
    _mark_ipa_cell_direct_flags(nodes, cell_object_keys)
    _attach_ipa_object_tree_status(nodes, tree_obj_by_key)
    _attach_ipa_dup_cell_statuses(nodes)
    _attach_ipa_drilldown_meta(nodes, tree_obj_by_key, resolve_cache=resolve_cache)
    _ensure_ipa_cell_tree_network_links(
        nodes, tree_obj_by_key, resolve_cache=resolve_cache
    )
    _attach_ipa_cell_address_fields(nodes, tree_obj_by_key)
    _attach_ipa_cell_ipam_object_refs(nodes, tree_obj_by_key)
    from netbox_nsm.analyzers.ip_analyzer.ipa_zone_label import (
        attach_ipa_cell_zone_label_refs,
        attach_ipa_cell_tenant_ref,
    )

    attach_ipa_cell_zone_label_refs(nodes, tree_obj_by_key)
    attach_ipa_cell_tenant_ref(nodes, tree_obj_by_key)
    _sync_ipa_cell_tree_node_flags(nodes)
    nodes = _prune_ipa_info_gap_nodes(nodes)
    _mark_ipa_ipam_parent_prefix_flags(nodes)
    _mark_ipa_cell_pill_roles(nodes)
    _scrub_ipa_cell_group_self_refs(nodes)
    _attach_ipa_cell_display_hints(nodes)
    _attach_ipa_explain_fields(nodes)
    _attach_ipa_dup_context_fields(nodes)
    _mark_ipa_cell_open_by_default(nodes)
    _annotate_ipa_cell_tree_depth(nodes)
    return nodes


def _mark_ipa_object_addr_drilldown_flags(nodes, obj_by_key=None):
    """Mark tree nodes that can lazy-load an IPAM drilldown when expanded."""
    for node in nodes or []:
        obj = None
        key = _ipa_object_tree_node_key(node)
        if key and obj_by_key:
            obj = obj_by_key.get(key)
        lazy = _ipa_object_node_should_drilldown(node, obj=obj, obj_by_key=obj_by_key)
        if not lazy and obj is not None:
            lazy = _ipa_object_has_addr_drilldown(obj)
        if not lazy and (node.get("ip_ref") or node.get("prefix_display_cidr")):
            lazy = _ipa_object_node_should_drilldown(node)
        if lazy:
            if obj is None:
                lazy = False
            else:
                lazy = _ipa_object_drilldown_has_visible_content(obj)
        if lazy:
            role = _ipa_object_node_role_from_tree_node(node)
            obj_role = _ipa_object_node_role_from_obj(obj) if obj is not None else IPA_NODE_ROLE_EMPTY
            cidr_hint = node.get("prefix_display_cidr") or (node.get("ip_ref") or {}).get("str")
            cidr_role = _ipa_object_node_role_from_cidr_hint(cidr_hint)
            lazy = (
                role == IPA_NODE_ROLE_PREFIX
                or obj_role == IPA_NODE_ROLE_PREFIX
                or cidr_role == IPA_NODE_ROLE_PREFIX
            )
        if lazy:
            node["addr_drilldown_lazy"] = True
        _mark_ipa_object_addr_drilldown_flags(node.get("children") or [], obj_by_key)


def _ipa_object_tree_csv_line(path_prefix, node):
    """One CSV row for a cell object, including subnet containment warnings."""
    row = list(path_prefix or [])
    ip_str = (
        node.get("prefix_display_cidr")
        or (node.get("ip_ref") or {}).get("str")
        or ""
    )
    ip_str = str(ip_str).strip()
    if ip_str and (not row or ip_str != row[-1]):
        row.append(ip_str)
    line = _hub._addr_path_line(row)
    contained = node.get("subnet_contained_in")
    if contained:
        line = f"{line},warn duplicate→{contained}"
    return line


def _flatten_ipa_object_tree_copy_lines(nodes, path_prefix=None):
    """CSV copy lines for cell object tree nodes (with containment warnings)."""
    if path_prefix is None:
        path_prefix = []
    lines = []
    for node in nodes or []:
        name = str(node.get("name") or "").strip()
        branch = path_prefix + ([name] if name else [])
        if node.get("ip_ref") or node.get("prefix_display_cidr"):
            lines.append(_ipa_object_tree_csv_line(branch, node))
        lines.extend(_flatten_ipa_object_tree_copy_lines(node.get("children") or [], branch))
    return lines


def _copy_ipa_cell_tree_subtree(node):
    """Recursive copy of a cell-tree node dict (avoid mutating diff addr_analyzer)."""
    copied = {key: value for key, value in node.items() if key != "children"}
    children = node.get("children") or []
    if children:
        copied["children"] = [_copy_ipa_cell_tree_subtree(child) for child in children]
    return copied


def _collect_addr_diff_cell_tree_groups(addr_analyzer):
    """Extract diff group roots from ``addr_analyzer`` sections."""
    groups = []
    for section in addr_analyzer or []:
        for type_block in section.get("types") or []:
            for group in type_block.get("nodes") or []:
                if group.get("diff_group"):
                    groups.append(group)
    return groups


def _prepare_diff_cell_tree_node(node):
    """Normalize one diff addr-tree node for flat cell-tree rendering."""
    prepared = _copy_ipa_cell_tree_subtree(node)
    children = prepared.get("children") or []
    if prepared.get("kind") == "leaf":
        if prepared.get("cell_addresses"):
            prepared.setdefault("is_cell_direct", True)
        role = _ipa_object_node_role_from_tree_node(prepared)
        hints = _ipa_object_node_presentation(
            role, has_member_children=bool(children)
        )
        if hints.get("node_role"):
            prepared.setdefault("node_role", hints["node_role"])
            prepared.setdefault("kind", hints["kind"])
    elif prepared.get("diff_group"):
        prepared.setdefault("kind", "group")
    if children:
        prepared["children"] = [
            _prepare_diff_cell_tree_node(child) for child in children
        ]
    return prepared


def _build_ipa_cell_object_tree_from_diff(addr_analyzer):
    """
    Convert addr diff analysis groups into IPA cell-tree ``object_tree`` nodes.

    Reuses the same nine-column flat table as merge/cell selection mode; diff
    badges live in the **Diff** column, group backgrounds via ``diff_group``.
    """
    groups = _collect_addr_diff_cell_tree_groups(addr_analyzer)
    if not groups:
        return []

    nodes = [_prepare_diff_cell_tree_node(group) for group in groups]
    _enrich_ipa_object_tree_cidr_from_names(nodes)
    _refresh_ipa_cell_tree_inventory_roles(nodes)
    _mark_ipa_cell_tree_parent_hints(nodes)
    _attach_ipa_drilldown_meta(nodes, {})
    _ensure_ipa_cell_tree_network_links(nodes, {})
    _attach_ipa_cell_ipam_object_refs(nodes, {})
    from netbox_nsm.analyzers.ip_analyzer.ipa_zone_label import (
        attach_ipa_cell_zone_label_refs,
        attach_ipa_cell_tenant_ref,
    )

    attach_ipa_cell_zone_label_refs(nodes, {})
    attach_ipa_cell_tenant_ref(nodes, {})
    _sync_ipa_cell_tree_node_flags(nodes)
    _attach_ipa_cell_display_hints(nodes)
    _attach_ipa_explain_fields(nodes)
    _annotate_ipa_cell_tree_depth(nodes)
    return nodes


def _apply_object_tree_copy_lines(addr_analyzer, object_tree):
    """Replace All-level CSV paths when the cell object tree is shown."""
    if not object_tree or not addr_analyzer:
        return addr_analyzer
    lines = _hub._prefix_addr_copy_lines(
        _flatten_ipa_object_tree_copy_lines(object_tree),
        "all",
    )
    if not lines:
        return addr_analyzer
    for section in addr_analyzer:
        for type_block in section.get("types") or []:
            type_block["all_copy_lines"] = lines
    return addr_analyzer


def _build_object_address_analyzer(_rulebook, obj, content_type_id):
    """Address analysis for a single object (IP Analyzer — object only, no src/dst)."""
    if not obj or not content_type_id:
        return []
    return _hub._build_multi_object_addr_analyzer([obj])


