"""Parse, normalize, and compact ``rule_view`` overrides in rulebook ``nsm_config``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

__all__ = (
    "compact_rule_view_block",
    "compact_rulebook_types_map",
    "default_rule_view_for_slug",
    "is_default_rule_view_config",
    "normalize_rule_view_config",
)

_RULE_VIEW_KEYS = ("sort_order", "display_template", "areas")


def default_rule_view_for_slug(slug: str) -> dict[str, Any]:
    """Return bundled default ``rule_view`` for a policy COT slug."""
    from netbox_nsm.core.display_template import DEFAULT_DISPLAY_TEMPLATE
    from netbox_nsm.type_metadata.config import config_dict_from_spec
    from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG

    spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
    if not spec:
        return {
            "sort_order": 0,
            "display_template": DEFAULT_DISPLAY_TEMPLATE,
            "areas": [],
        }
    config = config_dict_from_spec(spec)
    rule_view = {
        "sort_order": int(config.get("sort_order", 0)),
        "display_template": config.get("display_template"),
    }
    if config.get("areas"):
        rule_view["areas"] = list(config["areas"])
    return rule_view


def normalize_rule_view_config(
    raw: dict | None,
    *,
    slug: str,
) -> dict[str, Any]:
    """Return a complete ``rule_view`` block with defaults applied for *slug*."""
    result = default_rule_view_for_slug(slug)
    if not raw:
        return result
    if "sort_order" in raw:
        result["sort_order"] = int(raw.get("sort_order", 0))
    if "display_template" in raw:
        from netbox_nsm.type_metadata.config import _normalized_display_template

        result["display_template"] = _normalized_display_template(
            raw.get("display_template")
        )
    if "areas" in raw:
        result["areas"] = list(raw.get("areas") or [])
    return result


def is_default_rule_view_config(rule_view: dict | None, *, slug: str) -> bool:
    return normalize_rule_view_config(rule_view, slug=slug) == default_rule_view_for_slug(
        slug
    )


def compact_rule_view_block(
    rule_view: dict | None,
    *,
    slug: str,
) -> dict[str, Any] | None:
    """Return only ``rule_view`` keys that differ from default, or ``None``."""
    if is_default_rule_view_config(rule_view, slug=slug):
        return None
    default = default_rule_view_for_slug(slug)
    normalized = normalize_rule_view_config(rule_view, slug=slug)
    diff: dict[str, Any] = {}
    for key in _RULE_VIEW_KEYS:
        if normalized.get(key) != default.get(key):
            diff[key] = deepcopy(normalized[key])
    return diff or None


def compact_rulebook_types_map(types_map: dict | None) -> dict[str, Any]:
    """Drop type entries whose ``rule_view`` matches bundled defaults."""
    if not isinstance(types_map, dict):
        return {}
    result: dict[str, Any] = {}
    for slug, block in types_map.items():
        if not isinstance(block, dict):
            continue
        compact_rv = compact_rule_view_block(block.get("rule_view"), slug=str(slug))
        if compact_rv is None:
            continue
        entry = dict(block)
        entry["rule_view"] = compact_rv
        result[str(slug)] = entry
    return result
