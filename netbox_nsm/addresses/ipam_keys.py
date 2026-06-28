"""IPAM key helpers and legacy placeholder formatting for address naming."""

from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType

__all__ = (
    "IpamKey",
    "ipam_key_for_address",
    "ipam_key_for_ipam_obj",
    "ipam_obj_for_key",
    "legacy_format_template",
    "source_key_for_ipam_obj",
)

IpamKey = tuple[int, int]

_SOURCE_MODELS: dict[str, tuple[str, str]] = {
    "ipam.ipaddress": ("ipam", "ipaddress"),
    "ipam.prefix": ("ipam", "prefix"),
    "ipam.iprange": ("ipam", "iprange"),
}


def source_key_for_ipam_obj(ipam_obj) -> str | None:
    ct = ContentType.objects.get_for_model(ipam_obj)
    for source_key, (app_label, model) in _SOURCE_MODELS.items():
        if ct.app_label == app_label and ct.model == model:
            return source_key
    return None


def ipam_key_for_ipam_obj(ipam_obj) -> IpamKey:
    ct = ContentType.objects.get_for_model(ipam_obj)
    return ct.pk, ipam_obj.pk


def ipam_key_for_address(address_obj) -> IpamKey | None:
    ct_id = getattr(address_obj, "address_content_type_id", None)
    obj_id = getattr(address_obj, "address_object_id", None)
    if ct_id is None or obj_id is None:
        return None
    return int(ct_id), int(obj_id)


def ipam_obj_for_key(key: IpamKey):
    ct_id, obj_id = key
    ct = ContentType.objects.filter(pk=ct_id).first()
    if ct is None:
        return None
    model = ct.model_class()
    if model is None:
        return None
    return model.objects.filter(pk=obj_id).first()


def legacy_format_template(template: str, context: dict[str, Any]) -> str:
    """Format legacy ``{host}``-style placeholders using a flat context dict."""
    result = template
    for key, value in context.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result
