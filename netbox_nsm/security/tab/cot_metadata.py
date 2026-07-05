"""Resolve COT ``link_table`` from native fields or NSM metadata."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("netbox_nsm.tabs")

__all__ = ("cot_link_table_flag",)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _link_table_from_mapping(mapping: dict | None) -> bool:
    if not isinstance(mapping, dict):
        return False
    return _truthy(mapping.get("link_table"))


def _link_table_from_nsm_config_comments(cot) -> bool:
    try:
        from netbox_nsm.type_metadata.config import (
            _is_custom_object_type,
            parse_nsm_config_from_cot,
            resolve_nsm_config_dict_for_cot,
        )
    except ImportError:
        return False

    if not _is_custom_object_type(cot):
        return False

    try:
        cfg = resolve_nsm_config_dict_for_cot(cot)
        if _link_table_from_mapping(cfg):
            return True
    except Exception:
        logger.exception("could not read link_table from resolved nsm_config for %s", cot)

    try:
        parsed = parse_nsm_config_from_cot(cot)
        if _link_table_from_mapping(parsed):
            return True
    except Exception:
        logger.exception("could not parse link_table from COT comments for %s", cot)
    return False


def _link_table_from_cot_metadata_field(cot) -> bool:
    raw = getattr(cot, "metadata", None)
    if not raw or not str(raw).strip():
        return False
    try:
        import yaml

        document = yaml.safe_load(str(raw))
    except Exception:
        return False
    return _link_table_from_mapping(document if isinstance(document, dict) else None)


def cot_link_table_flag(cot) -> bool:
    """
    True when *cot* is an n:m link / junction table.

    Resolution order (first match wins):

    1. Native ``CustomObjectType.link_table`` when present (netbox-custom-objects PR #482).
    2. ``nsm_config`` in ``CustomObjectType.comments`` — top-level ``link_table``.
    3. Free-form ``CustomObjectType.metadata`` YAML/JSON with ``link_table: true``.
    """
    if cot is None:
        return False
    try:
        from netbox_nsm.type_metadata.config import _is_custom_object_type
    except ImportError:
        _is_custom_object_type = lambda obj: not getattr(obj, "custom_object_type", None)  # noqa: E731

    if not _is_custom_object_type(cot):
        return False
    try:
        if _truthy(getattr(cot, "link_table", False)):
            return True
    except Exception:
        pass
    if _link_table_from_nsm_config_comments(cot):
        return True
    return _link_table_from_cot_metadata_field(cot)
