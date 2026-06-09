"""Portable schema documents for netbox-custom-objects setup.

Canonical COT definitions live in ``schema/nsm_portable_schema.json`` in the
format described by netbox-custom-objects ``docs/portable-schema.md``. Setup
and sync apply that document via ``apply_document`` without transforming it.

``schema/nsm_choice_sets.json`` lists ``CustomFieldChoiceSet`` rows referenced
by ``choice_set`` fields in the schema.

``builtin_types.py`` retains only NSM-specific metadata that is *not* part of
the portable schema (areas/sections, TypeConfig hints, default seed objects).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

__all__ = (
    "SCHEMA_DIR",
    "build_choice_set_specs",
    "build_schema_document",
    "choice_set_names_in_document",
    "load_choice_set_specs",
    "load_portable_schema_document",
    "slugify_identifier",
    "iter_types",
    "type_slug",
)

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema"
PORTABLE_SCHEMA_PATH = SCHEMA_DIR / "nsm_portable_schema.json"
CHOICE_SETS_PATH = SCHEMA_DIR / "nsm_choice_sets.json"

# Areas that should be collapsed into a single combined section.
_AREA_COLLAPSE = {
    "source": "srcdst",
    "destination": "srcdst",
}


def _collapse_area(area):
    a = slugify_identifier(area)
    return _AREA_COLLAPSE.get(a, a)


def type_slug(base_name):
    """``"Addresses"`` -> ``"nsm_addresses"``."""
    return f"nsm_{slugify_identifier(base_name)}"


def iter_types(builtin_types):
    """Yield ``(typedef, base_slug, prefixed_slug, areas)`` for every type."""
    for typedef in builtin_types:
        base_slug = slugify_identifier(typedef.get("name", ""))
        raw_areas = typedef.get("areas") or (
            [typedef.get("area")] if typedef.get("area") else []
        )
        areas = []
        for a in raw_areas:
            collapsed = _collapse_area(a)
            if collapsed and collapsed not in areas:
                areas.append(collapsed)
        yield typedef, base_slug, type_slug(base_slug), areas


_IDENT_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_IDENT_COLLAPSE_RE = re.compile(r"_+")


def slugify_identifier(value):
    """Return a string matching ``^[a-z0-9]+(_[a-z0-9]+)*$``."""
    s = str(value or "").strip().lower()
    s = _IDENT_CLEAN_RE.sub("_", s)
    s = _IDENT_COLLAPSE_RE.sub("_", s).strip("_")
    return s or "x"


def _read_json(path: Path) -> dict | list:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_portable_schema_document(
    *,
    slugs: set[str] | None = None,
    include_rulebook_templates: bool = True,
) -> dict:
    """Load the bundled portable schema document (optionally filter by COT slug)."""
    document = _read_json(PORTABLE_SCHEMA_PATH)
    types = list(document.get("types", []))
    if include_rulebook_templates:
        from netbox_nsm.rulebooks.templates import build_rulebook_template_type_defs

        types.extend(build_rulebook_template_type_defs())
    if slugs is None:
        return {
            "schema_version": document.get("schema_version", "1"),
            "types": types,
        }
    filtered = [t for t in types if t.get("slug") in slugs]
    return {
        "schema_version": document.get("schema_version", "1"),
        "types": filtered,
    }


def load_choice_set_specs() -> list[dict]:
    """Load bundled choice-set definitions for schema apply."""
    data = _read_json(CHOICE_SETS_PATH)
    if not isinstance(data, list):
        raise ValueError(f"{CHOICE_SETS_PATH.name} must contain a JSON array")
    return data


def choice_set_names_in_document(document: dict) -> set[str]:
    names: set[str] = set()
    for type_def in document.get("types", []):
        for field_def in type_def.get("fields", []):
            choice_set = field_def.get("choice_set")
            if choice_set:
                names.add(str(choice_set))
    return names


def build_schema_document(builtin_types=None):
    """Return portable schema for setup/sync (full doc or subset by builtin typedef)."""
    if builtin_types is None:
        return load_portable_schema_document()
    slugs = {prefixed for _td, _bs, prefixed, _areas in iter_types(builtin_types)}
    return load_portable_schema_document(slugs=slugs)


def build_choice_set_specs(builtin_types=None):
    """Choice sets required by the schema document (all or subset)."""
    document = build_schema_document(builtin_types)
    needed = choice_set_names_in_document(document)
    return [spec for spec in load_choice_set_specs() if spec["name"] in needed]
