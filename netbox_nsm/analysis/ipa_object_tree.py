
"""IP Analyzer cell object tree (rule-cell hierarchy)."""
from __future__ import annotations
from django.contrib.contenttypes.models import ContentType
import netbox_nsm.analysis._lazy_api as _hub
from netbox_nsm.analysis.addr_ip_refs import _FIELD_TYPE_LABELS
from netbox_nsm.analysis.addr_netmask import sync_prefix_display_netmask
from netbox_nsm.core.nsm_object_status import get_nsm_object_status
from netbox_nsm.analysis.ipa_ipam_tree import _ipa_object_drilldown_has_visible_content
from netbox_nsm.analysis.ipa_object_node import (
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

def _build_ipa_object_columns(selections, objs):
    """IP Analysis: one table column per selected object (name + counter in header)."""
    columns = []
    for sel, obj in zip(selections, objs):
        analysis = _hub._build_multi_object_addr_analysis([obj]) if obj else []
        columns.append(
            {
                "name": sel["name"],
                "ct": sel["ct"],
                "pk": sel["pk"],
                "leaf_count": _hub._leaf_count_for_addr_analysis(analysis),
                "addr_analysis": analysis,
            }
        )
    return columns


def _parse_ipa_column_selections(request, col_suffix=""):
    """
    Parse repeated ip_ct/ip_pk/ip_name (or ip2_*) query params.
    Returns (selections, addr_analysis) where selections is
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
    from netbox_nsm.analysis.ipa_object_node import _ipa_object_expands_members as _impl

    return _impl(obj)


def _ipa_object_has_addr_drilldown(obj) -> bool:
    """Re-export from ``ipa_object_node`` (stable ``@patch`` target)."""
    from netbox_nsm.analysis.ipa_object_node import _ipa_object_has_addr_drilldown as _impl

    return _impl(obj)


def _attach_ipa_object_tree_ipam_stats(nodes, obj_by_key=None):
    """Attach NetBox prefix/range tab counts to object-tree nodes for summary badges."""
    for node in nodes or []:
        if not node.get("ipam_stats"):
            ip_ref = node.get("ip_ref") or {}
            stats = _hub._resolve_ipam_stats_from_ip_ref(ip_ref)
            if stats is None and node.get("prefix_display_cidr"):
                stats = _hub._resolve_ipam_stats_from_ip_ref(
                    {"str": node["prefix_display_cidr"]}
                )
            if stats is None:
                cidr = _ipa_cidr_from_object_name(node.get("name"))
                if cidr:
                    stats = _hub._resolve_ipam_stats_from_ip_ref({"str": cidr})
            if stats is None and obj_by_key:
                key = _ipa_object_tree_node_key(node)
                obj = obj_by_key.get(key) if key else None
                if obj is not None:
                    full_ref = _hub._addr_ip_ref(obj)
                    if full_ref is not None:
                        stats = _hub._resolve_ipam_stats_from_ip_ref(full_ref)
                    if stats is None:
                        prefix = _ipa_prefix_for_cell_object(obj)
                        if prefix is not None:
                            stats = _hub._prefix_ipam_stats(prefix)
            if stats:
                _hub._attach_ipam_stats_meta(node, stats)
        _attach_ipa_object_tree_ipam_stats(node.get("children") or [], obj_by_key)


def _attach_ipa_drilldown_meta(nodes, obj_by_key=None):
    """Attach INFO metadata to each cell-direct prefix/range row."""
    from netbox_nsm.analysis.ipa_ipam_tree import _build_ipa_drilldown_source_meta

    inventory_roles = {IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE}
    for node in nodes or []:
        if obj_by_key and node.get("is_cell_direct"):
            role = node.get("node_role") or _ipa_object_node_role_from_tree_node(node)
            if role in inventory_roles:
                key = _ipa_object_tree_node_key(node)
                obj = obj_by_key.get(key) if key else None
                if obj is not None:
                    node["ipa_drilldown_meta"] = _build_ipa_drilldown_source_meta(obj)
        _attach_ipa_drilldown_meta(node.get("children") or [], obj_by_key)


def _attach_ipa_object_tree_ip_meta(node, obj):
    """Attach IP/CIDR display; keep kind/role from ``_ipa_object_node_apply_presentation``."""
    if _ipa_object_expands_members(obj):
        return node
    ip_ref = _hub._addr_ip_ref(obj)
    if not ip_ref:
        from netbox_nsm.objects.address_literal import attach_literal_prefix_display

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


def _flatten_cell_selections_to_address_nodes(raw_selections, obj_by_key):
    """
    Merge cell selections into unique address nodes with ``cell_groups`` metadata.
    """
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

        for node, group_refs in _yield_flat_cell_addresses(obj, ct_id=sel_key[0]):
            addr_key = _ipa_object_tree_node_key(node)
            if not addr_key:
                continue
            entry = merged.get(addr_key)
            if entry is None:
                entry = {
                    "node": node,
                    "group_refs": [],
                    "is_cell_direct": False,
                }
                merged[addr_key] = entry
            for ref in group_refs:
                entry["group_refs"] = _append_cell_group_ref(entry["group_refs"], ref)
            if not is_group_sel and addr_key == sel_key:
                entry["is_cell_direct"] = True

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


def _ipa_object_tree_sort_key(node):
    """IPAM sibling order: network address (numeric), then prefix length, then name."""
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
    if role == IPA_NODE_ROLE_HOST or ip_ref.get("type") == _FIELD_TYPE_LABELS["ip_address"]:
        for candidate in (
            _ipa_cidr_from_host_object_name(node.get("name")),
            ip_ref.get("str"),
            node.get("prefix_display_cidr"),
        ):
            if not candidate:
                continue
            try:
                net = ipaddress.ip_network(str(candidate).strip(), strict=False)
            except ValueError:
                continue
            if net.prefixlen == 32:
                return net
            host_ip = str(net.network_address)
            try:
                return ipaddress.ip_network(f"{host_ip}/32", strict=False)
            except ValueError:
                continue
    return _hub._addr_tree_node_network(node)


def _ipa_object_tree_network_key(node):
    """Stable network identity for deduplicating cell-tree rows."""
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
        _attach_ipa_object_tree_status(node.get("children") or [], obj_by_key)


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
    merged: dict[tuple, dict] = {}
    unkeyed: list[dict] = []
    for node in nodes or []:
        net_key = _ipa_object_tree_network_key(node)
        if net_key is None:
            unkeyed.append(node)
            continue
        keeper = merged.get(net_key)
        if keeper is None:
            merged[net_key] = node
            continue
        if node.get("is_cell_direct") and not keeper.get("is_cell_direct"):
            _merge_ipa_cell_node_metadata(node, keeper)
            merged[net_key] = node
        else:
            _merge_ipa_cell_node_metadata(keeper, node)
    result = list(merged.values()) + unkeyed
    for node in result:
        _sync_cell_addresses(node)
    return result


def _collapse_ipa_cell_siblings_by_network(nodes):
    """Merge same-network siblings at every tree level (one row per CIDR)."""
    collapsed = _merge_ipa_cell_nodes_by_network(nodes)
    for node in collapsed:
        children = node.get("children")
        if children:
            node["children"] = _collapse_ipa_cell_siblings_by_network(children)
    return collapsed


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
            "str": str(prefix),
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

    forest = []
    for node in sorted(nodes, key=_ipa_object_tree_sort_key):
        parent = _ipa_deepest_cell_ancestor_node(
            node_prefix.get(id(node)), prefix_pk_to_node
        )
        if parent is None:
            net = _ipa_object_tree_containment_network(node)
            parent = _ipa_find_deepest_containing_node(forest, net) if net else None
        if parent is not None:
            parent.setdefault("children", []).append(node)
            parent["kind"] = "group"
        else:
            forest.append(node)

    for node in forest:
        children = node.get("children") or []
        if children:
            node["children"] = sorted(children, key=_ipa_object_tree_sort_key)
    return forest


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
                if anc_net and net.subnet_of(anc_net) and net != anc_net:
                    node["subnet_contained_in"] = _ipa_object_tree_containment_cidr(anc)
                    node["subnet_contained_in_name"] = anc.get("name") or ""
                    node["subnet_contained_in_url"] = anc.get("url") or ""
                    node["subnet_containment_display_net"] = (
                        _ipa_subnet_containment_display_net(node)
                    )
                    break

        next_ancestors = ancestors
        if _hub._addr_tree_node_network(node):
            next_ancestors = ancestors + [node]
        _mark_ipa_subnet_containment_warnings(
            node.get("children") or [], next_ancestors
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
        try:
            key = (int(node.get("ct") or 0), int(node.get("pk") or 0))
        except (TypeError, ValueError):
            key = None

        if key and key in seen:
            if not (is_root and node.get("is_doppelt")):
                node["object_duplicate"] = True
                node["object_duplicate_of"] = first_names.get(key, "")
                node["object_duplicate_of_url"] = first_urls.get(key, "")
        elif key:
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


def _prune_ipa_object_tree_duplicate_nodes(nodes):
    """Remove repeated object identities and networks; one row per network."""
    pruned = []
    seen_nets: set[tuple] = set()
    for node in nodes or []:
        if node.get("object_duplicate"):
            continue
        net_key = _ipa_object_tree_network_key(node)
        if net_key is not None:
            if net_key in seen_nets:
                continue
            seen_nets.add(net_key)
        children = node.get("children")
        if children:
            node["children"] = _prune_ipa_object_tree_duplicate_nodes(children)
        pruned.append(node)
    return pruned


def _ipa_cell_object_tree_visible(nodes, raw_count, *, prefer_logical_merge=False):
    """
    Whether to render the cell object tree (NSM layer + lazy IPAM drilldown).

    Always prefer the object tree when nodes were built: users expand prefixes via
    ``addr_drilldown_lazy`` and need ``ipam_stats`` on NSM objects. The merged
    addr_analysis tree remains available for counts/CSV fallback only.
    """
    del prefer_logical_merge, raw_count  # kept for stable call/patch signatures
    return bool(nodes)


def _mark_ipa_cell_direct_flags(nodes, cell_object_keys):
    """Mark only objects explicitly listed in the rule cell (not tree-expanded children)."""
    for node in nodes or []:
        key = _ipa_object_tree_node_key(node)
        if key and key in cell_object_keys:
            node["is_cell_direct"] = True
        else:
            node.pop("is_cell_direct", None)
        _mark_ipa_cell_direct_flags(node.get("children") or [], cell_object_keys)


def _ipa_node_renders_as_details(node):
    """True when ``addr_tree_node.html`` renders this node as ``<details>`` (IPA context)."""
    if node.get("kind") == "group":
        return bool(
            node.get("children")
            or node.get("ipam_stats")
            or node.get("addr_drilldown_lazy")
            or node.get("is_cell_direct")
        )
    return bool(node.get("ct") and node.get("addr_drilldown_lazy")) or bool(
        node.get("is_cell_direct") and node.get("ipa_drilldown_meta")
    )


def _mark_ipa_cell_open_by_default(nodes):
    """Mark IPA ``<details>`` nodes that should render open for cell-direct visibility."""
    for node in nodes or []:
        children = node.get("children") or []
        _mark_ipa_cell_open_by_default(children)
        child_exposes_cell_direct = any(
            c.get("is_cell_direct") or c.get("ipa_open_by_default") for c in children
        )
        if _ipa_node_renders_as_details(node) and (
            node.get("is_cell_direct") or child_exposes_cell_direct
        ):
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
    _enrich_ipa_object_tree_cidr_from_names(nodes)
    nodes = _merge_ipa_cell_nodes_by_network(nodes)
    nodes = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(nodes, obj_by_key)
    nodes = _sort_ipa_object_tree_siblings(nodes)
    nodes = _collapse_ipa_cell_siblings_by_network(nodes)
    _mark_ipa_subnet_containment_warnings(nodes)
    _mark_ipa_object_tree_duplicate_flags(nodes, is_root=True)
    nodes = _prune_ipa_object_tree_duplicate_nodes(nodes)
    tree_obj_by_key = _collect_ipa_tree_member_obj_by_key(obj_by_key)
    _mark_ipa_object_addr_drilldown_flags(nodes, tree_obj_by_key)
    _attach_ipa_object_tree_ipam_stats(nodes, tree_obj_by_key)
    _mark_ipa_cell_direct_flags(nodes, cell_object_keys)
    _attach_ipa_object_tree_status(nodes, tree_obj_by_key)
    _attach_ipa_drilldown_meta(nodes, tree_obj_by_key)
    _mark_ipa_cell_open_by_default(nodes)
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


def _apply_object_tree_copy_lines(addr_analysis, object_tree):
    """Replace All-level CSV paths when the cell object tree is shown."""
    if not object_tree or not addr_analysis:
        return addr_analysis
    lines = _hub._prefix_addr_copy_lines(
        _flatten_ipa_object_tree_copy_lines(object_tree),
        "all",
    )
    if not lines:
        return addr_analysis
    for section in addr_analysis:
        for type_block in section.get("types") or []:
            type_block["all_copy_lines"] = lines
    return addr_analysis


def _build_object_address_analysis(_rulebook, obj, content_type_id):
    """Address analysis for a single object (IP Analysis — object only, no src/dst)."""
    if not obj or not content_type_id:
        return []
    return _hub._build_multi_object_addr_analysis([obj])


