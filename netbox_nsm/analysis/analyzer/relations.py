"""
Edge resolvers for NetBox models.

Registered resolvers are called by ``registry.get_edges(obj)`` for known model
types. The catch-all ``_generic_fallback`` at the bottom handles everything
else (e.g. netbox_custom_objects Table*Models).

Import dependency:
    registry.py  ←  edge_sources.py  ←  relations.py
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from .all_edges import compose_all_edges
from .registry import (
    AnalyzerEdge,
    AnalyzerNode,
    node_from_object,
    registry,
)
# ── Device ──────────────────────────────────────────────────────────────────
from dcim.models import Device, Interface  # noqa: E402


@registry.register(Device)
def _device(device):
    return compose_all_edges(device)


# ── VirtualMachine ───────────────────────────────────────────────────────────
from virtualization.models import VirtualMachine, VMInterface  # noqa: E402


@registry.register(VirtualMachine)
def _vm(vm):
    return compose_all_edges(vm)


# ── Interface (dcim) ────────────────────────────────────────────────────────
@registry.register(Interface)
def _interface(iface):
    return compose_all_edges(iface)


# ── VMInterface ─────────────────────────────────────────────────────────────
@registry.register(VMInterface)
def _vminterface(iface):
    return compose_all_edges(iface)


# ── IPAddress ───────────────────────────────────────────────────────────────
from ipam.models import IPAddress, Prefix  # noqa: E402


@registry.register(IPAddress)
def _ipaddress(ip):
    extras: list[AnalyzerEdge] = []

    if ip.assigned_object:
        extras.append(
            AnalyzerEdge(
                "Assigned to", "assigned_to", node_from_object(ip.assigned_object)
            )
        )

    try:
        ip_str = str(ip.address).split("/")[0]
        matches = list(Prefix.objects.filter(prefix__net_contains=ip_str)[:10])
        matches.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
        if matches:
            extras.append(
                AnalyzerEdge("Subnet", "in_prefix", node_from_object(matches[0]))
            )
    except Exception:
        pass

    return compose_all_edges(ip, extras=extras)


# ── Prefix ──────────────────────────────────────────────────────────────────
@registry.register(Prefix)
def _prefix(pfx):
    extras: list[AnalyzerEdge] = []

    for ip in IPAddress.objects.filter(address__net_contained_or_equal=str(pfx.prefix)):
        extras.append(AnalyzerEdge("IP", "contains_ip", node_from_object(ip)))

    return compose_all_edges(pfx, extras=extras)


# ── Generic fallback (netbox_custom_objects + any unregistered model) ────────


def _generic_fallback(obj) -> list[AnalyzerEdge]:
    """Resolver for netbox_custom_objects Table*Models and any other unregistered type."""
    from netbox_nsm.security.cot_rule_references import scan_cot_security_references

    ct = ContentType.objects.get_for_model(obj)
    extras: list[AnalyzerEdge] = []

    seen_rb: dict = {}
    for match in scan_cot_security_references(ct, obj.pk):
        rb = match.get("rulebook")
        if rb is None:
            continue
        key = getattr(rb, "slug", None) or getattr(rb, "pk", None)
        if key is not None and key not in seen_rb:
            seen_rb[key] = rb
    for rb in seen_rb.values():
        extras.append(AnalyzerEdge("Rulebook", "in_rulebook", node_from_object(rb)))

    edges = compose_all_edges(obj, extras=extras)

    # Reverse through-table M2M (netbox_custom_objects only)
    if obj._meta.app_label == "netbox_custom_objects":
        from django.apps import apps

        seen: set[tuple[str, str]] = {(e.edge_label, e.node.id) for e in edges}
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
            for row in m.objects.filter(target_id=obj.pk).select_related("source"):
                key = (lbl, f"{ContentType.objects.get_for_model(row.source).pk}:{row.source.pk}")
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    AnalyzerEdge(lbl, "member_of", node_from_object(row.source))
                )

    return edges


registry.set_fallback(_generic_fallback)
