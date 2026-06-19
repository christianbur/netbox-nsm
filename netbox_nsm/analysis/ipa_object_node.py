"""
Presentation roles and helpers for IP Analyzer object-tree nodes.

Tree shape (conceptual)::

    NSM group (nsm_group)
      ├─ NSM address → Prefix (nsm_prefix)  →  [lazy] IPAM prefix layer → children
      ├─ NSM address → Range  (nsm_range)   →  [lazy] IPAM range → IPs
      ├─ NSM address → Host   (nsm_host)    →  leaf (no IPAM container drilldown)
      └─ nested NSM group (nsm_group, group_depth+1)
            └─ …

Counts always come from IPAM prefix/range stats, never from direct host leaves.
"""
from __future__ import annotations

import netbox_nsm.analysis._lazy_api as _hub
from netbox_nsm.analysis.addr_constants import FIELD_TYPE_LABELS

# Object-tree node roles (``node_role`` on tree dicts).
IPA_NODE_ROLE_GROUP = "nsm_group"
IPA_NODE_ROLE_PREFIX = "nsm_prefix"
IPA_NODE_ROLE_RANGE = "nsm_range"
IPA_NODE_ROLE_HOST = "nsm_host"
IPA_NODE_ROLE_EMPTY = "nsm_empty"
IPA_NODE_ROLE_IPAM_PREFIX = "ipam_prefix"

_IPA_INVENTORY_ROLES = frozenset(
    {IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE, IPA_NODE_ROLE_HOST}
)


def _ipa_object_expands_members(obj) -> bool:
    """True when the object tree should inline-expand NSM group members."""
    if getattr(obj, "address_type", None) == "address-group":
        return True
    if _hub._addr_ip_ref(obj) is not None:
        return False
    return bool(_hub._addr_group_members(obj))


def _ipa_object_has_addr_drilldown(obj) -> bool:
    """True when lazy-loading should expose IPAM resolution beyond cell members."""
    if not obj or not _hub._object_supports_addr_analysis(obj):
        return False
    if _ipa_object_expands_members(obj) and _hub._addr_ip_ref(obj) is None:
        return False
    return True


def _ipa_object_node_role_from_cidr_hint(cidr) -> str | None:
    """Infer inventory role from a CIDR/range string when ``ip_ref.type`` is absent."""
    import ipaddress
    import re

    text = str(cidr or "").strip()
    if not text:
        return None
    if "–" in text:
        return IPA_NODE_ROLE_RANGE
    if re.match(r"^[\d.]+\s*-\s*[\d.]+$", text):
        return IPA_NODE_ROLE_RANGE
    if "/" not in text:
        return None
    try:
        net = ipaddress.ip_network(text, strict=False)
    except ValueError:
        return None
    return (
        IPA_NODE_ROLE_HOST
        if net.prefixlen == net.max_prefixlen
        else IPA_NODE_ROLE_PREFIX
    )


def _ipa_object_node_role_from_ipam_obj(ipam_obj) -> str | None:
    """Map a resolved NetBox IPAM ORM object to an inventory role."""
    if ipam_obj is None:
        return None
    try:
        from ipam.models import IPAddress, IPRange, Prefix
    except ImportError:
        return None
    if isinstance(ipam_obj, Prefix):
        return IPA_NODE_ROLE_PREFIX
    if isinstance(ipam_obj, IPRange):
        return IPA_NODE_ROLE_RANGE
    if isinstance(ipam_obj, IPAddress):
        return IPA_NODE_ROLE_HOST
    return None


def _ipa_object_node_role_from_ip_ref(ip_ref) -> str | None:
    """Map an IPAM ``ip_ref`` payload to an object-tree inventory role."""
    if not ip_ref:
        return None
    ref_type = ip_ref.get("type")
    if ref_type == FIELD_TYPE_LABELS["prefix"]:
        return IPA_NODE_ROLE_PREFIX
    if ref_type == FIELD_TYPE_LABELS["range"]:
        return IPA_NODE_ROLE_RANGE
    if ref_type == FIELD_TYPE_LABELS["ip_address"]:
        return IPA_NODE_ROLE_HOST

    ipam_obj = _hub._ipam_obj_from_ip_ref(ip_ref)
    role = _ipa_object_node_role_from_ipam_obj(ipam_obj)
    if role is not None:
        return role

    return _ipa_object_node_role_from_cidr_hint(ip_ref.get("str"))


def _ipa_object_node_role_from_obj(obj, *, expands_members: bool | None = None) -> str:
    """Classify an ORM object before building its tree node."""
    if expands_members is None:
        expands_members = _ipa_object_expands_members(obj)
    if expands_members:
        return IPA_NODE_ROLE_GROUP
    ip_ref = _hub._addr_ip_ref(obj)
    if ip_ref:
        return _ipa_object_node_role_from_ip_ref(ip_ref) or IPA_NODE_ROLE_EMPTY
    from netbox_nsm.objects.address_literal import get_network_literal

    literal = get_network_literal(obj)
    if literal:
        return _ipa_object_node_role_from_cidr_hint(literal) or IPA_NODE_ROLE_PREFIX
    return IPA_NODE_ROLE_EMPTY


