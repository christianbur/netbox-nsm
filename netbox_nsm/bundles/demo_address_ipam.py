"""Assign demo IPAM prefixes and host IPs to ``nsm_address`` seed objects."""

from __future__ import annotations

import random
from dataclasses import dataclass

__all__ = (
    "DEMO_ADDR_HOST_NAME_PREFIX",
    "DEMO_ADDR_IPAM_HOST_RATIO",
    "DEMO_ADDR_IPAM_SEED",
    "DEMO_IPA_HIERARCHY",
    "DEMO_IPA_HIERARCHY_ADDR_NAMES",
    "demo_address_names_from_bundle",
    "seed_demo_address_ipam",
)

DEMO_ADDR_HOST_NAME_PREFIX = "demo-addr-host-"
DEMO_IPA_ADDR_NAME_PREFIX = "demo-ipa-"
DEMO_ADDR_IPAM_OCTET1 = 10
DEMO_ADDR_IPAM_OCTET2 = 199
DEMO_ADDR_IPAM_SEED = 42
DEMO_ADDR_IPAM_HOST_RATIO = 0.65
_PREFIX_LENGTHS = (24, 25, 26, 28)


@dataclass(frozen=True)
class DemoIpaHierarchyLevel:
    """One NSM/IPAM level in the 4-deep IPA demo tree."""

    addr_name: str
    label: str
    cidr: str
    kind: str  # "prefix" | "host"


# Continent → Country → City → Host (4 IPAM hierarchy levels for IPA testing).
DEMO_IPA_HIERARCHY: tuple[DemoIpaHierarchyLevel, ...] = (
    DemoIpaHierarchyLevel(
        "demo-ipa-continent",
        "Europa",
        "10.210.0.0/16",
        "prefix",
    ),
    DemoIpaHierarchyLevel(
        "demo-ipa-country",
        "Deutschland",
        "10.210.1.0/24",
        "prefix",
    ),
    DemoIpaHierarchyLevel(
        "demo-ipa-city",
        "Berlin",
        "10.210.1.64/26",
        "prefix",
    ),
    DemoIpaHierarchyLevel(
        "demo-ipa-host",
        "berlin-web",
        "10.210.1.70/32",
        "host",
    ),
)

DEMO_IPA_HIERARCHY_ADDR_NAMES: frozenset[str] = frozenset(
    level.addr_name for level in DEMO_IPA_HIERARCHY
)


def demo_address_names_from_bundle(bundle: dict) -> list[str]:
    """Return demo host names from bundle ``objects`` when present."""
    for entry in bundle.get("objects") or []:
        if not isinstance(entry, dict) or entry.get("type") != "nsm_address":
            continue
        names = [
            str(record.get("name", "")).strip()
            for record in entry.get("records") or []
            if isinstance(record, dict) and str(record.get("name", "")).strip()
        ]
        if names and names[0].startswith(DEMO_ADDR_HOST_NAME_PREFIX):
            return names
    return []


def _host_cidr(host_index: int) -> str:
    third = host_index // 256
    fourth = host_index % 256
    host_octet = (host_index % 253) + 1
    return (
        f"{DEMO_ADDR_IPAM_OCTET1}.{DEMO_ADDR_IPAM_OCTET2 + third}."
        f"{fourth}.{host_octet}/32"
    )


def _prefix_cidr(host_index: int, rng: random.Random) -> str:
    third = host_index // 256
    fourth = host_index % 256
    prefix_len = rng.choice(_PREFIX_LENGTHS)
    return (
        f"{DEMO_ADDR_IPAM_OCTET1}.{DEMO_ADDR_IPAM_OCTET2 + third}."
        f"{fourth}.0/{prefix_len}"
    )


def _demo_ipam_host_dns_name(addr_name: str) -> str:
    return f"{addr_name}.demo.local"


def _demo_ipam_host_description(addr_name: str) -> str:
    return f"Demo host {addr_name}"


def _demo_ipam_prefix_description(addr_name: str, cidr: str, *, label: str = "") -> str:
    if label:
        return f"Demo IPA hierarchy {label} ({cidr})"
    return f"Demo prefix {cidr} ({addr_name})"


def _apply_demo_ipam_metadata(
    ipam_obj,
    *,
    addr_name: str,
    label: str = "",
):
    """Ensure demo IPAM rows expose dns_name/description for the IPA cell tree."""
    from ipam.models import IPAddress, Prefix

    if isinstance(ipam_obj, IPAddress):
        ipam_obj.dns_name = _demo_ipam_host_dns_name(addr_name)
        ipam_obj.description = _demo_ipam_host_description(addr_name)
        if label:
            ipam_obj.description = f"Demo IPA hierarchy host {label} ({addr_name})"
        ipam_obj.save(update_fields=["dns_name", "description"])
    elif isinstance(ipam_obj, Prefix):
        ipam_obj.description = _demo_ipam_prefix_description(
            addr_name, str(ipam_obj.prefix), label=label
        )
        ipam_obj.save(update_fields=["description"])


