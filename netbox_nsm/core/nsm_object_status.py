"""Object status indicators (any model with a ``status`` field)."""

from __future__ import annotations

from django.core.exceptions import FieldDoesNotExist
from django.utils.html import conditional_escape
from django.utils.translation import gettext_lazy as _

__all__ = (
    "NSM_OBJECT_STATUS_ACTIVE",
    "NSM_OBJECT_STATUS_DEPRECATED",
    "NSM_OBJECT_STATUS_RESERVED",
    "get_nsm_object_status",
    "normalize_nsm_object_status",
    "nsm_object_status_icon_html",
    "nsm_object_status_tooltip",
    "object_has_status_field",
)

NSM_OBJECT_STATUS_ACTIVE = "active"
NSM_OBJECT_STATUS_RESERVED = "reserved"
NSM_OBJECT_STATUS_DEPRECATED = "deprecated"

_STATUS_TOOLTIPS = {
    NSM_OBJECT_STATUS_RESERVED: _("This object is reserved."),
    NSM_OBJECT_STATUS_DEPRECATED: _("This object is deprecated."),
}


def object_has_status_field(obj) -> bool:
    """True when the instance exposes a ``status`` model field or attribute."""
    if obj is None:
        return False
    meta = getattr(obj, "_meta", None)
    if meta is not None and hasattr(meta, "get_field"):
        try:
            meta.get_field("status")
            return True
        except FieldDoesNotExist:
            return False
    return hasattr(obj, "status")


def _coerce_status_raw(raw) -> str:
    if raw is None:
        return ""
    value = getattr(raw, "value", raw)
    return str(value).strip().lower()


def normalize_nsm_object_status(raw) -> str | None:
    value = _coerce_status_raw(raw)
    if value in (
        NSM_OBJECT_STATUS_ACTIVE,
        NSM_OBJECT_STATUS_RESERVED,
        NSM_OBJECT_STATUS_DEPRECATED,
    ):
        return value
    return None


def get_nsm_object_status(obj) -> str | None:
    """Return reserved/deprecated when object has ``status``; active/unknown → no icon."""
    if not object_has_status_field(obj):
        return None
    status = normalize_nsm_object_status(getattr(obj, "status", None))
    if status in (None, NSM_OBJECT_STATUS_ACTIVE):
        return None
    return status


def nsm_object_status_tooltip(status: str | None) -> str:
    normalized = normalize_nsm_object_status(status)
    if not normalized or normalized == NSM_OBJECT_STATUS_ACTIVE:
        return ""
    return str(_STATUS_TOOLTIPS.get(normalized, ""))


def nsm_object_status_icon_html(status: str | None) -> str:
    """Info icon with tooltip for reserved (orange) or deprecated (red)."""
    normalized = normalize_nsm_object_status(status)
    if normalized not in (NSM_OBJECT_STATUS_RESERVED, NSM_OBJECT_STATUS_DEPRECATED):
        return ""
    tooltip = nsm_object_status_tooltip(normalized)
    if not tooltip:
        return ""
    modifier = (
        "nsm-object-status-icon--deprecated"
        if normalized == NSM_OBJECT_STATUS_DEPRECATED
        else "nsm-object-status-icon--reserved"
    )
    color = (
        "#dc3545"
        if normalized == NSM_OBJECT_STATUS_DEPRECATED
        else "#fd7e14"
    )
    title = conditional_escape(tooltip)
    return (
        f'<i class="mdi mdi-information-outline nsm-object-status-icon {modifier}"'
        f' style="color:{color} !important;"'
        f' title="{title}" aria-label="{title}"></i>'
    )
