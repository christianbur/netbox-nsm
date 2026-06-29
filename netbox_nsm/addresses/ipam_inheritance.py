"""Shared logic: ancestor Prefix lookup and inherited NSM links for IPAM objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

__all__ = (
    "MAX_ANCESTOR_PREFIXES",
    "InheritedNsmLink",
    "ancestor_prefixes_for_ipam",
    "direct_nsm_type_keys_for_ipam",
    "iter_inherited_nsm_links",
    "nsm_address_q_for_ancestor",
    "should_include_inherited_type",
)

MAX_ANCESTOR_PREFIXES = 30


@dataclass(frozen=True)
class InheritedNsmLink:
    """One inherited NSM object resolved from a containing Prefix."""

    linked: object
    linked_ct: object
    type_key: str
    ancestor: object
    tc: object | None


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
            .order_by()
        )
        obj_prefixlen = obj.prefix.prefixlen
        candidates = [p for p in candidates if p.prefix.prefixlen < obj_prefixlen]
    else:
        return []

    candidates.sort(key=lambda p: p.prefix.prefixlen, reverse=True)
    return candidates[:MAX_ANCESTOR_PREFIXES]


def nsm_address_q_for_ancestor(addr_model, ancestor, _ipam_obj=None):
    """
    Q filter for nsm_addresses rows inherited via *ancestor* for the viewed
    IPAM object. Only addresses linked to the containing prefix are inherited;
    direct FK rows on the child IPAM object are shown as direct panel links.
    """
    from netbox_nsm.addresses.address_ipam_fk import addresses_for_ipam_object_queryset

    return addresses_for_ipam_object_queryset(addr_model, ancestor)


def direct_nsm_type_keys_for_ipam(ipam_obj, ipam_ct) -> set[str]:
    """Type keys of NSM object types directly linked to *ipam_obj*."""
    from netbox_nsm.objects.object_link_service import direct_nsm_type_keys_for_object

    return direct_nsm_type_keys_for_object(ipam_obj, ipam_ct)


def should_include_inherited_type(
    link,
    type_key: str,
    covered_type_keys: set[str],
    *,
    expected_propagation: str,
) -> bool:
    """Apply link propagation / propagate_stop_on_own."""
    from netbox_nsm.objects.link_propagation import should_propagate_inherited_link

    return should_propagate_inherited_link(
        link,
        type_key,
        covered_type_keys,
        expected_propagation=expected_propagation,
    )


def _type_config_map() -> dict:
    from netbox_nsm.objects.nsm_config import build_nsm_config_lookup

    return build_nsm_config_lookup()


def _linked_dedupe_key(linked, type_key: str) -> tuple:
    obj_url = linked.get_absolute_url() if hasattr(linked, "get_absolute_url") else "#"
    return type_key, obj_url


def iter_inherited_nsm_links(ipam_obj) -> Iterator[InheritedNsmLink]:
    """
    Yield NSM objects inherited from containing Prefixes for an IPAM object.

    Only COT ``nsm_object_link`` rows on ancestor Prefixes with IPAM inherit
    propagation are considered.
    """
    from ipam.models import IPAddress, IPRange, Prefix

    if not isinstance(ipam_obj, (IPAddress, IPRange, Prefix)):
        return

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import prefetch_related_objects

    from netbox_nsm.models.object_link import LinkPropagationChoices
    from netbox_nsm.objects.object_link_service import (
        ObjectLinkRecord,
        iter_links_on_container,
    )

    ancestor_prefixes = ancestor_prefixes_for_ipam(ipam_obj)
    if not ancestor_prefixes:
        return

    ipam_ct = ContentType.objects.get_for_model(ipam_obj)
    tc_map = _type_config_map()
    covered_type_keys = direct_nsm_type_keys_for_ipam(ipam_obj, ipam_ct)
    seen_dedupe_keys: set[tuple] = set()
    seen_group_type_keys: set[str] = set()

    def _yield_inherited(link, type_key, lct, linked, ancestor, tc):
        if not should_include_inherited_type(
            link,
            type_key,
            covered_type_keys,
            expected_propagation=LinkPropagationChoices.INHERIT_IPAM,
        ):
            return
        dedupe_key = _linked_dedupe_key(linked, type_key)
        if dedupe_key in seen_dedupe_keys:
            return
        seen_dedupe_keys.add(dedupe_key)
        if type_key not in seen_group_type_keys:
            seen_group_type_keys.add(type_key)
            covered_type_keys.add(type_key)
        yield InheritedNsmLink(
            linked=linked,
            linked_ct=lct,
            type_key=type_key,
            ancestor=ancestor,
            tc=tc,
        )

    for ancestor in ancestor_prefixes:
        raw_links = list(
            iter_links_on_container(
                ancestor, inherit_mode=LinkPropagationChoices.INHERIT_IPAM
            )
        )
        instances = [link.instance for link in raw_links if link.instance is not None]
        prefetch_related_objects(instances, "policy_object")
        for link in raw_links:
            linked = link.policy_object
            if linked is None:
                continue
            lct = ContentType.objects.get_for_model(linked)
            type_key = f"{lct.app_label}__{lct.model}"
            tc = tc_map.get(lct.pk)
            yield from _yield_inherited(link, type_key, lct, linked, ancestor, tc)

    try:
        from netbox_nsm.addresses.address_cot_schema import get_ipam_address_cot

        _addr_cot = get_ipam_address_cot()
        if _addr_cot:
            _AddrModel = _addr_cot.get_model()
            _addr_ct = ContentType.objects.get_for_model(_AddrModel)
            _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
            tc = tc_map.get(_addr_ct.pk)
            seen_addr_pks: set = set()
            for ancestor in ancestor_prefixes:
                inherit_links = [
                    link
                    for link in iter_links_on_container(
                        ancestor, inherit_mode=LinkPropagationChoices.INHERIT_IPAM
                    )
                    if link.policy_object is not None
                    and ContentType.objects.get_for_model(link.policy_object).pk
                    == _addr_ct.pk
                ]
                if not inherit_links:
                    continue
                stop_link = any(link.propagate_stop_on_own for link in inherit_links)
                if stop_link and _addr_type_key in covered_type_keys:
                    continue
                for _addr_obj in nsm_address_q_for_ancestor(
                    _AddrModel, ancestor, ipam_obj
                ):
                    if _addr_obj.pk in seen_addr_pks:
                        continue
                    seen_addr_pks.add(_addr_obj.pk)
                    pseudo_link = ObjectLinkRecord(
                        pk=0,
                        instance=None,
                        comment="",
                        propagation=LinkPropagationChoices.INHERIT_IPAM,
                        propagate_stop_on_own=stop_link,
                    )
                    yield from _yield_inherited(
                        pseudo_link,
                        _addr_type_key,
                        _addr_ct,
                        _addr_obj,
                        ancestor,
                        tc,
                    )
    except Exception:
        pass
