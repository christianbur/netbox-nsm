"""Permissions for Object Config / ``nsm_config`` (CustomObjectType-backed)."""

from __future__ import annotations

__all__ = (
    "VIEW_CUSTOM_OBJECT_TYPE",
    "ADD_CUSTOM_OBJECT_TYPE",
    "CHANGE_CUSTOM_OBJECT_TYPE",
    "DELETE_CUSTOM_OBJECT_TYPE",
    "can_change_cot_instance",
    "can_delete_cot_instance",
    "cot_instance_permission",
    "nsm_config_add_permission",
    "nsm_config_change_permission",
    "nsm_config_delete_permission",
    "nsm_config_view_permission",
    "user_can_change_nsm_config",
    "user_can_view_nsm_config",
)

VIEW_CUSTOM_OBJECT_TYPE = "netbox_custom_objects.view_customobjecttype"
ADD_CUSTOM_OBJECT_TYPE = "netbox_custom_objects.add_customobjecttype"
CHANGE_CUSTOM_OBJECT_TYPE = "netbox_custom_objects.change_customobjecttype"
DELETE_CUSTOM_OBJECT_TYPE = "netbox_custom_objects.delete_customobjecttype"


def nsm_config_view_permission() -> str:
    return VIEW_CUSTOM_OBJECT_TYPE


def nsm_config_change_permission() -> str:
    return CHANGE_CUSTOM_OBJECT_TYPE


def nsm_config_add_permission() -> str:
    return CHANGE_CUSTOM_OBJECT_TYPE


def nsm_config_delete_permission() -> str:
    return CHANGE_CUSTOM_OBJECT_TYPE


def user_can_view_nsm_config(user) -> bool:
    return user.has_perm(nsm_config_view_permission())


def user_can_change_nsm_config(user) -> bool:
    return user.has_perm(nsm_config_change_permission())


def cot_instance_permission(obj, action: str) -> str | None:
    """Return ``netbox_custom_objects.{action}_{model}`` for a COT instance."""
    cot = getattr(obj, "custom_object_type", None)
    if cot is None:
        return None
    try:
        model = cot.get_model()
    except Exception:
        return None
    if model is None:
        return None
    return f"netbox_custom_objects.{action}_{model._meta.model_name}"


def can_change_cot_instance(user, obj) -> bool:
    perm = cot_instance_permission(obj, "change")
    return bool(perm and user.has_perm(perm))


def can_delete_cot_instance(user, obj) -> bool:
    perm = cot_instance_permission(obj, "delete")
    if perm and user.has_perm(perm):
        return True
    return can_change_cot_instance(user, obj)
