"""Shared object display helpers."""

from __future__ import annotations

import functools
from typing import Any

__all__ = (
    "changelog_content_type_label",
    "ct_display_label",
    "get_display_template_map",
    "render_object_display",
    "tc_panel_label",
    "type_config_display_name",
    "type_config_display_name_for_ct_id",
)


@functools.lru_cache(maxsize=1)
def get_display_template_map() -> dict[int, str]:
    """Compatibility shim; Custom Objects renders display expressions."""
    return {}


def render_object_display(
    obj: Any, content_type_id: int, tmpl_map: dict[int, str] | None = None
) -> str:
    """Return the model's native display label."""
    return str(obj)


@functools.lru_cache(maxsize=256)
def changelog_content_type_label(content_type_id: int) -> str:
    """App › type label for changelog snapshots (e.g. Custom objects › Addresses)."""
    from django.apps import apps as django_apps
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.type_metadata.config import resolve_nsm_config_for_content_type

    try:
        ct = ContentType.objects.get(pk=content_type_id)
    except ContentType.DoesNotExist:
        return ""

    app_name = ct.app_label
    try:
        app_name = str(django_apps.get_app_config(ct.app_label).verbose_name)
    except LookupError:
        pass

    config = resolve_nsm_config_for_content_type(content_type_id)
    if config and (config.name or "").strip():
        type_name = config.name.strip()
    else:
        model_class = ct.model_class()
        if model_class:
            vn = model_class._meta.verbose_name_plural or model_class._meta.verbose_name
            type_name = str(vn).title() if vn else ct.model.replace("_", " ").title()
        else:
            type_name = ct.model.replace("_", " ").title()

    return f"{app_name} › {type_name}"


def type_config_display_name(type_config, content_type=None) -> str:
    """Picker/type label: TypeConfig.name, else model verbose_name_plural."""
    if type_config is not None:
        label = (getattr(type_config, "name", None) or "").strip()
        if label:
            return label
    ct = content_type
    if ct is None and type_config is not None:
        ct = getattr(type_config, "content_type", None)
    if ct is None:
        return ""
    model_class = ct.model_class()
    if model_class:
        return str(model_class._meta.verbose_name_plural)
    return str(ct.model)


def type_config_display_name_for_ct_id(content_type_id: int) -> str:
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.type_metadata.config import resolve_nsm_config_for_content_type

    config = resolve_nsm_config_for_content_type(content_type_id)
    if config:
        try:
            ct = ContentType.objects.get(pk=content_type_id)
        except ContentType.DoesNotExist:
            ct = None
        return type_config_display_name(config, ct)
    try:
        ct = ContentType.objects.get(pk=content_type_id)
    except ContentType.DoesNotExist:
        return ""
    return type_config_display_name(None, ct)


def ct_display_label(content_type) -> str:
    """Human-readable label for a ContentType (app › model)."""
    if content_type is None:
        return ""
    model_class = content_type.model_class()
    if model_class:
        app_name = getattr(
            model_class._meta.app_config, "verbose_name", content_type.app_label
        )
        model_name = str(model_class._meta.verbose_name)
        if model_name:
            model_name = model_name[:1].upper() + model_name[1:]
        return f"{app_name} › {model_name}"
    return f"{content_type.app_label} | {content_type.model}"


def tc_panel_label(content_type, type_config) -> str:
    """Label for panel/link grouping: TypeConfig.name if set, else ContentType label."""
    if type_config is not None and getattr(type_config, "name", None):
        return type_config.name
    return ct_display_label(content_type)
