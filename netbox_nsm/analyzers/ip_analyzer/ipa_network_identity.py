"""Canonical IP/prefix/range identity helpers for IPA comparisons."""

from __future__ import annotations

import ipaddress
import re


def host_network_from_value(value):
    """Return canonical host network (/32 or /128) parsed from *value*."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if "/" in text:
            host = ipaddress.ip_interface(text).ip
        else:
            host = ipaddress.ip_address(text)
    except ValueError:
        return None
    return ipaddress.ip_network(f"{host}/{host.max_prefixlen}", strict=False)


def network_from_value(value):
    """Return ip_network parsed from *value* (or None)."""
    if value is None:
        return None
    try:
        return ipaddress.ip_network(str(value).strip(), strict=False)
    except ValueError:
        return None


def range_identity(value):
    """Return canonical range identity tuple (version, start_int, end_int)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"^(.+?)\s*[\-–]\s*(.+)$", text)
    if not match:
        return None
    try:
        start = ipaddress.ip_address(match.group(1).strip())
        end = ipaddress.ip_address(match.group(2).strip())
    except ValueError:
        return None
    if start.version != end.version:
        return None
    start_int = int(start)
    end_int = int(end)
    if start_int > end_int:
        start_int, end_int = end_int, start_int
    return (start.version, start_int, end_int)


def value_identity(value):
    """Return canonical identity for networks/ranges suitable for equality checks."""
    net = network_from_value(value)
    if net is not None:
        return ("net", net.version, int(net.network_address), net.prefixlen)
    range_key = range_identity(value)
    if range_key is not None:
        return ("range",) + range_key
    return None


def values_equal(left, right):
    """True when *left* and *right* represent the same endpoint set."""
    left_key = value_identity(left)
    right_key = value_identity(right)
    if left_key is None or right_key is None:
        return False
    if left_key[0] == right_key[0]:
        return left_key == right_key

    # Cross-type equality: single-host range equals host network (/32 or /128).
    range_key = left_key if left_key[0] == "range" else right_key
    net_key = right_key if left_key[0] == "range" else left_key
    _, range_version, start_int, end_int = range_key
    _, net_version, net_addr_int, net_prefixlen = net_key
    if range_version != net_version or start_int != end_int:
        return False
    host_prefixlen = 32 if net_version == 4 else 128
    return net_prefixlen == host_prefixlen and net_addr_int == start_int
