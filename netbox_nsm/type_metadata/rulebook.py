"""Parse, format, and resolve ``nsm_config.rulebook`` in ``CustomObjectType.comments``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

__all__ = (
    "DEFAULT_RULEBOOK_CONFIG",
    "format_rulebook_config_yaml",
    "is_default_rulebook_config",
    "load_rulebook_parent_map",
    "merge_rulebook_config_into_comments",
    "normalize_rulebook_config",
    "parse_rulebook_config_from_comments",
    "resolve_rulebook_config_for_cot",
    "resolve_rulebook_config_for_slug",
    "save_rulebook_config_for_cot",
)

DEFAULT_RULEBOOK_CONFIG = {
    "parent_slug": "",
    "matrix_tab_enabled": True,
    "row_group_by_col_id": "",
}


def normalize_rulebook_config(raw: dict | None) -> dict[str, Any]:
    """Return a complete ``rulebook`` block with defaults applied."""
    base = deepcopy(DEFAULT_RULEBOOK_CONFIG)
    if not raw:
        return base
    if "parent_slug" in raw:
        base["parent_slug"] = str(raw.get("parent_slug") or "").strip()
    if "matrix_tab_enabled" in raw:
        base["matrix_tab_enabled"] = bool(raw["matrix_tab_enabled"])
    if "row_group_by_col_id" in raw:
        base["row_group_by_col_id"] = str(raw.get("row_group_by_col_id") or "").strip()
    return base


def is_default_rulebook_config(config: dict) -> bool:
    normalized = normalize_rulebook_config(config)
    return normalized == DEFAULT_RULEBOOK_CONFIG


def _rulebook_block_for_yaml(config: dict) -> dict[str, Any]:
    normalized = normalize_rulebook_config(config)
    return {
        "parent_slug": normalized["parent_slug"],
        "matrix_tab_enabled": normalized["matrix_tab_enabled"],
        "row_group_by_col_id": normalized["row_group_by_col_id"],
    }


def parse_rulebook_config_from_comments(text: str) -> dict[str, Any]:
    """Parse ``rulebook`` settings from ``CustomObjectType.comments``."""
    from netbox_nsm.type_metadata.config import (
        _extract_nsm_config_list_from_document,
        _load_yaml_document,
        _stored_nsm_config_document,
    )

    stored = _stored_nsm_config_document(text)
    if "rulebook" in stored:
        return normalize_rulebook_config(stored.get("rulebook"))

    document = _load_yaml_document(text)
    raw_list = _extract_nsm_config_list_from_document(document)
    if not raw_list:
        return deepcopy(DEFAULT_RULEBOOK_CONFIG)
    for entry in raw_list:
        if isinstance(entry, dict) and len(entry) == 1 and "rulebook" in entry:
            block = entry.get("rulebook")
            if isinstance(block, dict):
                return normalize_rulebook_config(block)
    return deepcopy(DEFAULT_RULEBOOK_CONFIG)


def format_rulebook_config_yaml(config: dict) -> str:
    """Return canonical ``nsm_config`` YAML containing only the rulebook segment."""
    import yaml

    normalized = normalize_rulebook_config(config)
    if is_default_rulebook_config(normalized):
        return ""
    payload = {"nsm_config": [{"rulebook": _rulebook_block_for_yaml(normalized)}]}
    return (
        yaml.dump(
            payload,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )


def merge_rulebook_config_into_comments(
    existing_comments: str,
    config_dict: dict,
) -> str:
    """Merge ``rulebook`` settings into existing ``CustomObjectType.comments`` YAML."""
    from netbox_nsm.type_metadata.config import merge_nsm_config_document_into_comments

    normalized = normalize_rulebook_config(config_dict)
    if is_default_rulebook_config(normalized):
        return merge_nsm_config_document_into_comments(
            existing_comments,
            {"rulebook": None},
        )
    return merge_nsm_config_document_into_comments(
        existing_comments,
        {"rulebook": normalized},
    )


def resolve_rulebook_config_for_cot(cot) -> dict[str, Any]:
    from netbox_nsm.type_metadata.config import _custom_object_type_comments, _is_custom_object_type

    if not _is_custom_object_type(cot):
        return deepcopy(DEFAULT_RULEBOOK_CONFIG)
    return parse_rulebook_config_from_comments(_custom_object_type_comments(cot) or "")


def resolve_rulebook_config_for_slug(slug: str) -> dict[str, Any]:
    from netbox_nsm.rulebooks.registry import get_deployed_cot_rulebook

    cot = get_deployed_cot_rulebook(slug)
    if cot is None:
        return deepcopy(DEFAULT_RULEBOOK_CONFIG)
    return resolve_rulebook_config_for_cot(cot)


def save_rulebook_config_for_cot(cot, config: dict) -> None:
    """Persist ``rulebook`` settings on *cot* ``comments``."""
    from django.core.exceptions import ValidationError

    from netbox_nsm.type_metadata.config import save_nsm_config_document_for_cot
    from netbox_nsm.rulebooks.cot_hierarchy import validate_cot_parent_slug

    existing = resolve_rulebook_config_for_cot(cot)
    merged = dict(existing)
    full_normalized = normalize_rulebook_config(config)
    for key in ("parent_slug", "matrix_tab_enabled", "row_group_by_col_id"):
        if key in config:
            merged[key] = full_normalized[key]

    parent = merged.get("parent_slug") or ""
    if parent:
        error = validate_cot_parent_slug(cot.slug, parent)
        if error:
            raise ValidationError(error)

    save_nsm_config_document_for_cot(cot, {"rulebook": merged})


def load_rulebook_parent_map() -> dict[str, str]:
    """Return ``{child_slug: parent_slug}`` for deployed COT rulebooks."""
    from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks

    parent_map: dict[str, str] = {}
    for cot in iter_deployed_cot_rulebooks():
        parent_slug = resolve_rulebook_config_for_cot(cot).get("parent_slug") or ""
        if parent_slug:
            parent_map[cot.slug] = parent_slug
    return parent_map
