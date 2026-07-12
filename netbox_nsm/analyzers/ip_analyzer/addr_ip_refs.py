"""IPAM reference resolution for NSM address objects."""
from __future__ import annotations

from netbox_nsm.analyzers.ip_analyzer.addr_constants import (
    ADDR_IPAM_FK_FIELDS,
    ADDR_IPAM_FK_FIELDS_HOST,
    ADDR_IPAM_FK_FIELDS_SUBNET,
    FIELD_TYPE_LABELS,
    _ADDR_IPAM_FK_FIELDS,
    _ADDR_IPAM_FK_FIELDS_HOST,
    _ADDR_IPAM_FK_FIELDS_SUBNET,
    _FIELD_TYPE_LABELS,
)
import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub


def _extract_ip_refs(obj):
    """Return list of {display, url, type} for IP-relevant objects reachable from obj."""
    return _extract_ip_refs_visited(obj, set())



def _addr_has_direct_ip_address(obj) -> bool:
    try:
        return getattr(obj, "ip_address", None) is not None
    except Exception:
        return False


def _addr_has_direct_range(obj) -> bool:
    try:
        return getattr(obj, "range", None) is not None
    except Exception:
        return False


def _addr_ip_ref_field_order(obj):
    """Host/range objects compare by specific IP; subnet rows keep prefix drilldown."""
    if _addr_has_direct_ip_address(obj) or _addr_has_direct_range(obj):
        return _ADDR_IPAM_FK_FIELDS_HOST
    return _ADDR_IPAM_FK_FIELDS_SUBNET


def _ip_ref_dict(ipam_obj, field_name, *, ct_pk=None):
    """Build the standard IPAM ref payload shared by legacy FK and polymorphic GFK paths."""
    from django.contrib.contenttypes.models import ContentType

    if ct_pk is None:
        ct_pk = ContentType.objects.get_for_model(ipam_obj).pk
    return {
        "str": str(ipam_obj),
        "url": ipam_obj.get_absolute_url(),
        "type": _FIELD_TYPE_LABELS.get(field_name, field_name),
        "ct": ct_pk,
        "pk": ipam_obj.pk,
    }


def _addr_ip_ref_from_fields(obj, field_names):
    """Return {str, url, type, ct, pk} for the first populated IPAM FK in *field_names*."""
    for field_name in field_names:
        try:
            related = getattr(obj, field_name, None)
            if related is not None:
                return _ip_ref_dict(related, field_name)
        except Exception:
            pass
    return None


def _addr_ip_ref_from_polymorphic_fk(obj):
    """Resolve IPAM ref via polymorphic ``address`` GFK when legacy FKs are empty."""
    try:
        from netbox_nsm.addresses.address_ipam_fk import iter_address_ipam_fk_refs

        for fk_ref in iter_address_ipam_fk_refs(obj):
            return _ip_ref_dict(
                fk_ref.ipam_obj,
                fk_ref.field_name,
                ct_pk=fk_ref.ipam_ct.pk,
            )
    except Exception:
        pass
    return None


def _addr_ip_ref(obj):
    """Return the most appropriate IPAM ref for analysis (host IP before parent prefix)."""
    ref = _addr_ip_ref_from_fields(obj, _addr_ip_ref_field_order(obj))
    if ref is not None:
        return ref
    return _addr_ip_ref_from_polymorphic_fk(obj)


def _addr_ip_ref_node_dict(ip_ref):
    """Minimal ip_ref payload for address-tree nodes (includes loupe ct/pk when present)."""
    data = {"str": ip_ref["str"], "url": ip_ref["url"]}
    ref_type = ip_ref.get("type")
    if ref_type is not None:
        data["type"] = ref_type
    if ip_ref.get("ct") is not None and ip_ref.get("pk") is not None:
        data["ct"] = ip_ref["ct"]
        data["pk"] = ip_ref["pk"]
    return data


def _addr_group_members(obj):
    """Members contained in this nsm_addresses group (forward M2M on ``group``)."""
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return []
    try:
        return list(group_rel.all().order_by("name"))
    except Exception:
        try:
            return list(group_rel.all())
        except Exception:
            return []


def _addr_is_group_container(obj):
    """True when obj has no direct IP but contains other address objects."""
    if _addr_ip_ref(obj) is not None:
        return False
    if getattr(obj, "address_type", None) == "address-group":
        return True
    return bool(_addr_group_members(obj))


