"""IPv4 prefix → dotted-decimal netmask helpers for address analysis UI."""

from __future__ import annotations

import ipaddress


def ipv4_prefix_length_to_netmask(prefix_len: int) -> str | None:
    """Convert an IPv4 prefix length (0–32) to dotted-decimal netmask notation."""
    if prefix_len < 0 or prefix_len > 32:
        return None
    mask = (0xFFFFFFFF << (32 - prefix_len)) & 0xFFFFFFFF
    return ".".join(str((mask >> (8 * i)) & 0xFF) for i in range(3, -1, -1))


def ipv4_netmask_for_cidr(cidr: str) -> str | None:
    """Return dotted-decimal netmask for IPv4 CIDR strings; None for IPv6 or invalid input."""
    if not cidr or "/" not in cidr:
        return None
    try:
        network = ipaddress.ip_network(str(cidr).strip(), strict=False)
    except ValueError:
        return None
    if network.version != 4:
        return None
    return ipv4_prefix_length_to_netmask(network.prefixlen)


def sync_prefix_display_netmask(node):
    """Ensure ``prefix_display_netmask`` exists when ``prefix_display_cidr`` is IPv4."""
    if not isinstance(node, dict):
        return node
    cidr = node.get("prefix_display_cidr")
    if not cidr or node.get("prefix_display_netmask"):
        return node
    labels = prefix_display_labels_for_cidr(cidr)
    if labels:
        node["prefix_display_cidr"], node["prefix_display_netmask"] = labels
    return node


def prefix_display_labels_for_cidr(cidr: str) -> tuple[str, str] | None:
    """Return (cidr, host netmask) label pair for IPv4 prefix display toggling."""
    if not cidr or "/" not in cidr:
        return None
    netmask = ipv4_netmask_for_cidr(cidr)
    if not netmask:
        return None
    host = cidr.split("/", 1)[0]
    return cidr, f"{host}/{netmask}"
