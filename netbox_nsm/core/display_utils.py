"""
Shared utility: apply TypeConfig.display_template to NetBox objects.

Usage (one DB query per request):
    from netbox_nsm.core.display_utils import get_display_template_map, render_object_display

    tmpl_map = get_display_template_map()           # {ct_id: "{{ name }}", ...}
    label = render_object_display(obj, ct_id, tmpl_map)
"""

from __future__ import annotations

import functools
from typing import Any

from netbox_nsm.core.display_template import (
    DEFAULT_DISPLAY_TEMPLATE,
    render_display_template,
)

__all__ = (
    "apply_display_template",
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
    """Return {content_type_id: display_template} for all configured types.

    Result is cached for the lifetime of the Python process (templates are
    virtually static at runtime; a container restart resets the cache).
    """
    from netbox_nsm.objects.nsm_config import build_nsm_config_lookup

    return {
        config.content_type_id: config.display_template
        for config in build_nsm_config_lookup().values()
        if config.display_template
    }


def apply_display_template(obj: Any, tmpl: str) -> str:
    """Render a Jinja2 display template for *obj*."""
    return render_display_template(obj, tmpl)


def render_object_display(
    obj: Any, content_type_id: int, tmpl_map: dict[int, str] | None = None
) -> str:
    """Return the display label for *obj*, applying the TypeConfig template if available."""
    if tmpl_map is None:
        tmpl_map = get_display_template_map()
    tmpl = tmpl_map.get(content_type_id, "") or DEFAULT_DISPLAY_TEMPLATE
    if tmpl:
        return apply_display_template(obj, tmpl)
    return render_display_template(obj, DEFAULT_DISPLAY_TEMPLATE)


@functools.lru_cache(maxsize=256)
def changelog_content_type_label(content_type_id: int) -> str:
    """App › type label for changelog snapshots (e.g. Custom objects › Addresses)."""
    from django.apps import apps as django_apps
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.objects.nsm_config import resolve_nsm_config_for_content_type

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
        return str(model_class._meta.verbose_name_plural).title()
    return str(ct.model)


def type_config_display_name_for_ct_id(content_type_id: int) -> str:
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.objects.nsm_config import resolve_nsm_config_for_content_type

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
