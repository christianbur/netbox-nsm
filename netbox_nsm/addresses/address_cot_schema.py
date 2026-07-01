"""Structural discovery for IPAM-linked address and address-group COTs."""

from __future__ import annotations

from typing import Any

__all__ = (
    "cot_address_group_flag",
    "cot_ipam_address_flag",
    "get_address_group_cot",
    "get_ipam_address_cot",
    "object_builder_in_nsm_config",
)

_IPAM_APP_LABEL = "ipam"
_IPAM_MODELS = frozenset({"ipaddress", "prefix", "iprange"})
_POLYMORPHIC_CT_ATTR = "address_content_type_id"
_POLYMORPHIC_OBJ_ATTR = "address_object_id"
_LEGACY_FK_ATTRS = frozenset({"prefix_id", "ip_address_id", "range_id"})
_CUSTOM_ADDRESS_FIELDS = frozenset({"ipv4", "ipv6", "subnet"})


def _truthy_object_builder_block(value: Any) -> bool:
    return isinstance(value, dict)


def object_builder_in_nsm_config(cot) -> bool:
    """True when COT comments contain an ``object_builder`` nsm_config segment."""
    if cot is None:
        return False
    comments = getattr(cot, "comments", "") or ""
    from netbox_nsm.type_metadata.config import (
        parse_nsm_config_document_from_comments,
        parse_nsm_config_from_comments,
    )

    parsed = parse_nsm_config_from_comments(comments)
    if parsed and _truthy_object_builder_block(parsed.get("object_builder")):
        return True
    document = parse_nsm_config_document_from_comments(comments)
    return _truthy_object_builder_block(document.get("object_builder"))


def _model_field_names(model) -> set[str]:
    meta = getattr(model, "_meta", None)
    if meta is None:
        return set()
    return {field.name for field in meta.get_fields()}


def _model_has_custom_address_fields(model) -> bool:
    names = _model_field_names(model)
    return _CUSTOM_ADDRESS_FIELDS.issubset(names)


def _model_has_ipam_address_link(model) -> bool:
    names = _model_field_names(model)
    if _POLYMORPHIC_CT_ATTR in names and _POLYMORPHIC_OBJ_ATTR in names:
        return True
    return bool(_LEGACY_FK_ATTRS & names)


def _related_content_types(field) -> list:
    types: list = []
    related = getattr(field, "related_object_type", None)
    if related is not None:
        types.append(related)
    try:
        types.extend(list(field.related_object_types.all()))
    except Exception:
        pass
    return types


def _content_type_is_ipam(ct) -> bool:
    return (
        getattr(ct, "app_label", None) == _IPAM_APP_LABEL
        and getattr(ct, "model", None) in _IPAM_MODELS
    )


def _field_targets_ipam(field) -> bool:
    related = _related_content_types(field)
    if not related:
        return False
    return any(_content_type_is_ipam(ct) for ct in related)


def _cot_has_ipam_address_field(cot) -> bool:
    """True when *cot* exposes an IPAM-binding field (any name; cot_roles)."""
    from netbox_nsm.objects.cot_roles import resolve_ipam_field

    return resolve_ipam_field(cot) is not None


def cot_ipam_address_flag(cot) -> bool:
    """True when *cot* represents IPAM-linked policy addresses (not manual custom)."""
    if cot is None:
        return False
    if object_builder_in_nsm_config(cot):
        return True
    try:
        model = cot.get_model()
    except Exception:
        model = None
    if model is not None:
        if _model_has_custom_address_fields(model):
            return False
        if _model_has_ipam_address_link(model):
            return True
    return _cot_has_ipam_address_field(cot)


def get_ipam_address_cot():
    """Return the deployed IPAM-linked address COT, or ``None``."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None

    for cot in CustomObjectType.objects.all():
        if cot_ipam_address_flag(cot):
            return cot
    return None


def _cot_has_group_members_field(cot) -> bool:
    """True when *cot* exposes an address-members field (any name; cot_roles)."""
    from netbox_nsm.objects.cot_roles import resolve_members_field

    return resolve_members_field(cot) is not None


def cot_address_group_flag(cot) -> bool:
    """True when *cot* is an address-group type (metadata role or ``group`` field)."""
    if cot is None:
        return False
    try:
        from netbox_nsm.type_metadata.roles import resolve_role_for_cot
    except ImportError:
        resolve_role_for_cot = None  # type: ignore[assignment,misc]

    if resolve_role_for_cot is not None and resolve_role_for_cot(cot) == "address_group":
        return True
    return _cot_has_group_members_field(cot)


def get_address_group_cot():
    """Return the deployed address-group COT, or ``None``."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None

    for cot in CustomObjectType.objects.all():
        if cot_address_group_flag(cot):
            return cot
    return None
