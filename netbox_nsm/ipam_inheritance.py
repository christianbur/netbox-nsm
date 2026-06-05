"""
Shared logic: ancestor Prefix lookup and inherited nsm_addresses for IPAM objects.
Used by InheritedLinksApiView and the object analyzer.
"""

from __future__ import annotations

__all__ = (
    "MAX_ANCESTOR_PREFIXES",
    "ancestor_prefixes_for_ipam",
    "nsm_address_q_for_ancestor",
)

MAX_ANCESTOR_PREFIXES = 30


def ancestor_prefixes_for_ipam(obj) -> list:
    """
    Return containing Prefixes for an IPAddress, IPRange, or child Prefix,
    most-specific first (longest prefix length).
    """
    from ipam.models import IPAddress, IPRange, Prefix

    if isinstance(obj, IPAddress):
        ip_str = str(obj.address).split("/")[0]
        candidates = list(
            Prefix.objects.filter(prefix__net_contains=ip_str).order_by()[
                :MAX_ANCESTOR_PREFIXES
            ]
        )
    elif isinstance(obj, IPRange):
        start_str = str(obj.start_address).split("/")[0]
        end_str = str(obj.end_address).split("/")[0]
        candidates = list(
            Prefix.objects.filter(prefix__net_contains=start_str)
            .filter(prefix__net_contains=end_str)
            .order_by()[:MAX_ANCESTOR_PREFIXES]
        )
    elif isinstance(obj, Prefix):
        ip_str = str(obj.prefix.ip)
        candidates = list(
            Prefix.objects.filter(prefix__net_contains=ip_str)
            .exclude(pk=obj.pk)
            .order_by()[:MAX_ANCESTOR_PREFIXES]
        )
    else:
        return []

    candidates.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
    return candidates


def nsm_address_q_for_ancestor(addr_model, ancestor, ipam_obj):
    """
    Q filter for nsm_addresses rows inherited via *ancestor* for the viewed
    IPAM object (prefix / ip_address / range FK fields).
    """
    from django.db.models import Q
    from ipam.models import IPAddress, IPRange, Prefix

    q = Q(prefix_id=ancestor.pk)
    if isinstance(ipam_obj, IPAddress):
        q |= Q(ip_address_id=ipam_obj.pk)
    elif isinstance(ipam_obj, IPRange):
        q |= Q(range_id=ipam_obj.pk)
    elif isinstance(ipam_obj, Prefix):
        q |= Q(prefix_id=ipam_obj.pk)
    return addr_model.objects.filter(q)
