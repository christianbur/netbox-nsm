"""
Shared utility: apply TypeConfig.display_template to NetBox objects.

Usage (one DB query per request):
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    tmpl_map = get_display_template_map()           # {ct_id: "Addr:{name}", ...}
    label = render_object_display(obj, ct_id, tmpl_map)
"""

from __future__ import annotations

import functools
import re
from typing import Any


@functools.lru_cache(maxsize=1)
def get_display_template_map() -> dict[int, str]:
    """Return {content_type_id: display_template} for all configured types.

    Result is cached for the lifetime of the Python process (templates are
    virtually static at runtime; a container restart resets the cache).
    """
    from netbox_nsm.models import TypeConfig

    return {
        tc.content_type_id: tc.display_template
        for tc in TypeConfig.objects.filter(display_template__gt="").only(
            "content_type_id", "display_template"
        )
    }


_PLACEHOLDER = re.compile(r"\{(\w+)(?:\[([-]?\d+)\])?(?:!(u))?\}")

# Attribute names tried in order when resolving ``{name}`` in a template.
_NAME_FALLBACKS = ("name", "prefix", "address", "cidr", "slug")


def _resolve_name(obj: Any) -> str:
    for attr in _NAME_FALLBACKS:
        val = getattr(obj, attr, None)
        if val:
            return str(val)
    return str(obj)


def apply_display_template(obj: Any, tmpl: str) -> str:
    """Apply a template string like 'Addr:{name}' to *obj*.

    ``{name}`` is special: it tries multiple common attribute names before
    falling back to ``str(obj)`` so that objects without a literal ``name``
    field (e.g. ``ipam.Prefix``) still render usefully.
    All other placeholders ``{field}`` are replaced by
    ``str(getattr(obj, field, ""))``.
    Unknown fields are replaced with an empty string.
    """

    def _replace(m: re.Match) -> str:
        field = m.group(1)
        idx = m.group(2)  # e.g. '0' from {protocol[0]}, or None
        upper = m.group(3)  # '!u' conversion for uppercase, or None
        if field == "name" and idx is None:
            raw = _resolve_name(obj)
        else:
            val = getattr(obj, field, "") or ""
            if idx is not None:
                try:
                    raw = str(val)[int(idx)]
                except (IndexError, ValueError, TypeError):
                    raw = ""
            else:
                raw = str(val)
        if upper:
            raw = raw.upper()
        return raw

    return _PLACEHOLDER.sub(_replace, tmpl)


def render_object_display(
    obj: Any, content_type_id: int, tmpl_map: dict[int, str] | None = None
) -> str:
    """Return the display label for *obj*, applying the TypeConfig template if available."""
    if tmpl_map is None:
        tmpl_map = get_display_template_map()
    tmpl = tmpl_map.get(content_type_id, "") or "{name}"
    if tmpl:
        return apply_display_template(obj, tmpl)
    return _resolve_name(obj)


@functools.lru_cache(maxsize=256)
def changelog_content_type_label(content_type_id: int) -> str:
    """App › type label for changelog snapshots (e.g. Custom objects › Addresses)."""
    from django.apps import apps as django_apps
    from django.contrib.contenttypes.models import ContentType

    from netbox_nsm.models import TypeConfig

    try:
        ct = ContentType.objects.get(pk=content_type_id)
    except ContentType.DoesNotExist:
        return ""

    app_name = ct.app_label
    try:
        app_name = str(django_apps.get_app_config(ct.app_label).verbose_name)
    except LookupError:
        pass

    tc = TypeConfig.objects.filter(content_type_id=content_type_id).only("name").first()
    if tc and (tc.name or "").strip():
        type_name = tc.name.strip()
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

    from netbox_nsm.models import TypeConfig

    tc = (
        TypeConfig.objects.filter(content_type_id=content_type_id)
        .select_related("content_type")
        .first()
    )
    if tc:
        return type_config_display_name(tc, tc.content_type)
    try:
        ct = ContentType.objects.get(pk=content_type_id)
    except ContentType.DoesNotExist:
        return ""
    return type_config_display_name(None, ct)


def type_name_for_field_content_type(field, content_type_id: int) -> str:
    """Type label configured on a rulebook field (RulebookFieldType → TypeConfig)."""
    if not field or not content_type_id:
        return ""
    for ft in field.type_configs.all():
        tc = getattr(ft, "type_config", None)
        if tc and tc.content_type_id == content_type_id:
            return type_config_display_name(tc, tc.content_type)
    return type_config_display_name_for_ct_id(content_type_id)


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
