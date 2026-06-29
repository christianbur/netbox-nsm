"""COT navigation bucket in ``nsm_config`` metadata (``menu`` key)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

__all__ = (
    "COT_MENU_CHOICES",
    "COT_MENU_VALUES",
    "DEFAULT_MENU_BY_ROLE",
    "MENU_GROUP_NAMES",
    "cot_has_menu",
    "default_menu_for_slug",
    "group_name_for_menu",
    "normalize_cot_menu",
    "parse_menu_from_comments",
    "resolve_menu_for_cot",
)

COT_MENU_VALUES = frozenset({"objects", "links", "rulebooks"})

MENU_GROUP_NAMES = {
    "objects": "NSM Objects",
    "links": "NSM Links",
    "rulebooks": "NSM Rulebooks",
}

COT_MENU_CHOICES = (
    ("objects", _("Objects")),
    ("links", _("Links")),
    ("rulebooks", _("Rulebooks")),
)

DEFAULT_MENU_BY_ROLE = {
    "zone": "objects",
    "address": "objects",
    "address_group": "objects",
    "label": "objects",
    "service": "objects",
    "service_group": "objects",
    "action": "objects",
    "app_business": "objects",
    "app_network": "objects",
    "object_link": "links",
    "rulebook": "rulebooks",
}


def normalize_cot_menu(value: str | None) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    if key not in COT_MENU_VALUES:
        return None
    return key


def default_menu_for_slug(slug: str) -> str | None:
    from netbox_nsm.type_metadata.roles import default_role_for_slug

    role = default_role_for_slug(slug)
    if not role:
        return None
    return DEFAULT_MENU_BY_ROLE.get(role)


def parse_menu_from_comments(text: str) -> str | None:
    from netbox_nsm.type_metadata.config import (
        _extract_nsm_config_list_from_document,
        _load_yaml_document,
    )

    document = _load_yaml_document(text)
    raw_list = _extract_nsm_config_list_from_document(document)
    if not raw_list:
        return None
    for entry in raw_list:
        if isinstance(entry, dict) and len(entry) == 1 and "menu" in entry:
            return normalize_cot_menu(entry.get("menu"))
    return None


def resolve_menu_for_cot(cot) -> str | None:
    """Return the effective menu bucket for *cot* (comments override slug defaults)."""
    stored = parse_menu_from_comments(getattr(cot, "comments", "") or "")
    if stored:
        return stored
    return default_menu_for_slug(getattr(cot, "slug", "") or "")


def cot_has_menu(cot, menu: str) -> bool:
    return resolve_menu_for_cot(cot) == normalize_cot_menu(menu)


def group_name_for_menu(menu: str | None) -> str | None:
    normalized = normalize_cot_menu(menu)
    if not normalized:
        return None
    return MENU_GROUP_NAMES.get(normalized)
