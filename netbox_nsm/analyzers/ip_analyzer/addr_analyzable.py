
"""Analyzable-object checks for IP Analysis."""
from __future__ import annotations
import netbox_nsm.analyzers.ip_analyzer._lazy_api as _hub
from netbox_nsm.core.type_kind import is_address_content_type_id
from netbox_nsm.addresses.address_literal import is_literal_address
from netbox_nsm.type_metadata.specs import content_type_ids_for_cot_slugs

def _object_supports_addr_analysis(obj):
    """True when obj can be expanded as an address tree (group container or IP leaf)."""
    if _hub._addr_ip_ref(obj) is not None or _hub._addr_is_group_container(obj):
        return True
    if is_literal_address(obj):
        return True
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            return True
    except Exception:
        pass
    return False


def _object_is_addr_analyzable(obj, content_type_id, address_ct_ids=None):
    """True when content type is address-class and the object can be IP-analyzed."""
    if not obj or not content_type_id:
        return False
    if not _hub._object_supports_addr_analysis(obj):
        return False
    if _hub._is_ipam_addr_object(obj):
        return True
    if address_ct_ids is None:
        address_ct_ids = set(
            _hub.content_type_ids_for_cot_slugs(
                ["nsm_address", "nsm_address_custom", "nsm_address_group"]
            )
        )
    return is_address_content_type_id(content_type_id, cache=address_ct_ids)


