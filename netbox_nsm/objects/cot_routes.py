"""NSM-scoped URL helpers for Custom Object types shown under Security → Objects."""

from __future__ import annotations

import contextvars

from django.urls import reverse

from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG

__all__ = (
    "NSM_OBJECTS_GROUP_NAME",
    "apply_nsm_object_url_patches",
    "cot_belongs_to_nsm_objects_menu",
    "current_nsm_object_route_slug",
    "is_nsm_object_menu_slug",
    "iter_nsm_objects_menu_cots",
    "nsm_object_menu_label_for_cot",
    "nsm_object_reverse",
    "nsm_object_viewname",
    "reset_current_nsm_object_route_slug",
    "set_current_nsm_object_route_slug",
)

NSM_OBJECTS_GROUP_NAME = "NSM Objects"

_nsm_object_route_slug = contextvars.ContextVar("nsm_object_route_slug", default=None)


def _custom_object_type_model():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    return CustomObjectType


def cot_belongs_to_nsm_objects_menu(cot) -> bool:
    return getattr(cot, "group_name", None) == NSM_OBJECTS_GROUP_NAME


def is_nsm_object_menu_slug(slug: str | None) -> bool:
    if not slug:
        return False
    CustomObjectType = _custom_object_type_model()
    if CustomObjectType is None:
        return False
    return CustomObjectType.objects.filter(
        slug=slug,
        group_name=NSM_OBJECTS_GROUP_NAME,
    ).exists()


def iter_nsm_objects_menu_cots():
    """Yield deployed COTs in the Custom Objects group ``NSM Objects``."""
    CustomObjectType = _custom_object_type_model()
    if CustomObjectType is None:
        return
    yield from CustomObjectType.objects.filter(group_name=NSM_OBJECTS_GROUP_NAME)


def nsm_object_menu_label_for_cot(cot) -> str:
    spec = TYPECONFIG_SPEC_BY_SLUG.get(cot.slug)
    if spec and spec.get("label"):
        return spec["label"]
    return cot.get_verbose_name_plural()


def set_current_nsm_object_route_slug(slug: str | None):
    return _nsm_object_route_slug.set(slug)


def reset_current_nsm_object_route_slug(token) -> None:
    _nsm_object_route_slug.reset(token)


def current_nsm_object_route_slug() -> str | None:
    return _nsm_object_route_slug.get()


def nsm_object_viewname(action: str | None = None) -> str:
    if action:
        return f"plugins:netbox_nsm:nsm_object_{action}"
    return "plugins:netbox_nsm:nsm_object"


def nsm_object_reverse(action: str | None, slug: str, *, pk: int | None = None) -> str:
    kwargs = {"custom_object_type": slug}
    if pk is not None:
        kwargs["pk"] = pk
    return reverse(nsm_object_viewname(action), kwargs=kwargs)


def _resolve_slug_for_viewname(model) -> str | None:
    route_slug = current_nsm_object_route_slug()
    if route_slug:
        return route_slug
    custom_object_type = getattr(model, "custom_object_type", None)
    if custom_object_type is not None:
        return getattr(custom_object_type, "slug", None)
    return None


def _should_use_nsm_object_urls(*, slug: str | None = None, cot=None) -> bool:
    if cot is not None:
        return cot_belongs_to_nsm_objects_menu(cot)
    return is_nsm_object_menu_slug(slug)


def apply_nsm_object_url_patches() -> None:
    """Route NSM Objects group COT links through ``plugins:netbox_nsm`` URLs."""
    try:
        from netbox_custom_objects.models import CustomObject, CustomObjectType
        from netbox_custom_objects.utilities import get_viewname as original_get_viewname
    except ImportError:
        return

    original_instance_get_absolute_url = CustomObject.get_absolute_url
    original_instance_get_list_url = CustomObject.get_list_url
    original_type_get_list_url = CustomObjectType.get_list_url

    def patched_get_absolute_url(self):
        cot = getattr(self, "custom_object_type", None)
        slug = getattr(cot, "slug", None)
        if _should_use_nsm_object_urls(slug=slug, cot=cot):
            return nsm_object_reverse(None, slug, pk=self.pk)
        return original_instance_get_absolute_url(self)

    def patched_instance_get_list_url(self):
        cot = getattr(self, "custom_object_type", None)
        slug = getattr(cot, "slug", None)
        if _should_use_nsm_object_urls(slug=slug, cot=cot):
            return nsm_object_reverse("list", slug)
        return original_instance_get_list_url(self)

    def patched_type_get_list_url(self):
        if _should_use_nsm_object_urls(slug=self.slug, cot=self):
            return nsm_object_reverse("list", self.slug)
        return original_type_get_list_url(self)

    def patched_get_viewname(model, action=None, rest_api=False):
        if rest_api:
            return original_get_viewname(model, action=action, rest_api=rest_api)
        cot = getattr(model, "custom_object_type", None)
        slug = _resolve_slug_for_viewname(model)
        if _should_use_nsm_object_urls(slug=slug, cot=cot):
            return nsm_object_viewname(action)
        return original_get_viewname(model, action=action, rest_api=rest_api)

    CustomObject.get_absolute_url = patched_get_absolute_url
    CustomObject.get_list_url = patched_instance_get_list_url
    CustomObjectType.get_list_url = patched_type_get_list_url

    import netbox_custom_objects.utilities as utilities_module

    utilities_module.get_viewname = patched_get_viewname

    import netbox_custom_objects.templatetags.custom_object_buttons as buttons_module

    buttons_module.get_viewname = patched_get_viewname
