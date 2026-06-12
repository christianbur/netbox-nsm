"""Type-kind helpers derived from COT content-type model names."""

from __future__ import annotations

__all__ = (
    "ADDRESS_CONTENT_MODELS",
    "address_content_type_ids",
    "column_is_address",
    "is_address_content_model",
    "is_address_content_type_id",
    "search_properties_for_model",
    "type_config_css_slug",
    "type_config_icon",
)

ADDRESS_CONTENT_MODELS = frozenset({"nsm_address", "nsm_address_group"})

_MODEL_PROPERTY_HINTS = {
    "nsm_address": ["name", "description"],
    "nsm_address_group": ["name"],
    "nsm_zone": ["name", "description"],
    "nsm_label": ["name", "label_type"],
    "nsm_service": ["name", "protocol", "port"],
    "nsm_service_group": ["name"],
    "nsm_action": ["name"],
}

_MODEL_ICONS = {
    "address": "mdi-ip-network-outline",
    "address-group": "mdi-ip-network-outline",
    "zone": "mdi-map-marker-radius-outline",
    "service": "mdi-cog-outline",
    "service-group": "mdi-cog-outline",
    "action": "mdi-play-circle-outline",
    "label": "mdi-label-outline",
    "app-business": "mdi-information-outline",
    "app-network": "mdi-application-outline",
    "object-link": "mdi-link-variant",
}


def is_address_content_model(model: str) -> bool:
    return (model or "") in ADDRESS_CONTENT_MODELS


def address_content_type_ids() -> set[int]:
    from django.contrib.contenttypes.models import ContentType

    return set(
        ContentType.objects.filter(model__in=ADDRESS_CONTENT_MODELS).values_list(
            "pk", flat=True
        )
    )


def is_address_content_type_id(content_type_id, *, cache: set[int] | None = None) -> bool:
    try:
        ct_id = int(content_type_id)
    except (TypeError, ValueError):
        return False
    if cache is None:
        cache = address_content_type_ids()
    return ct_id in cache


def search_properties_for_model(model: str) -> list[str]:
    return list(_MODEL_PROPERTY_HINTS.get(model or "", ["name"]))


def type_config_css_slug(type_config) -> str:
    model = ""
    content_type = getattr(type_config, "content_type", None)
    if content_type is not None:
        model = getattr(content_type, "model", "") or ""
    if model.startswith("nsm_"):
        return model[4:].replace("_", "-")
    return (model or "other").replace("_", "-")


def type_config_icon(type_config) -> str:
    return _MODEL_ICONS.get(type_config_css_slug(type_config), "mdi-cube-outline")


def column_is_address(col: dict) -> bool:
    type_name = str(col.get("type_name") or "")
    if type_name.startswith("ct_"):
        try:
            ct_id = int(type_name[3:])
        except ValueError:
            return False
        return is_address_content_type_id(ct_id)
    label = str(col.get("label") or "").lower()
    return "address" in label
