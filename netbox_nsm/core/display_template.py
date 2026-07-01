"""Jinja2 display templates for NSM type metadata (``display_template``)."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from jinja2 import TemplateSyntaxError, Undefined
from jinja2.sandbox import SandboxedEnvironment

__all__ = (
    "DEFAULT_DISPLAY_TEMPLATE",
    "build_display_template_context",
    "normalize_display_template",
    "render_display_template",
    "validate_display_template",
)

DEFAULT_DISPLAY_TEMPLATE = "{{ name }}"

_JINJA_ENV = SandboxedEnvironment(undefined=Undefined)

_NAME_FALLBACKS = ("name", "prefix", "address", "cidr", "slug")


def normalize_display_template(tmpl: str | None) -> str:
    """Return a stripped display template string, defaulting when empty."""
    return (tmpl or "").strip() or DEFAULT_DISPLAY_TEMPLATE


def validate_display_template(tmpl: str) -> None:
    """Raise ``ValidationError`` when *tmpl* is not valid Jinja2."""
    try:
        _JINJA_ENV.from_string(normalize_display_template(tmpl))
    except TemplateSyntaxError as exc:
        raise ValidationError(
            _("Invalid display template: %(error)s") % {"error": exc.message}
        ) from exc


def _resolve_name(obj: Any) -> str:
    for attr in _NAME_FALLBACKS:
        val = getattr(obj, attr, None)
        if val:
            return str(val)
    return str(obj)


def _context_value(value: Any) -> Any:
    if value is None:
        return ""
    return value


def build_display_template_context(obj: Any) -> dict[str, Any]:
    """Build Jinja2 context for *obj* (COT instances, NetBox models, etc.)."""
    ctx: dict[str, Any] = {"name": _resolve_name(obj)}

    field_objects = getattr(obj, "_field_objects", None)
    if field_objects:
        try:
            from netbox_custom_objects.models import FIELD_TYPE_CLASS
        except ImportError:
            FIELD_TYPE_CLASS = None

        for field_info in field_objects.values():
            field_name = field_info["name"]
            if field_name in ctx:
                continue
            field = field_info.get("field")
            if FIELD_TYPE_CLASS is not None and field is not None:
                try:
                    field_type = FIELD_TYPE_CLASS[field.type]()
                    ctx[field_name] = _context_value(
                        field_type.get_display_value(obj, field_name)
                    )
                    continue
                except Exception:
                    pass
            ctx[field_name] = _context_value(getattr(obj, field_name, ""))

    meta = getattr(obj, "_meta", None)
    if meta is not None and hasattr(meta, "concrete_fields"):
        for field in meta.concrete_fields:
            name = field.name
            if name in ctx:
                continue
            try:
                ctx[name] = _context_value(getattr(obj, name))
            except Exception:
                continue

    for key, value in vars(obj).items():
        if key.startswith("_") or key in ctx:
            continue
        ctx[key] = _context_value(value)

    return ctx


def render_display_template(obj: Any, tmpl: str) -> str:
    """Render *tmpl* for *obj*; fall back to resolved name on error/empty."""
    expression = normalize_display_template(tmpl)
    if not expression:
        return _resolve_name(obj)
    try:
        rendered = _JINJA_ENV.from_string(expression).render(
            **build_display_template_context(obj)
        ).strip()
        return rendered or _resolve_name(obj)
    except Exception:
        return _resolve_name(obj)
