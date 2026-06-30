"""Shared constants for address / IP analysis."""

from __future__ import annotations

FIELD_TYPE_LABELS = {
    "address": "Address",
    "prefix": "Prefix",
    "ip_address": "IP Address",
    "range": "Range",
}
ADDR_IPAM_FK_FIELDS = ("prefix", "ip_address", "range")
ADDR_IPAM_FK_FIELDS_HOST = ("ip_address", "range", "prefix")
ADDR_IPAM_FK_FIELDS_SUBNET = ("prefix", "ip_address", "range")

# Backward-compatible aliases (tests / legacy imports).
_FIELD_TYPE_LABELS = FIELD_TYPE_LABELS
_ADDR_IPAM_FK_FIELDS = ADDR_IPAM_FK_FIELDS
_ADDR_IPAM_FK_FIELDS_HOST = ADDR_IPAM_FK_FIELDS_HOST
_ADDR_IPAM_FK_FIELDS_SUBNET = ADDR_IPAM_FK_FIELDS_SUBNET

__all__ = (
    "ADDR_IPAM_FK_FIELDS",
    "ADDR_IPAM_FK_FIELDS_HOST",
    "ADDR_IPAM_FK_FIELDS_SUBNET",
    "FIELD_TYPE_LABELS",
    "_ADDR_IPAM_FK_FIELDS",
    "_ADDR_IPAM_FK_FIELDS_HOST",
    "_ADDR_IPAM_FK_FIELDS_SUBNET",
    "_FIELD_TYPE_LABELS",
)