def _get_or_create_prefix(cidr: str, *, addr_name: str, label: str = ""):
    from ipam.models import Prefix

    existing = Prefix.objects.filter(prefix=cidr).order_by("pk").first()
    if existing is not None:
        _apply_demo_ipam_metadata(existing, addr_name=addr_name, label=label)
        return existing
    prefix = Prefix.objects.create(prefix=cidr, status="active")
    _apply_demo_ipam_metadata(prefix, addr_name=addr_name, label=label)
    return prefix


def _get_or_create_ipaddress(cidr: str, *, addr_name: str, label: str = ""):
    from ipam.models import IPAddress

    existing = IPAddress.objects.filter(address=cidr).order_by("pk").first()
    if existing is not None:
        _apply_demo_ipam_metadata(existing, addr_name=addr_name, label=label)
        return existing
    ip_address = IPAddress.objects.create(address=cidr, status="active")
    _apply_demo_ipam_metadata(ip_address, addr_name=addr_name, label=label)
    return ip_address


def _link_address_to_ipam(addr_obj, ipam_obj, *, ip_ct_id: int, prefix_ct_id: int) -> None:
    from ipam.models import IPAddress

    ct_id = ip_ct_id if isinstance(ipam_obj, IPAddress) else prefix_ct_id
    addr_obj.address_content_type_id = ct_id
    addr_obj.address_object_id = ipam_obj.pk
    addr_obj.save(update_fields=["address_content_type_id", "address_object_id"])


def seed_demo_ipa_hierarchy_ipam(*, names: frozenset[str] | None = None) -> int:
    """Create nested IPAM prefixes/host and link ``demo-ipa-*`` addresses."""
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import IPAddress, Prefix

    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.filter(slug="nsm_address").first()
    if cot is None:
        return 0

    target_names = names or DEMO_IPA_HIERARCHY_ADDR_NAMES
    if not target_names:
        return 0

    model = cot.get_model()
    addr_by_name = {
        obj.name: obj
        for obj in model.objects.filter(name__in=target_names)
    }
    if not addr_by_name:
        return 0

    ip_ct_id = ContentType.objects.get_for_model(IPAddress).pk
    prefix_ct_id = ContentType.objects.get_for_model(Prefix).pk

    linked = 0
    for level in DEMO_IPA_HIERARCHY:
        if level.addr_name not in target_names:
            continue
        addr_obj = addr_by_name.get(level.addr_name)
        if addr_obj is None:
            continue
        if level.kind == "host":
            ipam_obj = _get_or_create_ipaddress(
                level.cidr, addr_name=level.addr_name, label=level.label
            )
        else:
            ipam_obj = _get_or_create_prefix(
                level.cidr,
                addr_name=level.addr_name,
                label=level.label,
            )
        _link_address_to_ipam(
            addr_obj,
            ipam_obj,
            ip_ct_id=ip_ct_id,
            prefix_ct_id=prefix_ct_id,
        )
        linked += 1
    return linked


def seed_demo_address_ipam(*, names: list[str] | None = None) -> int:
    """Link demo ``nsm_address`` rows to IPAM (hierarchy tree + random hosts)."""
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import IPAddress, Prefix

    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.filter(slug="nsm_address").first()
    if cot is None:
        return 0

    model = cot.get_model()
    hierarchy_linked = seed_demo_ipa_hierarchy_ipam()
    if names:
        host_names = [
            name
            for name in names
            if name.startswith(DEMO_ADDR_HOST_NAME_PREFIX)
            and name not in DEMO_IPA_HIERARCHY_ADDR_NAMES
        ]
        queryset = model.objects.filter(name__in=host_names).order_by("name")
    else:
        queryset = model.objects.filter(
            name__startswith=DEMO_ADDR_HOST_NAME_PREFIX
        ).order_by("name")

    ip_ct_id = ContentType.objects.get_for_model(IPAddress).pk
    prefix_ct_id = ContentType.objects.get_for_model(Prefix).pk

    linked = hierarchy_linked
    for host_index, addr_obj in enumerate(queryset):
        rng = random.Random(DEMO_ADDR_IPAM_SEED + host_index * 991)
        if rng.random() < DEMO_ADDR_IPAM_HOST_RATIO:
            ipam_obj = _get_or_create_ipaddress(
                _host_cidr(host_index), addr_name=addr_obj.name
            )
        else:
            ipam_obj = _get_or_create_prefix(
                _prefix_cidr(host_index, rng), addr_name=addr_obj.name
            )
        _link_address_to_ipam(
            addr_obj,
            ipam_obj,
            ip_ct_id=ip_ct_id,
            prefix_ct_id=prefix_ct_id,
        )
        linked += 1
    return linked