def _extract_ip_refs_visited(obj, visited=None):
    """Like _extract_ip_refs but accepts a visited set to avoid cycles in address groups."""
    if visited is None:
        visited = set()
    refs = []

    fd = getattr(obj, "field_data", None)
    if fd:
        for v in fd.values():
            if (
                isinstance(v, dict)
                and (v.get("str") or v.get("display"))
                and v.get("url")
            ):
                refs.append(
                    {
                        "display": v.get("display") or v.get("str"),
                        "url": v["url"],
                        "type": "",
                    }
                )
        return refs

    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            refs.append(
                {
                    "display": str(obj),
                    "url": obj.get_absolute_url(),
                    "type": obj._meta.verbose_name.capitalize(),
                }
            )
            return refs
    except Exception:
        pass

    ip_ref = _addr_ip_ref(obj)
    if ip_ref is None and _addr_is_group_container(obj):
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        for member in members:
            if member.pk not in visited:
                visited.add(member.pk)
                refs.extend(_extract_ip_refs_visited(member, visited))
        return refs

    if ip_ref is not None:
        refs.append(
            {
                "display": ip_ref["str"],
                "url": ip_ref["url"],
                "type": ip_ref["type"],
            }
        )

    return refs


def _addr_node_prefix_cidr(*, obj=None, ip_ref=None):
    """Return CIDR string for IPv4 IPAM prefixes and host addresses (e.g. /32)."""
    if ip_ref:
        ip_ref_type = ip_ref.get("type")
        cidr = ip_ref.get("str")
        if ip_ref_type == _FIELD_TYPE_LABELS["prefix"]:
            return cidr
        if ip_ref_type in (
            _FIELD_TYPE_LABELS["ip_address"],
            _FIELD_TYPE_LABELS["address"],
        ):
            if cidr and "/" in cidr:
                return cidr
        if not ip_ref_type and cidr and "/" in cidr:
            return cidr
        if cidr and "/" in cidr:
            try:
                import ipaddress

                net = ipaddress.ip_network(str(cidr).strip(), strict=False)
                if net.prefixlen < net.max_prefixlen:
                    return cidr
            except ValueError:
                pass
    if obj is not None:
        try:
            if obj._meta.app_label == "ipam":
                if obj._meta.model_name == "prefix":
                    prefix_val = getattr(obj, "prefix", None)
                    return str(prefix_val) if prefix_val is not None else str(obj)
                if obj._meta.model_name == "ipaddress":
                    addr = getattr(obj, "address", None)
                    cidr = str(addr) if addr is not None else str(obj)
                    if cidr and "/" in cidr:
                        return cidr
        except Exception:
            pass
        from netbox_nsm.addresses.address_literal import get_policy_address_cidr

        policy_cidr = get_policy_address_cidr(obj)
        if policy_cidr:
            return policy_cidr
    return None


def _attach_addr_node_prefix_display(node, *, obj=None, ip_ref=None):
    """Attach CIDR/netmask display labels to address-tree nodes for IPv4 prefixes/hosts."""
    from netbox_nsm.analyzers.ip_analyzer.addr_netmask import prefix_display_labels_for_cidr

    cidr = _addr_node_prefix_cidr(obj=obj, ip_ref=ip_ref)
    if not cidr:
        return node
    labels = prefix_display_labels_for_cidr(cidr)
    if labels:
        node["prefix_display_cidr"], node["prefix_display_netmask"] = labels
    return node


def _ipam_obj_from_ip_ref(ip_ref):
    """Load the IPAM object shown in the tree (matches ``ip_ref`` ct/pk)."""
    if not ip_ref:
        return None
    ct_id = ip_ref.get("ct")
    pk = ip_ref.get("pk")
    if ct_id is None or pk is None:
        return None
    try:
        from django.contrib.contenttypes.models import ContentType

        model = ContentType.objects.get(pk=int(ct_id)).model_class()
        if model is None:
            return None
        return model.objects.filter(pk=int(pk)).first()
    except Exception:
        return None


def _ipam_fk_object_for_addr_node(obj):
    # Direct IPAM ORM objects should resolve to themselves.
    try:
        meta = getattr(obj, "_meta", None)
        if meta and getattr(meta, "app_label", "") == "ipam":
            if getattr(meta, "model_name", "") in {"prefix", "iprange", "ipaddress"}:
                return obj
    except Exception:
        pass

    for field_name in _addr_ip_ref_field_order(obj):
        try:
            related = getattr(obj, field_name, None)
            # Ignore scalar helpers (e.g. Prefix.prefix -> netaddr.IPNetwork).
            if related is not None and getattr(related, "_meta", None) is not None:
                return related
        except Exception:
            pass
    try:
        from netbox_nsm.addresses.address_ipam_fk import iter_address_ipam_fk_refs

        for fk_ref in iter_address_ipam_fk_refs(obj):
            return fk_ref.ipam_obj
    except Exception:
        pass
    return None


