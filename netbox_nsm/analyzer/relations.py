"""
Edge resolvers for NetBox models.

Registered resolvers are called by ``registry.get_edges(obj)`` for known model
types. The catch-all ``_generic_fallback`` at the bottom handles everything
else (e.g. netbox_custom_objects Table*Models).

Import dependency:
    registry.py  ←  _helpers.py  ←  relations.py
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from .registry import (
    AnalyzerEdge,
    AnalyzerRegistry,
    AnalyzerNode,
    node_from_object,
    registry,
)
from ._helpers import (
    nsm_link_edges,
    policy_item_edges,
    group_m2m_edges,
    addr_fk_edges,
    inherited_nsm_link_edges,
    _MAX,
)

# ── Shared host helpers ─────────────────────────────────────────────────────


def _host_edges(obj, *, iface_model, iface_fk: str) -> list[AnalyzerEdge]:
    """Common edges for Device and VirtualMachine."""
    edges = []

    for iface in iface_model.objects.filter(**{iface_fk: obj})[:_MAX]:
        edges.append(
            AnalyzerEdge("Interface", "has_interface", node_from_object(iface))
        )

    for attr, label, edge_type in (
        ("primary_ip4", "Primary IPv4", "primary_ip4"),
        ("primary_ip6", "Primary IPv6", "primary_ip6"),
        ("site", "Site", "in_site"),
        ("tenant", "Tenant", "in_tenant"),
    ):
        val = getattr(obj, attr, None)
        if val:
            edges.append(AnalyzerEdge(label, edge_type, node_from_object(val)))

    # Bidirectional ObjectLinks (Security Panel parity: zones, labels, prefixes, etc.)
    ct = ContentType.objects.get_for_model(obj)
    edges.extend(nsm_link_edges(obj, ct))

    # Rules that reference this host (one edge per rule)
    edges.extend(policy_item_edges(obj, ct))

    return edges


def _iface_edges(iface, *, parent_attr: str, parent_label: str) -> list[AnalyzerEdge]:
    """Common edges for dcim.Interface and virtualization.VMInterface."""
    from ipam.models import IPAddress

    edges = []
    parent = getattr(iface, parent_attr, None)
    if parent:
        edges.append(AnalyzerEdge(parent_label, "belongs_to", node_from_object(parent)))

    iface_ct = ContentType.objects.get_for_model(iface)
    for ip in IPAddress.objects.filter(
        assigned_object_type=iface_ct, assigned_object_id=iface.pk
    )[:_MAX]:
        edges.append(AnalyzerEdge("IP", "has_ip", node_from_object(ip)))

    vlan = getattr(iface, "untagged_vlan", None)
    if vlan:
        edges.append(AnalyzerEdge("Untagged VLAN", "in_vlan", node_from_object(vlan)))

    return edges


# ── Device ──────────────────────────────────────────────────────────────────
from dcim.models import Device, Interface  # noqa: E402


@registry.register(Device)
def _device(device):
    return _host_edges(device, iface_model=Interface, iface_fk="device")


# ── VirtualMachine ───────────────────────────────────────────────────────────
from virtualization.models import VirtualMachine, VMInterface  # noqa: E402


@registry.register(VirtualMachine)
def _vm(vm):
    return _host_edges(vm, iface_model=VMInterface, iface_fk="virtual_machine")


# ── Interface (dcim) ────────────────────────────────────────────────────────
@registry.register(Interface)
def _interface(iface):
    return _iface_edges(iface, parent_attr="device", parent_label="Device")


# ── VMInterface ─────────────────────────────────────────────────────────────
@registry.register(VMInterface)
def _vminterface(iface):
    return _iface_edges(iface, parent_attr="virtual_machine", parent_label="VM")


# ── IPAddress ───────────────────────────────────────────────────────────────
from ipam.models import IPAddress, Prefix  # noqa: E402


@registry.register(IPAddress)
def _ipaddress(ip):
    edges = []

    if ip.assigned_object:
        edges.append(
            AnalyzerEdge(
                "Assigned to", "assigned_to", node_from_object(ip.assigned_object)
            )
        )
    if ip.vrf:
        edges.append(AnalyzerEdge("VRF", "in_vrf", node_from_object(ip.vrf)))

    # Most-specific containing prefix (direct parent)
    try:
        ip_str = str(ip.address).split("/")[0]
        matches = list(Prefix.objects.filter(prefix__net_contains=ip_str)[:10])
        matches.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
        if matches:
            edges.append(
                AnalyzerEdge("Subnet", "in_prefix", node_from_object(matches[0]))
            )
    except Exception:
        pass

    ct = ContentType.objects.get_for_model(ip)
    edges.extend(policy_item_edges(ip, ct))
    edges.extend(nsm_link_edges(ip, ct))
    edges.extend(addr_fk_edges(ip))
    edges.extend(inherited_nsm_link_edges(ip))
    return edges


# ── Prefix ──────────────────────────────────────────────────────────────────
@registry.register(Prefix)
def _prefix(pfx):
    edges = []

    for ip in IPAddress.objects.filter(address__net_contained_or_equal=str(pfx.prefix))[
        :_MAX
    ]:
        edges.append(AnalyzerEdge("IP", "contains_ip", node_from_object(ip)))

    for attr, label, edge_type in (
        ("vrf", "VRF", "in_vrf"),
        ("_site", "Site", "in_site"),
        ("tenant", "Tenant", "in_tenant"),
        ("vlan", "VLAN", "in_vlan"),
    ):
        val = getattr(pfx, attr, None)
        if val:
            edges.append(AnalyzerEdge(label, edge_type, node_from_object(val)))

    ct = ContentType.objects.get_for_model(pfx)
    edges.extend(policy_item_edges(pfx, ct))
    edges.extend(nsm_link_edges(pfx, ct))
    edges.extend(addr_fk_edges(pfx))
    edges.extend(inherited_nsm_link_edges(pfx))
    return edges


# ── Rule ───────────────────────────────────────────────────────
from netbox_nsm.models import (  # noqa: E402
    Rule,
    Rulebook,
    ObjectGroup,
    RuleObjectItem,
    ObjectGroupMember,
    ObjectLink,
)


@registry.register(Rule)
def _rule(rule):
    edges = []
    if rule.rulebook:
        edges.append(
            AnalyzerEdge("Rulebook", "in_rulebook", node_from_object(rule.rulebook))
        )
    for item in RuleObjectItem.objects.filter(rule=rule).select_related(
        "field", "content_type"
    )[:_MAX]:
        if item.assigned_object is not None:
            edges.append(
                AnalyzerEdge(
                    str(item.field),
                    item.field.slug,
                    node_from_object(item.assigned_object),
                )
            )
    return edges


# ── Rulebook ───────────────────────────────────────────────────
@registry.register(Rulebook)
def _rulebook(rb):
    edges = []
    for rule in rb.rules.all()[:_MAX]:
        edges.append(AnalyzerEdge("Regel", "has_rule", node_from_object(rule)))
    return edges


# ── ObjectGroup ──────────────────────────────────────────────────────
@registry.register(ObjectGroup)
def _object_group(grp):
    edges = []

    for sub in grp.sub_groups.all()[:_MAX]:
        edges.append(AnalyzerEdge("Sub-Group", "has_subgroup", node_from_object(sub)))

    for member in ObjectGroupMember.objects.filter(group=grp).select_related(
        "content_type"
    )[:_MAX]:
        if member.assigned_object is not None:
            edges.append(
                AnalyzerEdge(
                    "Member", "has_member", node_from_object(member.assigned_object)
                )
            )

    for slug in (grp.field_slugs or [])[:_MAX]:
        edges.append(AnalyzerEdge("Field", "in_field", slug))

    grp_ct = ContentType.objects.get_for_model(grp)
    edges.extend(policy_item_edges(grp, grp_ct))
    edges.extend(nsm_link_edges(grp, grp_ct))
    return edges


# ── Generic fallback (netbox_custom_objects + any unregistered model) ────────


def _generic_fallback(obj) -> list[AnalyzerEdge]:
    """Resolver for netbox_custom_objects Table*Models and any other unregistered type.

    Traverses:
    - Forward FK fields
    - Forward M2M fields (excluding tags)
    - group M2M members + reverse parent groups (Security Panel)
    - Reverse through-table M2M (netbox_custom_objects only)
    - Bidirectional ObjectLink
    - RuleObjectItem → deduplicated to Rulebook level
    """
    from netbox_nsm.models import RuleObjectItem

    ct = ContentType.objects.get_for_model(obj)
    edges = []

    # Forward FK fields
    for f in obj._meta.fields:
        if type(f).__name__ == "ForeignKey":
            related = getattr(obj, f.name, None)
            if related is not None:
                label = str(f.verbose_name).title() if f.verbose_name else f.name
                edges.append(AnalyzerEdge(label, f.name, node_from_object(related)))

    # Forward M2M fields (skip group — handled by group_m2m_edges below)
    for f in obj._meta.many_to_many:
        if f.name in ("tags", "group"):
            continue
        label = str(f.verbose_name).title() if f.verbose_name else f.name
        for rel in getattr(obj, f.name).all()[:25]:
            edges.append(AnalyzerEdge(label, f.name, node_from_object(rel)))

    # group M2M: members (forward) + parent groups (reverse) — Security Panel parity
    edges.extend(group_m2m_edges(obj))

    # Reverse through-table M2M (netbox_custom_objects):
    # The reverse M2M accessor has related_name='+' (not navigable via Python
    # attribute), so we query through-tables directly to find groups that
    # contain this object as a target.
    if obj._meta.app_label == "netbox_custom_objects":
        from django.apps import apps

        for m in apps.get_app_config("netbox_custom_objects").get_models():
            if "through" not in m.__name__.lower():
                continue
            try:
                tgt_fk = m._meta.get_field("target")
                src_fk = m._meta.get_field("source")
            except Exception:
                continue
            if tgt_fk.related_model is not type(obj):
                continue
            lbl = str(src_fk.related_model._meta.verbose_name).title()
            for row in m.objects.filter(target_id=obj.pk).select_related("source")[
                :_MAX
            ]:
                edges.append(
                    AnalyzerEdge(lbl, "member_of", node_from_object(row.source))
                )

    # Bidirectional ObjectLink
    edges.extend(nsm_link_edges(obj, ct))

    # Rulebooks that reference this object (deduplicated)
    seen_rb: dict = {}
    for item in RuleObjectItem.objects.filter(
        content_type=ct, object_id=obj.pk
    ).select_related("rule__rulebook")[:50]:
        rb = item.rule.rulebook if item.rule else None
        if rb and rb.pk not in seen_rb:
            seen_rb[rb.pk] = rb
    for rb in seen_rb.values():
        edges.append(AnalyzerEdge("Rulebook", "in_rulebook", node_from_object(rb)))

    return edges


registry.set_fallback(_generic_fallback)
