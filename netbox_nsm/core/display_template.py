"""Jinja2 display templates for NSM type metadata (``display_template``)."""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from jinja2 import TemplateSyntaxError, Undefined
from jinja2.sandbox import SandboxedEnvironment

__all__ = (
    "DEFAULT_DISPLAY_TEMPLATE",
    "SERVICE_DISPLAY_TEMPLATE",
    "build_display_template_context",
    "normalize_display_template",
    "render_display_template",
    "validate_display_template",
)

DEFAULT_DISPLAY_TEMPLATE = "{{ name }}"

SERVICE_DISPLAY_TEMPLATE = "{{ name }} ({{ protocol }}/{% if port_end and port_end != port %}{{ port }}-{{ port_end }}{% elif port %}{{ port }}{% else %}—{% endif %})"

_JINJA_ENV = SandboxedEnvironment(undefined=Undefined)

_NAME_FALLBACKS = ("name", "prefix", "address", "cidr", "slug")


def _is_multiobject_field_type(field_type: Any) -> bool:
    """Best-effort check for CustomField multiobject type across NetBox/plugin versions."""
    try:
        from extras.choices import CustomFieldTypeChoices

        return field_type == CustomFieldTypeChoices.TYPE_MULTIOBJECT
    except Exception:
        return str(field_type or "").strip().lower() == "multiobject"


def _render_multiobject_context_value(obj: Any, field_name: str) -> str:
    """Return comma-separated display labels for a multiobject field.

    Uses NSM type display templates per referenced object type.
    """
    related = getattr(obj, field_name, None)
    if related is None:
        return ""

    try:
        objects = list(related.all()) if hasattr(related, "all") else list(related)
    except Exception:
        return ""

    if not objects:
        return ""

    try:
        from django.contrib.contenttypes.models import ContentType
        from netbox_nsm.core.display_utils import get_display_template_map, render_object_display

        tmpl_map = get_display_template_map()
        ct_cache: dict[type, int | None] = {}
        rendered: list[str] = []
        for ref_obj in objects:
            if ref_obj is None:
                continue
            model_cls = ref_obj.__class__
            if model_cls not in ct_cache:
                try:
                    ct_cache[model_cls] = ContentType.objects.get_for_model(ref_obj).pk
                except Exception:
                    ct_cache[model_cls] = None
            ct_id = ct_cache[model_cls]
            if ct_id is None:
                rendered.append(str(ref_obj))
            else:
                rendered.append(render_object_display(ref_obj, ct_id, tmpl_map))
        return ", ".join(text for text in rendered if text)
    except Exception:
        return ", ".join(str(ref_obj) for ref_obj in objects if ref_obj is not None)


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
            if field is not None and _is_multiobject_field_type(getattr(field, "type", None)):
                ctx[field_name] = _context_value(_render_multiobject_context_value(obj, field_name))
                continue
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
