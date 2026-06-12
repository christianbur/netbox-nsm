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
    "build_portable_schema_preview_types",
    "build_schema_document",
    "choice_set_names_in_document",
    "export_portable_schema_yaml",
    "load_choice_set_specs",
    "load_portable_schema_document",
    "parse_custom_objects_schema_yaml",
    "prepare_document_for_apply",
    "slugify_identifier",
    "strip_nsm_config_sidecars",
    "validate_custom_objects_schema_yaml",
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


def export_portable_schema_yaml(
    *,
    slugs: set[str] | None = None,
    include_rulebook_templates: bool = False,
) -> str:
    """Return portable schema as YAML with ``comments.nsm_config`` per UI type."""
    import yaml

    from netbox_nsm.objects.nsm_config import (
        config_dict_from_spec,
        format_type_comments_for_setup_yaml,
    )
    from netbox_nsm.objects.type_config_specs import (
        TYPECONFIG_LIST_EXCLUDED_SLUGS,
        TYPECONFIG_SPEC_BY_SLUG,
    )

    document = load_portable_schema_document(
        slugs=slugs,
        include_rulebook_templates=include_rulebook_templates,
    )
    types_for_export: list[dict] = []
    for type_def in document.get("types", []):
        export_def = dict(type_def)
        slug = export_def.get("slug", "")
        spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
        if spec and slug not in TYPECONFIG_LIST_EXCLUDED_SLUGS:
            export_def["comments"] = format_type_comments_for_setup_yaml(
                config_dict_from_spec(spec)
            )
        types_for_export.append(export_def)
    payload = {
        "schema_version": document["schema_version"],
        "types": types_for_export,
    }
    return (
        yaml.dump(
            payload,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
        + "\n"
    )


def build_portable_schema_preview_types(
    *,
    slugs: set[str] | None = None,
    include_rulebook_templates: bool = False,
) -> list[dict]:
    """Human-readable preview rows per bundled COT type (slug, label, fields)."""
    from netbox_nsm.objects.nsm_config import (
        build_nsm_config_preview_rows,
        config_dict_from_spec,
        format_nsm_config_comment_yaml,
    )
    from netbox_nsm.objects.type_config_specs import (
        TYPECONFIG_LIST_EXCLUDED_SLUGS,
        TYPECONFIG_SPEC_BY_SLUG,
    )

    document = load_portable_schema_document(
        slugs=slugs,
        include_rulebook_templates=include_rulebook_templates,
    )
    preview_types: list[dict] = []
    for type_def in document.get("types", []):
        slug = type_def.get("slug", "")
        fields: list[dict] = []
        for field_def in type_def.get("fields", []):
            fields.append(
                {
                    "name": field_def.get("name", ""),
                    "label": field_def.get("label") or field_def.get("name", ""),
                    "type": field_def.get("type", ""),
                    "required": bool(field_def.get("required")),
                }
            )
        spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
        nsm_config_yaml = ""
        nsm_config_preview: list[dict] = []
        if spec and slug not in TYPECONFIG_LIST_EXCLUDED_SLUGS:
            from netbox_nsm.objects.nsm_config import NsmTypeConfig

            spec_config = config_dict_from_spec(spec)
            cfg = NsmTypeConfig(
                slug=slug,
                content_type_id=0,
                name=spec["label"],
                sort_order=spec_config["sort_order"],
                display_template=spec_config["display_template"],
            )
            nsm_config_yaml = format_nsm_config_comment_yaml(
                config_dict_from_spec(spec)
            ).rstrip()
            nsm_config_preview = build_nsm_config_preview_rows(cfg)
        preview_types.append(
            {
                "slug": slug,
                "label": type_def.get("verbose_name") or slug,
                "description": type_def.get("description", ""),
                "group_name": type_def.get("group_name", ""),
                "fields": fields,
                "nsm_config_yaml": nsm_config_yaml,
                "nsm_config_preview": nsm_config_preview,
            }
        )
    return preview_types


def parse_custom_objects_schema_yaml(yaml_text: str) -> dict:
    """Parse setup portable-schema YAML."""
    import yaml

    document = yaml.safe_load(yaml_text or "")
    if not isinstance(document, dict):
        raise ValueError("Schema YAML must be a mapping.")
    if "types" not in document:
        raise ValueError("Schema YAML must contain a 'types' key.")
    if not isinstance(document.get("types"), list):
        raise ValueError("'types' must be a list.")
    return document


def _validate_nsm_config_block(config: dict, *, slug: str) -> None:
    from netbox_nsm.objects.nsm_config import normalize_nsm_config_list

    if normalize_nsm_config_list(config) is None:
        raise ValueError(
            f"Invalid nsm_config for type '{slug}' (expected rule_view and panel blocks)."
        )


def validate_custom_objects_schema_yaml(yaml_text: str) -> dict:
    """Validate setup schema YAML and return the parsed document."""
    from netbox_nsm.objects.nsm_config import extract_nsm_config_from_type_comments

    document = parse_custom_objects_schema_yaml(yaml_text)
    for type_def in document.get("types", []):
        if not isinstance(type_def, dict):
            raise ValueError("Each type entry must be a mapping.")
        slug = type_def.get("slug") or "<unknown>"
        if not type_def.get("slug"):
            raise ValueError("Each type must define 'slug'.")
        comments = type_def.get("comments")
        if comments is None:
            continue
        config = extract_nsm_config_from_type_comments(type_def)
        if config is None and comments:
            raise ValueError(
                f"Type '{slug}' has comments but no valid nsm_config block."
            )
        if config is not None:
            comments_list = comments if isinstance(comments, list) else []
            for entry in comments_list:
                if isinstance(entry, dict) and "nsm_config" in entry:
                    _validate_nsm_config_block(entry["nsm_config"], slug=slug)
    return document


def strip_nsm_config_sidecars(document: dict) -> tuple[dict, dict[str, dict]]:
    """Return apply-ready document and per-slug nsm_config payloads."""
    from copy import deepcopy

    from netbox_nsm.objects.nsm_config import extract_nsm_config_from_type_comments

    apply_doc = deepcopy(document)
    configs_by_slug: dict[str, dict] = {}
    cleaned_types: list[dict] = []
    for type_def in apply_doc.get("types", []):
        slug = type_def.get("slug", "")
        config = extract_nsm_config_from_type_comments(type_def)
        if config is not None and slug:
            configs_by_slug[slug] = config
        cleaned = dict(type_def)
        cleaned.pop("comments", None)
        cleaned_types.append(cleaned)
    apply_doc["types"] = cleaned_types
    return apply_doc, configs_by_slug


def prepare_document_for_apply(yaml_text: str) -> tuple[dict, dict[str, dict]]:
    """Validate YAML and return document for apply plus nsm_config sidecars."""
    document = validate_custom_objects_schema_yaml(yaml_text)
    return strip_nsm_config_sidecars(document)
