"""
Shared utility: apply NSMTypeConfig.display_template to NetBox objects.

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

    Reads from both NSMTypeConfig and TypeConfig; TypeConfig takes precedence
    when both have a template for the same ContentType.

    Result is cached for the lifetime of the Python process (templates are
    virtually static at runtime; a container restart resets the cache).
    """
    from netbox_nsm.models import NSMTypeConfig, TypeConfig

    result = {
        tc.content_type_id: tc.display_template
        for tc in NSMTypeConfig.objects.filter(display_template__gt="").only(
            "content_type_id", "display_template"
        )
    }
    # TypeConfig overrides NSMTypeConfig
    result.update({
        tc.content_type_id: tc.display_template
        for tc in TypeConfig.objects.filter(display_template__gt="").only(
            "content_type_id", "display_template"
        )
    })
    return result


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
        idx = m.group(2)   # e.g. '0' from {protocol[0]}, or None
        upper = m.group(3) # '!u' conversion for uppercase, or None
        if field == "name" and idx is None:
            raw = _resolve_name(obj)
        else:
            val = getattr(obj, field, "") or ""
            if isinstance(val, (list, tuple)):
                raw = "/".join(str(v) for v in val)
            else:
                raw = str(val)
            if idx is not None:
                try:
                    raw = raw[int(idx)]
                except IndexError:
                    raw = ""
        return raw.upper() if upper else raw

    return _PLACEHOLDER.sub(_replace, tmpl)


def render_object_display(
    obj: Any,
    ct_id: int,
    template_map: dict[int, str],
) -> str:
    """Return the display label for *obj*, applying the NSMTypeConfig template if available.

    Falls back to ``obj.name`` → ``str(obj)`` when no template is configured.
    """
    tmpl = template_map.get(ct_id, "")
    if tmpl:
        return apply_display_template(obj, tmpl)
    return str(getattr(obj, "name", None) or obj)


# Short display names for apps with long verbose_names.
_APP_SHORT_NAMES: dict[str, str] = {
    "netbox_nsm": "NSM",
}


def ct_display_label(ct) -> str:
    """Return a human-readable type label for a ContentType.

    Always renders as "App › Model", e.g.:
        ipam.prefix                        → "IPAM › Prefix"
        ipam.ipaddress                     → "IPAM › IP Address"
        netbox_custom_objects.table10model → "Custom Objects › Addresses"
        netbox_nsm.securityzone            → "NSM › Security Zone"
    """
    # Smart title-case: capitalise only all-lowercase words so "IP address" → "IP Address"
    model_name = " ".join(
        w if any(c.isupper() for c in w) else w.capitalize()
        for w in ct.name.split()
    )
    try:
        from django.apps import apps
        app_vn = _APP_SHORT_NAMES.get(ct.app_label) or apps.get_app_config(ct.app_label).verbose_name
        return f"{app_vn} \u203a {model_name}"
    except Exception:
        return model_name
