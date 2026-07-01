"""Bundle-driven discovery of expected COT slugs and setup health.

Phase A — Platform decoupling. Instead of gating on a hardcoded
``REQUIRED_COT_SLUGS`` list and ``core_bundle_applied("nsm_schema")``, the
Setup health derives the expected policy COT slugs from the *discovered* schema
bundles. Swapping ``bundles/builtin/`` (or adding ``bundle_paths``) changes the
expected schema without touching Python.

Rulebook COTs (``nsm_rb_*``) are excluded — they are deployed on demand, not
part of the policy-object baseline that Setup tracks.
"""

from __future__ import annotations

import json

from netbox_nsm.bundles.dispatch import (
    discover_schema_files,
    get_bundle_status,
    load_bundle,
)
from netbox_nsm.bundles.paths import bundle_slug_from_path

__all__ = (
    "discovered_schema_bundles",
    "discovered_cot_slugs",
    "discovered_policy_cot_slugs",
    "discovered_schema_bundle_slugs",
    "all_schema_bundles_applied",
)


def _is_rulebook_slug(slug: str) -> bool:
    return slug.startswith("nsm_rb_")


def discovered_schema_bundles() -> list[dict]:
    """Return loaded schema (JSON) bundles, each tagged with ``_slug``."""
    bundles: list[dict] = []
    for path in discover_schema_files():
        try:
            bundle = load_bundle(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        bundle["_slug"] = bundle_slug_from_path(path)
        bundles.append(bundle)
    return bundles


def discovered_schema_bundle_slugs() -> list[str]:
    """Return the slugs of every discovered schema bundle."""
    return [bundle["_slug"] for bundle in discovered_schema_bundles()]


def discovered_cot_slugs() -> list[str]:
    """Return every COT type slug declared across discovered schema bundles."""
    slugs: list[str] = []
    seen: set[str] = set()
    for bundle in discovered_schema_bundles():
        for type_def in bundle.get("types") or []:
            if not isinstance(type_def, dict):
                continue
            slug = str(type_def.get("slug", "")).strip()
            if not slug or slug in seen:
                continue
            seen.add(slug)
            slugs.append(slug)
    return slugs


def discovered_policy_cot_slugs() -> list[str]:
    """Return discovered policy-object COT slugs (rulebook COTs excluded)."""
    return [slug for slug in discovered_cot_slugs() if not _is_rulebook_slug(slug)]


def all_schema_bundles_applied() -> bool:
    """True when at least one schema bundle is discovered and all are applied."""
    slugs = discovered_schema_bundle_slugs()
    if not slugs:
        return False
    return all(get_bundle_status(slug) == "applied" for slug in slugs)
