"""
Forward IPAM FK references on ``nsm_addresses`` custom objects.

Reverse lookup (IPAM object → addresses) lives in ``template_content`` and
``analyzer._helpers.addr_fk_edges``; this module covers address → IPAM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

__all__ = (
    "NSM_ADDRESSES_SLUG",
    "AddressIpamFkRef",
    "get_nsm_address_model",
    "is_nsm_address_object",
    "iter_address_ipam_fk_refs",
    "panel_link_type_for_address_ipam_fk",
    "fk_field_name_from_filter",
)

NSM_ADDRESSES_SLUG = "nsm_addresses"

_FK_FIELDS = (
    ("prefix", "prefix_id"),
    ("ip_address", "ip_address_id"),
    ("range", "range_id"),
)

_FK_FILTER_TO_FIELD = {fk_attr: field_name for field_name, fk_attr in _FK_FIELDS}


@dataclass(frozen=True)
class AddressIpamFkRef:
    """One IPAM object referenced by an ``nsm_addresses`` row."""

    ipam_obj: object
    ipam_ct: object
    field_name: str


def get_nsm_address_model():
    """Return the dynamic ``nsm_addresses`` model class, or ``None``."""
    try:
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(slug=NSM_ADDRESSES_SLUG).first()
        if cot is None:
            return None
        return cot.get_model()
    except Exception:
        return None


def is_nsm_address_object(obj, addr_model=None) -> bool:
    if obj is None:
        return False
    cot = getattr(obj, "custom_object_type", None)
    if cot is not None and getattr(cot, "slug", None) == NSM_ADDRESSES_SLUG:
        return True
    model = addr_model or get_nsm_address_model()
    if model is None:
        return False
    return isinstance(obj, model)


def iter_address_ipam_fk_refs(addr_obj) -> Iterator[AddressIpamFkRef]:
    """Yield IPAM Prefix / IPAddress / IPRange referenced by FK fields."""
    from django.contrib.contenttypes.models import ContentType

    for field_name, fk_attr in _FK_FIELDS:
        if not getattr(addr_obj, fk_attr, None):
            continue
        ipam_obj = getattr(addr_obj, field_name, None)
        if ipam_obj is None:
            continue
        yield AddressIpamFkRef(
            ipam_obj=ipam_obj,
            ipam_ct=ContentType.objects.get_for_model(ipam_obj),
            field_name=field_name,
        )


def panel_link_type_for_address_ipam_fk(field_name: str) -> str:
    from django.utils.translation import gettext as _

    labels = {
        "prefix": _("Prefix"),
        "ip_address": _("IP address"),
        "range": _("IP range"),
    }
    label = labels.get(field_name, field_name.replace("_", " ").title())
    return str(_("IPAM reference ({field})").format(field=label))


def fk_field_name_from_filter(fk_filter: dict) -> str | None:
    """Map ``{prefix_id: pk}`` style filters to FK field name."""
    if not fk_filter or len(fk_filter) != 1:
        return None
    fk_attr = next(iter(fk_filter))
    return _FK_FILTER_TO_FIELD.get(fk_attr)
