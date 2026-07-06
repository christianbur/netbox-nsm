"""Fixed COT role values for ``nsm_config`` metadata."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

__all__ = (
    "COT_ROLE_CHOICES",
    "COT_ROLE_VALUES",
    "DEFAULT_ROLE_BY_SLUG",
    "default_role_for_slug",
    "normalize_cot_role",
    "parse_role_from_comments",
    "resolve_role_for_cot",
)

COT_ROLE_VALUES = frozenset(
    {
        "zone",
        "address",
        "address_group",
        "label",
        "service",
        "service_group",
        "action",
        "app_business",
        "app_network",
        "object_link",
        "rulebook",
    }
)

COT_ROLE_CHOICES = (
    ("zone", _("Zone")),
    ("address", _("Address")),
    ("address_group", _("Address group")),
    ("label", _("Label")),
    ("service", _("Service")),
    ("service_group", _("Service group")),
    ("action", _("Action")),
    ("app_business", _("Business app")),
    ("app_network", _("Network app")),
    ("object_link", _("Object link")),
    ("rulebook", _("Rulebook")),
)

DEFAULT_ROLE_BY_SLUG = {
    "nsm_zone": "zone",
    "nsm_address": "address",
    "nsm_address_custom": "address",
    "nsm_address_group": "address_group",
    "nsm_label": "label",
    "nsm_service": "service",
    "nsm_service_group": "service_group",
    "nsm_action": "action",
    "nsm_app_business": "app_business",
    "nsm_app_network": "app_network",
    "nsm_object_link": "object_link",
}


def normalize_cot_role(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key not in COT_ROLE_VALUES:
        return None
    return key


def default_role_for_slug(slug: str) -> str | None:
    slug = (slug or "").strip()
    if not slug:
        return None
    explicit = DEFAULT_ROLE_BY_SLUG.get(slug)
    if explicit:
        return explicit
    from netbox_nsm.rulebooks.templates import is_rulebook_template_slug

    if slug.startswith("nsm_rb_") and not is_rulebook_template_slug(slug):
        return "rulebook"
    return None


def parse_role_from_comments(text: str) -> str | None:
    from netbox_nsm.type_metadata.config import (
        _comments_may_contain_nsm_config,
        _extract_nsm_config_list_from_document,
        _load_yaml_document,
    )

    if not _comments_may_contain_nsm_config(text):
        return None
    document = _load_yaml_document(text)
    raw_list = _extract_nsm_config_list_from_document(document)
    if not raw_list:
        return None
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        if len(entry) == 1 and "role" in entry:
            return normalize_cot_role(entry.get("role"))
        if "role" in entry and len(entry) == 1:
            return normalize_cot_role(entry.get("role"))
    return None


def resolve_role_for_cot(cot) -> str | None:
    """Return the effective role for *cot* (comments override slug defaults)."""
    from netbox_nsm.type_metadata.config import _custom_object_type_comments, _is_custom_object_type

    if not _is_custom_object_type(cot):
        parent = getattr(cot, "custom_object_type", None)
        if parent is not None and parent is not cot:
            return resolve_role_for_cot(parent)
        return default_role_for_slug(getattr(parent, "slug", "") or "")

    comments = _custom_object_type_comments(cot)
    stored = parse_role_from_comments(comments or "")
    if stored:
        return stored
    return default_role_for_slug(getattr(cot, "slug", "") or "")
