"""Literal network values for ``nsm_address`` without an IPAM object.

Literal CIDR (e.g. ``0.0.0.0/0``) is stored in the object ``comments`` field as
``nsm_config`` YAML, not as a COT database field::

    nsm_config:
      - network: 0.0.0.0/0
"""

from __future__ import annotations

import ipaddress
import re

from django.core.exceptions import ValidationError

__all__ = (
    "ALLOWED_NETWORK_LITERALS",
    "attach_literal_prefix_display",
    "format_network_nsm_config_comments",
    "get_network_literal",
    "get_policy_address_cidr",
    "has_address_ipam_link",
    "is_literal_address",
    "merge_network_into_instance_comments",
    "parse_network_from_instance_comments",
    "validate_address_fields",
)

ALLOWED_NETWORK_LITERALS = frozenset({"0.0.0.0/0"})

_PLAIN_CIDR_RE = re.compile(
    r"^\s*((?:\d{1,3}\.){3}\d{1,3}/\d{1,2})\s*$"
)


def _load_yaml_document(text: str):
    import yaml

    return yaml.safe_load(text or "")


def _extract_nsm_config_list(document) -> list | None:
    if not isinstance(document, dict):
        return None
    raw = document.get("nsm_config")
    if isinstance(raw, list):
        return raw
    return None


def _network_from_nsm_config_list(raw_list: list | None) -> str | None:
    if not raw_list:
        return None
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        if len(entry) == 1 and "network" in entry:
            value = entry.get("network")
        elif "network" in entry:
            value = entry.get("network")
        else:
            continue
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def parse_network_from_instance_comments(text: str) -> str | None:
    """Return literal network CIDR from ``comments`` ``nsm_config`` YAML."""
    raw_list = _extract_nsm_config_list(_load_yaml_document(text))
    return _network_from_nsm_config_list(raw_list)


def _legacy_plain_cidr_in_comments(text: str) -> str | None:
    """Detect legacy plain-CIDR comments (pre-nsm_config demo imports)."""
    if not text or "nsm_config" in text:
        return None
    match = _PLAIN_CIDR_RE.match(text)
    if not match:
        return None
    return match.group(1)


def merge_network_into_instance_comments(
    existing_comments: str,
    network: str | None,
) -> str:
    """Merge or remove the ``network`` segment in instance ``comments`` YAML."""
    import yaml

    document = _load_yaml_document(existing_comments)
    if not isinstance(document, dict):
        document = {}

    raw_list = _extract_nsm_config_list(document) or []
    kept = [
        entry
        for entry in raw_list
        if not (
            isinstance(entry, dict)
            and ("network" in entry or (len(entry) == 1 and "network" in entry))
        )
    ]
    if network:
        kept.append({"network": network})
    if kept:
        document["nsm_config"] = kept
    else:
        document.pop("nsm_config", None)

    if not document:
        return ""
    return (
        yaml.dump(
            document,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )


def format_network_nsm_config_comments(network: str) -> str:
    """Return canonical ``comments`` YAML for a literal-only address object."""
    return merge_network_into_instance_comments("", network)


def get_network_literal(addr_obj) -> str | None:
    """Return stripped literal network CIDR from ``comments`` ``nsm_config``."""
    if addr_obj is None:
        return None

    comments = getattr(addr_obj, "comments", None)
    if comments:
        network = parse_network_from_instance_comments(str(comments))
        if network:
            return network
        legacy_plain = _legacy_plain_cidr_in_comments(str(comments))
        if legacy_plain:
            return legacy_plain

    # Transitional: field may still exist until schema sync drops the column.
    value = getattr(addr_obj, "network_literal", None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def has_address_ipam_link(addr_obj) -> bool:
    from netbox_nsm.addresses.address_ipam_fk import iter_address_ipam_fk_refs

    return bool(list(iter_address_ipam_fk_refs(addr_obj)))


def get_policy_address_cidr(addr_obj) -> str | None:
    """Return manual CIDR from ``nsm_address_custom`` or legacy comments literal."""
    from netbox_nsm.addresses.address_custom import (
        get_custom_address_cidr,
        is_nsm_address_custom_object,
    )

    if is_nsm_address_custom_object(addr_obj):
        return get_custom_address_cidr(addr_obj)
    return get_network_literal(addr_obj)


def is_literal_address(addr_obj) -> bool:
    return get_policy_address_cidr(addr_obj) is not None


def _normalize_literal(cidr: str) -> str:
    try:
        return str(ipaddress.ip_network(cidr, strict=False))
    except ValueError as exc:
        raise ValidationError({"comments": f"Invalid network: {cidr}"}) from exc


def validate_address_fields(addr_obj) -> None:
    """
    Require exactly one of IPAM ``address`` or literal ``network`` in ``comments``.

    Literal ``network`` is restricted to documented special cases (currently
    IPv4 ``0.0.0.0/0``) and must be stored as ``nsm_config`` in ``comments``.
    """
    literal = get_network_literal(addr_obj)
    has_ipam = has_address_ipam_link(addr_obj)

    if literal and has_ipam:
        raise ValidationError(
            "An address object cannot set both an IPAM address and a literal network."
        )
    if not literal and not has_ipam:
        raise ValidationError(
            "Either an IPAM address (prefix, IP, or range) or a literal network "
            "(nsm_config.network in comments) is required."
        )
    if not literal:
        return

    normalized = _normalize_literal(literal)
    if normalized not in ALLOWED_NETWORK_LITERALS:
        allowed = ", ".join(sorted(ALLOWED_NETWORK_LITERALS))
        raise ValidationError(
            {
                "comments": (
                    f"Unsupported literal network {literal!r}. "
                    f"Allowed values: {allowed}."
                )
            }
        )


def attach_literal_prefix_display(node, obj) -> dict:
    """Attach CIDR display labels from literal ``network`` when no IPAM ref exists."""
    if node.get("ip_ref") or not obj:
        return node
    literal = get_policy_address_cidr(obj)
    if not literal:
        return node
    from netbox_nsm.analyzers.ip_analyzer.addr_netmask import sync_prefix_display_netmask

    node["prefix_display_cidr"] = literal
    sync_prefix_display_netmask(node)
    return node
