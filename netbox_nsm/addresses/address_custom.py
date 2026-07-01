"""Manual IPv4/IPv6 + prefix-length addresses without IPAM (``nsm_address_custom``)."""

from __future__ import annotations

import ipaddress

from django.core.exceptions import ValidationError

__all__ = (
    "NSM_ADDRESS_CUSTOM_SLUG",
    "get_custom_address_cidr",
    "is_nsm_address_custom_object",
    "validate_custom_address_fields",
)

NSM_ADDRESS_CUSTOM_SLUG = "nsm_address_custom"


def is_nsm_address_custom_object(obj) -> bool:
    if obj is None:
        return False
    cot = getattr(obj, "custom_object_type", None)
    if cot is not None and getattr(cot, "slug", None) == NSM_ADDRESS_CUSTOM_SLUG:
        return True
    return getattr(obj._meta, "model_name", "") == NSM_ADDRESS_CUSTOM_SLUG


def _field_text(obj, name: str) -> str:
    value = getattr(obj, name, None)
    if value is None:
        return ""
    return str(value).strip()


def _field_subnet(obj) -> int | None:
    value = getattr(obj, "subnet", None)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({"subnet": "Prefix length must be an integer."}) from exc


def get_custom_address_cidr(obj) -> str | None:
    """Return normalized CIDR from ``ipv4``/``ipv6`` + ``subnet``, or ``None``."""
    if not is_nsm_address_custom_object(obj):
        return None

    ipv4 = _field_text(obj, "ipv4")
    ipv6 = _field_text(obj, "ipv6")
    prefix_len = _field_subnet(obj)

    if prefix_len is None:
        return None

    if ipv4 and ipv6:
        return None
    if not ipv4 and not ipv6:
        return None

    try:
        if ipv4:
            addr = ipaddress.IPv4Address(ipv4)
            max_len = 32
        else:
            addr = ipaddress.IPv6Address(ipv6)
            max_len = 128
        if prefix_len < 0 or prefix_len > max_len:
            return None
        return str(ipaddress.ip_network(f"{addr}/{prefix_len}", strict=False))
    except ValueError:
        return None


def validate_custom_address_fields(obj) -> None:
    """Require exactly one of ``ipv4``/``ipv6`` and a valid ``subnet`` (0–32 / 0–128)."""
    ipv4 = _field_text(obj, "ipv4")
    ipv6 = _field_text(obj, "ipv6")

    if ipv4 and ipv6:
        raise ValidationError("Set either IPv4 or IPv6, not both.")
    if not ipv4 and not ipv6:
        raise ValidationError("Either IPv4 or IPv6 is required.")

    prefix_len = _field_subnet(obj)
    if prefix_len is None:
        raise ValidationError({"subnet": "Prefix length is required."})

    family = "IPv4" if ipv4 else "IPv6"
    max_len = 32 if ipv4 else 128
    field_name = "ipv4" if ipv4 else "ipv6"
    raw_addr = ipv4 or ipv6

    try:
        if ipv4:
            ipaddress.IPv4Address(raw_addr)
        else:
            ipaddress.IPv6Address(raw_addr)
    except ValueError as exc:
        raise ValidationError({field_name: f"Invalid {family} address: {raw_addr!r}."}) from exc

    if prefix_len < 0 or prefix_len > max_len:
        raise ValidationError(
            {"subnet": f"Prefix length must be between 0 and {max_len} for {family}."}
        )

    try:
        ipaddress.ip_network(f"{raw_addr}/{prefix_len}", strict=False)
    except ValueError as exc:
        raise ValidationError(
            {field_name: f"Invalid {family} network {raw_addr}/{prefix_len}."}
        ) from exc
