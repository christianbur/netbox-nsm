"""NSM-scoped URL helpers for Custom Object types shown under Security → Objects."""

from __future__ import annotations

import contextvars

from django.urls import reverse

from netbox_nsm.type_metadata.menus import (
    MENU_GROUP_NAMES,
    cot_has_menu,
    resolve_menu_for_cot,
)

_NSM_CO_DETAIL_TEMPLATE = "netbox_nsm/customobject.html"

__all__ = (
    "NSM_OBJECTS_GROUP_NAME",
    "apply_nsm_object_co_view_patches",
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

NSM_OBJECTS_GROUP_NAME = MENU_GROUP_NAMES["objects"]

_nsm_object_route_slug = contextvars.ContextVar("nsm_object_route_slug", default=None)


def _custom_object_type_model():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return None
    return CustomObjectType


def cot_belongs_to_nsm_objects_menu(cot) -> bool:
    return cot_has_menu(cot, "objects")


def is_nsm_object_menu_slug(slug: str | None) -> bool:
    if not slug:
        return False
    CustomObjectType = _custom_object_type_model()
    if CustomObjectType is None:
        return False
    cot = CustomObjectType.objects.filter(slug=slug).first()
    if cot is None:
        return False
    return cot_belongs_to_nsm_objects_menu(cot)


def iter_nsm_objects_menu_cots():
    """Yield deployed COTs whose metadata menu bucket is ``objects``."""
    CustomObjectType = _custom_object_type_model()
    if CustomObjectType is None:
        return
    for cot in CustomObjectType.objects.order_by("name", "slug"):
        if cot_belongs_to_nsm_objects_menu(cot):
            yield cot


def nsm_object_menu_label_for_cot(cot) -> str:
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
    """Route NSM policy-object COT links through ``plugins:netbox_nsm`` URLs."""
    try:
        from netbox_custom_objects.models import CustomObject, CustomObjectType
        from netbox_custom_objects.utilities import get_viewname as original_get_viewname
    except ImportError:
        return

    original_instance_get_absolute_url = CustomObject.get_absolute_url
    original_instance_get_list_url = CustomObject.get_list_url
    original_type_get_list_url = CustomObjectType.get_list_url
    original_get_action_url = CustomObject.__dict__["_get_action_url"].__func__

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

    def patched_get_action_url(cls, action=None, rest_api=False, kwargs=None):
        if rest_api:
            return original_get_action_url(cls, action, rest_api, kwargs)
        cot = getattr(cls, "custom_object_type", None)
        slug = _resolve_slug_for_viewname(cls) or getattr(cot, "slug", None)
        if _should_use_nsm_object_urls(slug=slug, cot=cot):
            if kwargs is None:
                kwargs = {}
            else:
                kwargs = dict(kwargs)
            kwargs["custom_object_type"] = slug
            return nsm_object_reverse(action, slug, pk=kwargs.get("pk"))
        return original_get_action_url(cls, action, rest_api, kwargs)

    CustomObject.get_absolute_url = patched_get_absolute_url
    CustomObject.get_list_url = patched_instance_get_list_url
    CustomObjectType.get_list_url = patched_type_get_list_url
    CustomObject._get_action_url = classmethod(patched_get_action_url)

    import netbox_custom_objects.utilities as utilities_module

    utilities_module.get_viewname = patched_get_viewname

    import netbox_custom_objects.templatetags.custom_object_buttons as buttons_module

    buttons_module.get_viewname = patched_get_viewname


def _patch_co_view_dispatch(view_class, *, template_attr: str, template_value: str) -> None:
    original_dispatch = view_class.dispatch

    def patched_dispatch(self, request, *args, **kwargs):
        slug = kwargs.get("custom_object_type")
        token = None
        if is_nsm_object_menu_slug(slug):
            token = set_current_nsm_object_route_slug(slug)
            setattr(self, template_attr, template_value)
        try:
            return original_dispatch(self, request, *args, **kwargs)
        finally:
            if token is not None:
                reset_current_nsm_object_route_slug(token)

    patched_dispatch._nsm_co_view_patch = True
    view_class.dispatch = patched_dispatch


def apply_nsm_object_co_view_patches() -> None:
    """Use the NSM detail template (Security tab nav) on CO routes for menu=objects."""
    try:
        from netbox_custom_objects.views import (
            CustomObjectChangeLogView,
            CustomObjectJournalView,
            CustomObjectView,
        )
    except ImportError:
        return

    if getattr(CustomObjectView.dispatch, "_nsm_co_view_patch", False):
        return

    _patch_co_view_dispatch(
        CustomObjectView,
        template_attr="template_name",
        template_value=_NSM_CO_DETAIL_TEMPLATE,
    )
    _patch_co_view_dispatch(
        CustomObjectJournalView,
        template_attr="base_template",
        template_value=_NSM_CO_DETAIL_TEMPLATE,
    )
    _patch_co_view_dispatch(
        CustomObjectChangeLogView,
        template_attr="base_template",
        template_value=_NSM_CO_DETAIL_TEMPLATE,
    )
