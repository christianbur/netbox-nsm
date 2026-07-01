"""IPAM → NSM status mapping for object report checks."""

from __future__ import annotations

__all__ = (
    "BUILDER_IGNORE_STATUS",
    "DEFAULT_IPAM_STATUS_MAP",
    "DEPRECATED_OBJECT_STATUS",
    "map_ipam_status",
)

BUILDER_IGNORE_STATUS = "ignore"
DEPRECATED_OBJECT_STATUS = "deprecated"

DEFAULT_IPAM_STATUS_MAP = {
    "active": "active",
    "reserved": "reserved",
    "deprecated": "deprecated",
    "dhcp": BUILDER_IGNORE_STATUS,
    "slaac": BUILDER_IGNORE_STATUS,
    "container": BUILDER_IGNORE_STATUS,
}


def map_ipam_status(ipam_status_value: str | None, status_map: dict[str, str] | None = None) -> str | None:
    """Map an IPAM status string to an NSM address status (or ``ignore``)."""
    mapping = status_map or DEFAULT_IPAM_STATUS_MAP
    if ipam_status_value is None:
        return None
    key = str(ipam_status_value).strip().lower()
    if not key:
        return None
    mapped = mapping.get(key)
    if mapped is None:
        return None
    if mapped == BUILDER_IGNORE_STATUS:
        return None
    return mapped
