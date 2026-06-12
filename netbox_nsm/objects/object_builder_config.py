"""Defaults and normalization for ``nsm_config.object_builder`` (``nsm_address`` only)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

__all__ = (
    "BUILDABLE_IPAM_STATUSES",
    "BUILDER_IGNORE_STATUS",
    "DEFAULT_OBJECT_BUILDER_CONFIG",
    "DEFAULT_OBJECT_BUILDER_STATUS_MAP",
    "IPAM_SOURCE_KEYS",
    "normalize_object_builder_config",
    "object_builder_config_from_spec",
)

BUILDER_IGNORE_STATUS = "ignore"

# Only these IPAM status values may be created by the Object Builder.
BUILDABLE_IPAM_STATUSES = frozenset({"active"})

IPAM_SOURCE_KEYS = (
    "ipam.ipaddress",
    "ipam.prefix",
    "ipam.iprange",
)

DEFAULT_OBJECT_BUILDER_STATUS_MAP = {
    "active": "active",
    "reserved": "reserved",
    "deprecated": "deprecated",
    "dhcp": BUILDER_IGNORE_STATUS,
    "slaac": BUILDER_IGNORE_STATUS,
    "container": BUILDER_IGNORE_STATUS,
}

DEFAULT_OBJECT_BUILDER_SOURCES = {
    "ipam.ipaddress": {
        "build_template": "H-{host}",
        "copy_description": True,
    },
    "ipam.prefix": {
        "build_template": "N-{network}-{prefix_length}",
    },
    "ipam.iprange": {
        "build_template": "R-{start_host}-{end_host}",
    },
}

DEFAULT_OBJECT_BUILDER_CONFIG = {
    "enabled": True,
    "status_map": DEFAULT_OBJECT_BUILDER_STATUS_MAP,
    "sources": DEFAULT_OBJECT_BUILDER_SOURCES,
}


def normalize_object_builder_config(raw: dict | None) -> dict[str, Any]:
    """Return a complete ``object_builder`` block with defaults applied."""
    base = deepcopy(DEFAULT_OBJECT_BUILDER_CONFIG)
    if not raw:
        return base

    if "enabled" in raw:
        base["enabled"] = bool(raw["enabled"])

    status_map = raw.get("status_map")
    if isinstance(status_map, dict):
        merged = dict(base["status_map"])
        for key, value in status_map.items():
            if value is not None:
                merged[str(key)] = str(value)
        base["status_map"] = merged

    sources = raw.get("sources")
    if isinstance(sources, dict):
        merged_sources = deepcopy(base["sources"])
        for source_key in IPAM_SOURCE_KEYS:
            source_def = sources.get(source_key)
            if not isinstance(source_def, dict):
                continue
            entry = dict(merged_sources.get(source_key, {}))
            if "build_template" in source_def:
                entry["build_template"] = str(source_def["build_template"] or "")
            if "copy_description" in source_def:
                entry["copy_description"] = bool(source_def["copy_description"])
            merged_sources[source_key] = entry
        base["sources"] = merged_sources

    return base


def object_builder_config_from_spec(spec: dict | None) -> dict[str, Any] | None:
    if not spec or "object_builder" not in spec:
        return None
    return normalize_object_builder_config(spec.get("object_builder"))
