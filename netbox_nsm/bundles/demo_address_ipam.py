"""Assign demo IPAM prefixes and host IPs to ``nsm_address`` seed objects."""

from __future__ import annotations

import random

__all__ = (
    "DEMO_ADDR_HOST_NAME_PREFIX",
    "DEMO_ADDR_IPAM_HOST_RATIO",
    "DEMO_ADDR_IPAM_SEED",
    "demo_address_names_from_bundle",
    "seed_demo_address_ipam",
)

DEMO_ADDR_HOST_NAME_PREFIX = "demo-addr-host-"
DEMO_ADDR_IPAM_OCTET1 = 10
DEMO_ADDR_IPAM_OCTET2 = 199
DEMO_ADDR_IPAM_SEED = 42
DEMO_ADDR_IPAM_HOST_RATIO = 0.65
_PREFIX_LENGTHS = (24, 25, 26, 28)


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


def _demo_ipam_prefix_description(addr_name: str, cidr: str) -> str:
    return f"Demo prefix {cidr} ({addr_name})"


def _apply_demo_ipam_metadata(ipam_obj, *, addr_name: str):
    """Ensure demo IPAM rows expose dns_name/description for the IPA cell tree."""
    from ipam.models import IPAddress, Prefix

    if isinstance(ipam_obj, IPAddress):
        ipam_obj.dns_name = _demo_ipam_host_dns_name(addr_name)
        ipam_obj.description = _demo_ipam_host_description(addr_name)
        ipam_obj.save(update_fields=["dns_name", "description"])
    elif isinstance(ipam_obj, Prefix):
        ipam_obj.description = _demo_ipam_prefix_description(
            addr_name, str(ipam_obj.prefix)
        )
        ipam_obj.save(update_fields=["description"])


def _get_or_create_prefix(cidr: str, *, addr_name: str):
    from ipam.models import Prefix

    existing = Prefix.objects.filter(prefix=cidr).order_by("pk").first()
    if existing is not None:
        _apply_demo_ipam_metadata(existing, addr_name=addr_name)
        return existing
    prefix = Prefix.objects.create(prefix=cidr, status="active")
    _apply_demo_ipam_metadata(prefix, addr_name=addr_name)
    return prefix


def _get_or_create_ipaddress(cidr: str, *, addr_name: str):
    from ipam.models import IPAddress

    existing = IPAddress.objects.filter(address=cidr).order_by("pk").first()
    if existing is not None:
        _apply_demo_ipam_metadata(existing, addr_name=addr_name)
        return existing
    ip_address = IPAddress.objects.create(address=cidr, status="active")
    _apply_demo_ipam_metadata(ip_address, addr_name=addr_name)
    return ip_address


def seed_demo_address_ipam(*, names: list[str] | None = None) -> int:
    """Link each demo ``nsm_address`` row to a random IPAM host or prefix."""
    from django.contrib.contenttypes.models import ContentType
    from ipam.models import IPAddress, Prefix

    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.filter(slug="nsm_address").first()
    if cot is None:
        return 0

    model = cot.get_model()
    if names:
        queryset = model.objects.filter(name__in=names).order_by("name")
    else:
        queryset = model.objects.filter(
            name__startswith=DEMO_ADDR_HOST_NAME_PREFIX
        ).order_by("name")

    ip_ct_id = ContentType.objects.get_for_model(IPAddress).pk
    prefix_ct_id = ContentType.objects.get_for_model(Prefix).pk

    linked = 0
    for host_index, addr_obj in enumerate(queryset):
        rng = random.Random(DEMO_ADDR_IPAM_SEED + host_index * 991)
        if rng.random() < DEMO_ADDR_IPAM_HOST_RATIO:
            ipam_obj = _get_or_create_ipaddress(
                _host_cidr(host_index), addr_name=addr_obj.name
            )
            ct_id = ip_ct_id
        else:
            ipam_obj = _get_or_create_prefix(
                _prefix_cidr(host_index, rng), addr_name=addr_obj.name
            )
            ct_id = prefix_ct_id

        addr_obj.address_content_type_id = ct_id
        addr_obj.address_object_id = ipam_obj.pk
        addr_obj.save(
            update_fields=["address_content_type_id", "address_object_id"]
        )
        linked += 1
    return linked