def _ipa_object_node_role_from_tree_node(node) -> str:
    """Infer role from an existing tree node dict."""
    if node.get("layer") == "ipam_prefix":
        return IPA_NODE_ROLE_IPAM_PREFIX
    role = node.get("node_role")
    if role:
        return role
    ip_ref = node.get("ip_ref") or {}
    inventory_role = _ipa_object_node_role_from_ip_ref(ip_ref)
    if inventory_role:
        return inventory_role
    for hint in (node.get("prefix_display_cidr"), node.get("name")):
        inventory_role = _ipa_object_node_role_from_cidr_hint(hint)
        if inventory_role:
            return inventory_role
    if node.get("children"):
        return IPA_NODE_ROLE_GROUP
    return IPA_NODE_ROLE_EMPTY


def _ipa_object_node_presentation(role: str, *, has_member_children: bool = False) -> dict:
    """
    Return tree presentation hints for a role.

    - ``kind``: ``group`` (expandable) or ``leaf``
    - ``expand_members``: inline NSM member children
    - ``drilldown``: lazy IPAM resolution on expand (prefix/range containers)
    """
    if role == IPA_NODE_ROLE_GROUP:
        return {
            "node_role": role,
            "kind": "group" if has_member_children else "leaf",
            "expand_members": True,
            "drilldown": False,
        }
    if role == IPA_NODE_ROLE_PREFIX:
        return {
            "node_role": role,
            "kind": "group",
            "expand_members": False,
            "drilldown": True,
        }
    if role == IPA_NODE_ROLE_RANGE:
        return {
            "node_role": role,
            "kind": "group",
            "expand_members": False,
            "drilldown": True,
        }
    if role == IPA_NODE_ROLE_HOST:
        return {
            "node_role": role,
            "kind": "leaf",
            "expand_members": False,
            "drilldown": False,
        }
    if role == IPA_NODE_ROLE_IPAM_PREFIX:
        return {
            "node_role": role,
            "kind": "group",
            "layer": "ipam_prefix",
            "expand_members": False,
            "drilldown": False,
        }
    return {
        "node_role": IPA_NODE_ROLE_EMPTY,
        "kind": "leaf",
        "expand_members": False,
        "drilldown": False,
    }


def _ipa_object_node_should_drilldown(
    node, *, obj=None, obj_by_key=None
) -> bool:
    """Whether expanding this node should lazy-load IPAM drilldown content."""
    if obj is None:
        key = None
        try:
            key = (int(node.get("ct") or 0), int(node.get("pk") or 0))
        except (TypeError, ValueError):
            pass
        if key and obj_by_key:
            obj = obj_by_key.get(key)

    if obj is not None and not _hub._object_supports_addr_analysis(obj):
        return False

    role = (
        _ipa_object_node_role_from_obj(obj)
        if obj is not None
        else _ipa_object_node_role_from_tree_node(node)
    )
    hints = _ipa_object_node_presentation(role)
    if not hints.get("drilldown"):
        return False
    if role in (IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE):
        return bool(node.get("ip_ref") or node.get("prefix_display_cidr") or obj)
    return bool(node.get("ip_ref") or node.get("prefix_display_cidr") or node.get("ipam_stats"))


def _ipa_object_node_apply_presentation(
    node,
    obj,
    *,
    group_depth: int = 0,
    member_children: list | None = None,
) -> dict:
    """
    Apply role, kind, and structural fields to a freshly built object-tree node.

    *member_children* — inline NSM members when role is ``nsm_group``.
    *group_depth* — nesting level for groups-in-groups (0 = cell root).
    """
    role = _ipa_object_node_role_from_obj(obj)
    has_members = bool(member_children)
    hints = _ipa_object_node_presentation(role, has_member_children=has_members)

    node["node_role"] = hints["node_role"]
    node["kind"] = hints["kind"]
    if role == IPA_NODE_ROLE_GROUP:
        node["group_depth"] = group_depth
        node["children"] = list(member_children or [])
    elif hints["kind"] == "group":
        node.setdefault("children", [])
    else:
        node["children"] = []

    if hints.get("layer"):
        node["layer"] = hints["layer"]

    if role != IPA_NODE_ROLE_GROUP:
        ip_ref = _hub._addr_ip_ref(obj)
        if ip_ref:
            node["ip_ref"] = _hub._addr_ip_ref_node_dict(ip_ref)
            _hub._attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)
        else:
            from netbox_nsm.objects.address_literal import attach_literal_prefix_display

            attach_literal_prefix_display(node, obj)
    return node


def _ipa_object_group_members(obj) -> list:
    """Ordered member list for an NSM group (forward M2M + legacy address_group)."""
    members = list(_hub._addr_group_members(obj))
    if getattr(obj, "address_type", None) == "address-group":
        try:
            seen = {m.pk for m in members}
            members.extend(
                m for m in obj.address_group.all() if m.pk not in seen
            )
        except Exception:
            pass
    return members


__all__ = (
    "IPA_NODE_ROLE_EMPTY",
    "IPA_NODE_ROLE_GROUP",
    "IPA_NODE_ROLE_HOST",
    "IPA_NODE_ROLE_IPAM_PREFIX",
    "IPA_NODE_ROLE_PREFIX",
    "IPA_NODE_ROLE_RANGE",
    "_ipa_object_expands_members",
    "_ipa_object_group_members",
    "_ipa_object_has_addr_drilldown",
    "_ipa_object_node_apply_presentation",
    "_ipa_object_node_presentation",
    "_ipa_object_node_role_from_ipam_obj",
    "_ipa_object_node_role_from_ip_ref",
    "_ipa_object_node_role_from_obj",
    "_ipa_object_node_role_from_tree_node",
    "_ipa_object_node_should_drilldown",
)
