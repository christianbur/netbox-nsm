"""
Forward IPAM references on ``nsm_addresses`` custom objects.

Supports the polymorphic ``address`` GFK (``address_content_type_id`` /
``address_object_id``) and legacy per-type FK fields.

Reverse lookup (IPAM object → addresses) lives in ``template_content`` and
``analyzer.edge_sources.addr_fk_edges``; this module covers address → IPAM.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

from netbox_nsm.addresses.address_cot_schema import (
    cot_ipam_address_flag,
    get_ipam_address_cot,
)
from netbox_nsm.addresses.address_custom import (
    NSM_ADDRESS_CUSTOM_SLUG,
    is_nsm_address_custom_object,
)

__all__ = (
    "NSM_ADDRESSES_SLUG",
    "POLICY_ADDRESS_COT_SLUGS",
    "AddressIpamFkRef",
    "clear_address_ipam_link",
    "get_nsm_address_model",
    "is_nsm_address_object",
    "is_policy_address_object",
    "iter_address_ipam_fk_refs",
    "iter_addresses_for_ipam_object",
    "addresses_for_ipam_object_queryset",
    "panel_link_type_for_address_ipam_fk",
    "fk_field_name_from_filter",
)

NSM_ADDRESSES_SLUG = "nsm_addresses"

POLICY_ADDRESS_COT_SLUGS = frozenset(
    {
        NSM_ADDRESSES_SLUG,
        NSM_ADDRESS_CUSTOM_SLUG,
    }
)

_LEGACY_FK_FIELDS = (
    ("prefix", "prefix_id"),
    ("ip_address", "ip_address_id"),
    ("range", "range_id"),
)

_LEGACY_FK_FILTER_TO_FIELD = {
    fk_attr: field_name for field_name, fk_attr in _LEGACY_FK_FIELDS
}

_POLYMORPHIC_CT_ATTR = "address_content_type_id"
_POLYMORPHIC_OBJ_ATTR = "address_object_id"
_POLYMORPHIC_FIELD = "address"


def _ipam_gfk_attrs_for_obj(addr_obj) -> tuple[str, str, str]:
    """Return ``(ct_attr, obj_attr, field_name)`` for *addr_obj*'s IPAM GFK.

    Fast path uses the default ``address`` column names; for COTs with a
    differently-named IPAM field the names are resolved via ``cot_roles``.
    """
    if hasattr(addr_obj, _POLYMORPHIC_CT_ATTR):
        return _POLYMORPHIC_CT_ATTR, _POLYMORPHIC_OBJ_ATTR, _POLYMORPHIC_FIELD
    cot = getattr(addr_obj, "custom_object_type", None)
    if cot is not None:
        cot_pk = getattr(cot, "pk", None)
        if cot_pk is not None:
            return _ipam_gfk_attrs_for_cot_pk(cot_pk)
        from netbox_nsm.objects.cot_roles import ipam_gfk_attrs, resolve_ipam_field_name

        ct_attr, obj_attr = ipam_gfk_attrs(cot)
        return ct_attr, obj_attr, resolve_ipam_field_name(cot)
    return _POLYMORPHIC_CT_ATTR, _POLYMORPHIC_OBJ_ATTR, _POLYMORPHIC_FIELD


@lru_cache(maxsize=256)
def _ipam_gfk_attrs_for_cot_pk(cot_pk: int) -> tuple[str, str, str]:
    from netbox_custom_objects.models import CustomObjectType
    from netbox_nsm.objects.cot_roles import ipam_gfk_attrs, resolve_ipam_field_name

    try:
        cot = CustomObjectType.objects.get(pk=cot_pk)
    except CustomObjectType.DoesNotExist:
        return _POLYMORPHIC_CT_ATTR, _POLYMORPHIC_OBJ_ATTR, _POLYMORPHIC_FIELD
    ct_attr, obj_attr = ipam_gfk_attrs(cot)
    return ct_attr, obj_attr, resolve_ipam_field_name(cot)


def _ipam_gfk_attrs_for_model(addr_model) -> tuple[str, str, str]:
    """Resolve the IPAM GFK columns for an address *model* via its COT."""
    if hasattr(addr_model, _POLYMORPHIC_CT_ATTR):
        return _POLYMORPHIC_CT_ATTR, _POLYMORPHIC_OBJ_ATTR, _POLYMORPHIC_FIELD
    cot = get_ipam_address_cot()
    if cot is not None:
        from netbox_nsm.objects.cot_roles import ipam_gfk_attrs, resolve_ipam_field_name

        ct_attr, obj_attr = ipam_gfk_attrs(cot)
        return ct_attr, obj_attr, resolve_ipam_field_name(cot)
    return _POLYMORPHIC_CT_ATTR, _POLYMORPHIC_OBJ_ATTR, _POLYMORPHIC_FIELD


@dataclass(frozen=True)
class AddressIpamFkRef:
    """One IPAM object referenced by an ``nsm_addresses`` row."""

    ipam_obj: object
    ipam_ct: object
    field_name: str


def get_nsm_address_model():
    """Return the dynamic IPAM-linked address model class, or ``None``."""
    cot = get_ipam_address_cot()
    if cot is None:
        return None
    try:
        return cot.get_model()
    except Exception:
        return None


def is_nsm_address_object(obj, addr_model=None) -> bool:
    if obj is None:
        return False
    cot = getattr(obj, "custom_object_type", None)
    if cot is not None and cot_ipam_address_flag(cot):
        return True
    model = addr_model or get_nsm_address_model()
    if model is None:
        return False
    return isinstance(obj, model)


def is_policy_address_object(obj, addr_model=None) -> bool:
    """True for IPAM-linked address rows and manual custom addresses."""
    if is_nsm_address_custom_object(obj):
        return True
    if is_nsm_address_object(obj, addr_model=addr_model):
        return True
    return False


def _iter_polymorphic_ref(addr_obj) -> Iterator[AddressIpamFkRef]:
    from django.contrib.contenttypes.models import ContentType

    ct_attr, obj_attr, field_name = _ipam_gfk_attrs_for_obj(addr_obj)
    ct_id = getattr(addr_obj, ct_attr, None)
    obj_id = getattr(addr_obj, obj_attr, None)
    if not ct_id or not obj_id:
        return

    try:
        ct = ContentType.objects.get(pk=ct_id)
    except ContentType.DoesNotExist:
        return

    model = ct.model_class()
    if model is None:
        return

    ipam_obj = model.objects.filter(pk=obj_id).first()
    if ipam_obj is None:
        return

    yield AddressIpamFkRef(
        ipam_obj=ipam_obj,
        ipam_ct=ct,
        field_name=field_name,
    )


def _iter_legacy_refs(addr_obj) -> Iterator[AddressIpamFkRef]:
    from django.contrib.contenttypes.models import ContentType

    for field_name, fk_attr in _LEGACY_FK_FIELDS:
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


def iter_address_ipam_fk_refs(addr_obj) -> Iterator[AddressIpamFkRef]:
    """Yield IPAM Prefix / IPAddress / IPRange referenced by address row."""
    polymorphic = list(_iter_polymorphic_ref(addr_obj))
    if polymorphic:
        yield from polymorphic
        return
    yield from _iter_legacy_refs(addr_obj)


def _legacy_fk_attr_for_ipam_object(ipam_obj) -> tuple[str, str] | None:
    """Return ``(fk_attr, field_name)`` for a legacy IPAM FK on *ipam_obj*, if any."""
    model_name = type(ipam_obj).__name__
    mapping = {
        "Prefix": ("prefix_id", "prefix"),
        "IPAddress": ("ip_address_id", "ip_address"),
        "IPRange": ("range_id", "range"),
    }
    entry = mapping.get(model_name)
    if entry is None:
        return None
    return entry


def _addr_model_supports_legacy_fk(addr_model, fk_attr: str) -> bool:
    try:
        addr_model._meta.get_field(fk_attr)
        return True
    except Exception:
        return False


def iter_addresses_for_ipam_object(ipam_obj) -> Iterator[tuple[object, str]]:
    """
    Yield ``(nsm_address, field_name)`` rows referencing *ipam_obj*.

    Covers polymorphic ``address`` GFK and legacy ``prefix`` / ``ip_address`` /
    ``range`` FK columns.
    """
    if ipam_obj is None or not getattr(ipam_obj, "pk", None):
        return

    addr_model = get_nsm_address_model()
    if addr_model is None:
        return

    from django.contrib.contenttypes.models import ContentType

    ct_attr, obj_attr, field_name = _ipam_gfk_attrs_for_model(addr_model)
    seen: set[int] = set()
    ipam_ct = ContentType.objects.get_for_model(ipam_obj)

    for addr in addr_model.objects.filter(
        **{
            ct_attr: ipam_ct.pk,
            obj_attr: ipam_obj.pk,
        }
    ).order_by("name"):
        if addr.pk in seen:
            continue
        seen.add(addr.pk)
        yield addr, field_name

    legacy = _legacy_fk_attr_for_ipam_object(ipam_obj)
    if legacy is not None:
        fk_attr, field_name = legacy
        if _addr_model_supports_legacy_fk(addr_model, fk_attr):
            for addr in addr_model.objects.filter(**{fk_attr: ipam_obj.pk}).order_by(
                "name"
            ):
                if addr.pk in seen:
                    continue
                seen.add(addr.pk)
                yield addr, field_name


def addresses_for_ipam_object_queryset(addr_model, ipam_obj):
    """QuerySet of ``nsm_addresses`` rows referencing *ipam_obj*."""
    from django.contrib.contenttypes.models import ContentType
    from django.db.models import Q

    if addr_model is None or ipam_obj is None or not getattr(ipam_obj, "pk", None):
        return addr_model.objects.none() if addr_model is not None else None

    ct_attr, obj_attr, _field_name = _ipam_gfk_attrs_for_model(addr_model)
    ipam_ct = ContentType.objects.get_for_model(ipam_obj)
    q = Q(
        **{
            ct_attr: ipam_ct.pk,
            obj_attr: ipam_obj.pk,
        }
    )
    legacy = _legacy_fk_attr_for_ipam_object(ipam_obj)
    if legacy is not None:
        fk_attr, _field_name = legacy
        if _addr_model_supports_legacy_fk(addr_model, fk_attr):
            q |= Q(**{fk_attr: ipam_obj.pk})
    return addr_model.objects.filter(q)


def clear_address_ipam_link(addr) -> list[str]:
    """Clear polymorphic and legacy IPAM links on an address row; return updated fields."""
    update_fields: list[str] = []
    ct_attr, obj_attr, _field = _ipam_gfk_attrs_for_obj(addr)
    for attr in (ct_attr, obj_attr):
        if hasattr(addr, attr):
            setattr(addr, attr, None)
            update_fields.append(attr)
    for _field_name, fk_attr in _LEGACY_FK_FIELDS:
        if hasattr(addr, fk_attr):
            setattr(addr, fk_attr, None)
            update_fields.append(fk_attr)
    return update_fields


def panel_link_type_for_address_ipam_fk(field_name: str) -> str:
    from django.utils.translation import gettext as _

    labels = {
        _POLYMORPHIC_FIELD: _("Address"),
        "prefix": _("Prefix"),
        "ip_address": _("IP address"),
        "range": _("IP range"),
    }
    label = labels.get(field_name, field_name.replace("_", " ").title())
    return str(_("IPAM reference ({field})").format(field=label))


def fk_field_name_from_filter(fk_filter: dict) -> str | None:
    """Map ``{prefix_id: pk}`` or polymorphic GFK filters to field name."""
    if not fk_filter:
        return None
    if len(fk_filter) == 2 and _POLYMORPHIC_CT_ATTR in fk_filter and _POLYMORPHIC_OBJ_ATTR in fk_filter:
        return _POLYMORPHIC_FIELD
    if len(fk_filter) != 1:
        return None
    fk_attr = next(iter(fk_filter))
    if fk_attr == _POLYMORPHIC_OBJ_ATTR:
        return _POLYMORPHIC_FIELD
    return _LEGACY_FK_FILTER_TO_FIELD.get(fk_attr)
