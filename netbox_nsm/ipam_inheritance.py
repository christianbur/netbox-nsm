"""
Shared logic: ancestor Prefix lookup and inherited NSM links for IPAM objects.
Used by InheritedLinksApiView and the object analyzer.
"""

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
        # For Prefix objects, only true parents may inherit to the child prefix.
        # Avoid child->parent inheritance when networks share the same base IP.
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
    return addr_model.objects.filter(prefix_id=ancestor.pk)


def direct_nsm_type_keys_for_ipam(ipam_obj, ipam_ct) -> set[str]:
    """Type keys of NSM object types directly linked to *ipam_obj*."""
    from netbox_nsm.models import ObjectLink

    covered_type_keys: set[str] = set()
    for link in ObjectLink.objects.filter(
        object_a_type=ipam_ct, object_a_id=ipam_obj.pk
    ).select_related("object_b_type"):
        lct = link.object_b_type
        covered_type_keys.add(f"{lct.app_label}__{lct.model}")
    for link in ObjectLink.objects.filter(
        object_b_type=ipam_ct, object_b_id=ipam_obj.pk
    ).select_related("object_a_type"):
        lct = link.object_a_type
        covered_type_keys.add(f"{lct.app_label}__{lct.model}")
    return covered_type_keys


def should_include_inherited_type(
    link,
    type_key: str,
    covered_type_keys: set[str],
    *,
    expected_propagation: str,
) -> bool:
    """Apply ObjectLink propagation / propagate_stop_on_own."""
    from netbox_nsm.link_propagation import should_propagate_inherited_link

    return should_propagate_inherited_link(
        link,
        type_key,
        covered_type_keys,
        expected_propagation=expected_propagation,
    )


def _type_config_map() -> dict:
    from netbox_nsm.models import TypeConfig

    return {
        tc.content_type_id: tc
        for tc in TypeConfig.objects.select_related("content_type").all()
    }


def _linked_dedupe_key(linked, type_key: str) -> tuple:
    obj_url = linked.get_absolute_url() if hasattr(linked, "get_absolute_url") else "#"
    return type_key, obj_url


def iter_inherited_nsm_links(ipam_obj) -> Iterator[InheritedNsmLink]:
    """
    Yield NSM objects inherited from containing Prefixes for an IPAM object.

    Only ObjectLinks on ancestor Prefixes with ``propagation=inherit_ipam`` are
    considered. ``propagate_stop_on_own`` on the parent link suppresses a type
    when the child already has a direct link of that type.
    """
    from ipam.models import IPAddress, IPRange, Prefix

    if not isinstance(ipam_obj, (IPAddress, IPRange, Prefix)):
        return

    from django.contrib.contenttypes.models import ContentType
    from django.db.models import prefetch_related_objects
    from netbox_nsm.models import ObjectLink

    ancestor_prefixes = ancestor_prefixes_for_ipam(ipam_obj)
    if not ancestor_prefixes:
        return

    ipam_ct = ContentType.objects.get_for_model(ipam_obj)
    tc_map = _type_config_map()
    covered_type_keys = direct_nsm_type_keys_for_ipam(ipam_obj, ipam_ct)
    prefix_ct = ContentType.objects.get_for_model(Prefix)
    seen_dedupe_keys: set[tuple] = set()
    seen_group_type_keys: set[str] = set()

    from netbox_nsm.models.object_link import LinkPropagationChoices

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
        for direction in ("fwd", "rev"):
            if direction == "fwd":
                qs_inh = list(
                    ObjectLink.objects.filter(
                        object_a_type=prefix_ct,
                        object_a_id=ancestor.pk,
                        propagation=LinkPropagationChoices.INHERIT_IPAM,
                    ).select_related("object_b_type")
                )
                prefetch_related_objects(qs_inh, "object_b")
            else:
                qs_inh = list(
                    ObjectLink.objects.filter(
                        object_b_type=prefix_ct,
                        object_b_id=ancestor.pk,
                        propagation=LinkPropagationChoices.INHERIT_IPAM,
                    ).select_related("object_a_type")
                )
                prefetch_related_objects(qs_inh, "object_a")

            for link in qs_inh:
                linked = link.object_b if direction == "fwd" else link.object_a
                if linked is None:
                    continue
                lct = link.object_b_type if direction == "fwd" else link.object_a_type
                type_key = f"{lct.app_label}__{lct.model}"
                tc = tc_map.get(lct.pk)
                yield from _yield_inherited(link, type_key, lct, linked, ancestor, tc)

    try:
        from netbox_custom_objects.models import CustomObjectType as _COT

        _addr_cot = _COT.objects.filter(slug="nsm_addresses").first()
        if _addr_cot:
            _AddrModel = _addr_cot.get_model()
            _addr_ct = ContentType.objects.get_for_model(_AddrModel)
            _addr_type_key = f"{_addr_ct.app_label}__{_addr_ct.model}"
            tc = tc_map.get(_addr_ct.pk)
            seen_addr_pks: set = set()
            for ancestor in ancestor_prefixes:
                has_inherit_addr = ObjectLink.objects.filter(
                    object_a_type=prefix_ct,
                    object_a_id=ancestor.pk,
                    propagation=LinkPropagationChoices.INHERIT_IPAM,
                    object_b_type=_addr_ct,
                ).exists()
                if not has_inherit_addr:
                    continue
                stop_link = ObjectLink.objects.filter(
                    object_a_type=prefix_ct,
                    object_a_id=ancestor.pk,
                    propagation=LinkPropagationChoices.INHERIT_IPAM,
                    object_b_type=_addr_ct,
                    propagate_stop_on_own=True,
                ).exists()
                if stop_link and _addr_type_key in covered_type_keys:
                    continue
                for _addr_obj in nsm_address_q_for_ancestor(
                    _AddrModel, ancestor, ipam_obj
                ):
                    if _addr_obj.pk in seen_addr_pks:
                        continue
                    seen_addr_pks.add(_addr_obj.pk)
                    pseudo_link = ObjectLink(
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
