"""Discover, preview, and apply NSM schema JSON bundles."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from django.db import transaction

from netbox_nsm.bundles.paths import bundle_json_path

__all__ = (
    "BUNDLE_FORMAT_JSON",
    "BUNDLE_FORMAT_PYTHON",
    "apply_bundle",
    "bundle_json_path",
    "bundle_slug_from_path",
    "discover_schema_files",
    "get_bundle_status",
    "load_bundle",
    "list_bundles",
    "list_setup_bundles",
    "normalize_bundle_metadata",
    "organize_bundles_tree",
    "preview_bundle",
    "sync_metadata",
    "to_portable_document",
)

BUNDLE_FORMAT_JSON = "json"
BUNDLE_FORMAT_PYTHON = "python"

_BUNDLE_SORT_ORDER = {
    "nsm_schema": 0,
    "nsm_demo_zone_matrix": 30,
    "nsm_demo_zone_address_adressgroup": 40,
}


# ---------------------------------------------------------------------------
# Low-level loaders
# ---------------------------------------------------------------------------


def discover_schema_files() -> list[Path]:
    """Return ``bundle.json`` paths for discovered schema bundles (sorted by slug)."""
    from netbox_nsm.bundles.paths import find_bundle_dirs

    paths: list[Path] = []
    for slug, bundle_dir in sorted(find_bundle_dirs().items()):
        bundle_json = bundle_dir / "bundle.json"
        if not bundle_json.is_file():
            continue
        try:
            bundle = load_bundle(bundle_json)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if bundle.get("bundle_kind", "schema") == "schema":
            paths.append(bundle_json)
    return paths


def bundle_slug_from_path(path: Path | str) -> str:
    return Path(path).stem


def load_bundle(path: Path | str) -> dict:
    bundle_path = Path(path)
    with bundle_path.open(encoding="utf-8") as fh:
        document = json.load(fh)
    if not isinstance(document, dict):
        raise ValueError(f"{bundle_path.name}: root must be a JSON object.")
    if document.get("schema_type") != "nsm":
        raise ValueError(f"{bundle_path.name}: schema_type must be 'nsm'.")
    if str(document.get("schema_version", "")) != "1":
        raise ValueError(f"{bundle_path.name}: schema_version must be '1'.")
    bundle_kind = document.get("bundle_kind", "schema")
    if bundle_kind not in ("schema", "python"):
        raise ValueError(
            f"{bundle_path.name}: bundle_kind must be 'schema' or 'python', "
            f"got {bundle_kind!r}."
        )
    return document


def normalize_bundle_metadata(bundle: dict) -> dict:
    """Return the bundle ``metadata`` block."""
    metadata = bundle.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return {}


def to_portable_document(bundle: dict) -> dict:
    """Extract COT portable-schema payload from an NSM bundle."""
    document: dict[str, Any] = {
        "schema_version": str(bundle.get("schema_version", "1")),
    }
    for key in ("choice_sets", "types", "objects"):
        if key in bundle and bundle[key]:
            document[key] = deepcopy(bundle[key])
    if "types" not in document:
        document["types"] = []
    return document


# ---------------------------------------------------------------------------
# Bundle status
# ---------------------------------------------------------------------------


def _get_cot_by_slug(slug: str):
    from netbox_custom_objects.models import CustomObjectType

    return CustomObjectType.objects.filter(slug=slug).first()


def get_bundle_status(slug: str) -> str:
    """Return ``missing``, ``partial``, or ``applied`` for bundle *slug*."""
    from netbox_nsm.bundles.paths import find_bundle_dirs

    bundle_dirs = find_bundle_dirs()
    if slug not in bundle_dirs:
        return "missing"

    bundle_json = bundle_dirs[slug] / "bundle.json"
    try:
        bundle = load_bundle(bundle_json)
    except (OSError, ValueError, json.JSONDecodeError):
        return "missing"

    # Python bundles have no schema types to check
    if bundle.get("bundle_kind") == "python":
        return "applied"

    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return "missing"

    type_slugs = {
        str(t.get("slug", "")).strip()
        for t in bundle.get("types") or []
        if isinstance(t, dict) and t.get("slug")
    }
    if not type_slugs:
        return "applied"

    existing = set(
        CustomObjectType.objects.filter(slug__in=type_slugs).values_list(
            "slug", flat=True
        )
    )
    if not existing:
        return "missing"
    if existing == type_slugs:
        return "applied"
    return "partial"


# ---------------------------------------------------------------------------
# Bundle summaries
# ---------------------------------------------------------------------------


def _normalize_require_slugs(requires: list | None) -> list[str]:
    return [str(req).removesuffix(".json") for req in (requires or [])]


def _check_requires(bundle: dict) -> list[str]:
    missing: list[str] = []
    for req_slug in _normalize_require_slugs(bundle.get("requires")):
        if get_bundle_status(req_slug) != "applied":
            missing.append(req_slug)
    return missing


def _schema_bundle_summary(bundle: dict) -> dict:
    """Summary dict for a schema (JSON) bundle."""
    slug = bundle.get("_slug", "")
    metadata = normalize_bundle_metadata(bundle)
    return {
        "slug": slug,
        "title": bundle.get("title") or slug,
        "description": bundle.get("description") or "",
        "requires": _normalize_require_slugs(bundle.get("requires")),
        "format": BUNDLE_FORMAT_JSON,
        "action": "",
        "needs_confirm": False,
        "confirm_label": "",
        "type_count": len(bundle.get("types") or []),
        "choice_set_count": len(bundle.get("choice_sets") or []),
        "object_count": sum(
            len(entry.get("records") or [])
            for entry in (bundle.get("objects") or [])
            if isinstance(entry, dict)
        ),
        "metadata_type_count": len(metadata.get("types") or {}),
        "metadata_rulebook_count": len(metadata.get("rulebooks") or {}),
        "status": get_bundle_status(slug) if slug else "missing",
        "missing_requires": _check_requires(bundle) if slug else [],
    }


def _python_bundle_summary(bundle: dict) -> dict:
    """Summary dict for a Python bundle."""
    slug = bundle.get("_slug", "")
    requires = _normalize_require_slugs(bundle.get("requires"))
    stub = {"requires": requires}
    return {
        "slug": slug,
        "title": bundle.get("title") or slug,
        "description": bundle.get("description") or "",
        "requires": requires,
        "format": BUNDLE_FORMAT_PYTHON,
        "action": "run_bundle",
        "needs_confirm": bool(bundle.get("needs_confirm")),
        "confirm_label": bundle.get("confirm_label") or "",
        "type_count": None,
        "choice_set_count": None,
        "object_count": None,
        "metadata_type_count": None,
        "metadata_rulebook_count": None,
        "status": None,
        "missing_requires": _check_requires(stub),
    }


def bundle_summary(bundle: dict) -> dict:
    """Return a UI-ready summary dict for a bundle (schema or python)."""
    if bundle.get("bundle_kind") == "python":
        return _python_bundle_summary(bundle)
    return _schema_bundle_summary(bundle)


# ---------------------------------------------------------------------------
# Tree ordering
# ---------------------------------------------------------------------------


def _bundle_sort_key(bundle: dict) -> tuple:
    return (_BUNDLE_SORT_ORDER.get(bundle["slug"], 100), bundle["slug"])


def organize_bundles_tree(bundles: list[dict]) -> list[dict]:
    """Return *bundles* in tree order with a ``depth`` key for UI indentation."""
    by_slug = {bundle["slug"]: bundle for bundle in bundles}
    children: dict[str, list[dict]] = {}
    roots: list[dict] = []

    for bundle in bundles:
        parent_slug = None
        for req_slug in bundle.get("requires") or []:
            if req_slug in by_slug:
                parent_slug = req_slug
                break
        if parent_slug:
            children.setdefault(parent_slug, []).append(bundle)
        else:
            roots.append(bundle)

    for slug in children:
        children[slug].sort(key=_bundle_sort_key)
    roots.sort(key=_bundle_sort_key)

    ordered: list[dict] = []

    def walk(node: dict, depth: int) -> None:
        entry = dict(node)
        entry["depth"] = depth
        ordered.append(entry)
        for child in children.get(node["slug"], []):
            walk(child, depth + 1)

    for root in roots:
        walk(root, 0)
    return ordered


# ---------------------------------------------------------------------------
# Preview and apply
# ---------------------------------------------------------------------------


def preview_bundle(
    bundle: dict,
    *,
    allow_destructive: bool = False,
) -> dict:
    from netbox_custom_objects.schema.executor import diff_document

    from netbox_nsm.bundles.bundle_extensions import (
        diff_choice_sets,
        diff_seed_objects,
        serialize_cot_diffs,
    )

    portable = to_portable_document(bundle)
    cot_diffs = diff_document(portable)
    return {
        "portable_document": portable,
        "cot_diff": serialize_cot_diffs(cot_diffs),
        "choice_set_diff": diff_choice_sets(bundle.get("choice_sets")),
        "object_diff": diff_seed_objects(bundle.get("objects")),
        "destructive_blocked": (
            not allow_destructive
            and any(d.has_destructive_changes for d in cot_diffs)
        ),
        "metadata": deepcopy(normalize_bundle_metadata(bundle)),
    }


def apply_bundle(
    bundle: dict,
    *,
    allow_destructive: bool = False,
) -> dict:
    from netbox_custom_objects.schema.executor import apply_document

    missing = _check_requires(bundle)
    if missing:
        raise ValueError(
            f"Missing required bundles: {', '.join(missing)}. Apply them first."
        )

    from netbox_nsm.bundles.bundle_extensions import (
        apply_choice_sets,
        apply_seed_objects,
    )

    portable = to_portable_document(bundle)
    metadata = normalize_bundle_metadata(bundle)
    with transaction.atomic():
        choice_sets_applied = apply_choice_sets(bundle.get("choice_sets"))
        apply_document(portable, allow_destructive=allow_destructive)
        objects_seeded = apply_seed_objects(bundle.get("objects"))
        meta_counts = sync_metadata(metadata)

    from netbox_nsm.rulebooks.rulebook_groups import sync_all_rulebook_cots

    sync_all_rulebook_cots()

    return {
        "types_applied": len(portable.get("types") or []),
        "choice_sets_applied": choice_sets_applied,
        "objects_seeded": objects_seeded,
        "metadata_types_synced": meta_counts["types"],
        "metadata_rulebooks_synced": meta_counts["rulebooks"],
    }


# ---------------------------------------------------------------------------
# Discovery and listing
# ---------------------------------------------------------------------------


def list_bundles() -> list[dict]:
    """Discover all bundles via paths.py and return a list of summary dicts."""
    from netbox_nsm.bundles.paths import find_bundle_dirs

    items: list[dict] = []
    for slug, bundle_dir in find_bundle_dirs().items():
        try:
            bundle = load_bundle(bundle_dir / "bundle.json")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        bundle["_slug"] = slug
        items.append(bundle_summary(bundle))
    return items


def list_setup_bundles() -> list[dict]:
    """All discovered bundles ordered as a dependency tree."""
    return organize_bundles_tree(list_bundles())


# ---------------------------------------------------------------------------
# Metadata sync
# ---------------------------------------------------------------------------


def sync_metadata(metadata: dict | None) -> dict[str, int]:
    """Write bundle ``metadata`` into COT ``comments`` (via ``nsm_config`` YAML)."""
    from netbox_nsm.objects.nsm_config import save_nsm_config_document_for_cot

    if not metadata:
        return {"types": 0, "rulebooks": 0}

    types_count = 0
    for slug, block in (metadata.get("types") or {}).items():
        if not isinstance(block, dict):
            continue
        cot = _get_cot_by_slug(slug)
        if cot is None:
            continue
        if "link_table" in block and hasattr(cot, "link_table"):
            cot.link_table = bool(block["link_table"])
            cot.save(update_fields=["link_table"])
            types_count += 1
        updates: dict[str, Any] = {}
        if "links" in block:
            updates["links"] = block["links"]
        if "role" in block:
            updates["role"] = block["role"]
        if not updates:
            continue
        save_nsm_config_document_for_cot(cot, updates)
        types_count += 1

    rulebooks_count = 0
    for rulebook_slug, block in (metadata.get("rulebooks") or {}).items():
        if not isinstance(block, dict):
            continue
        rb_slug = str(rulebook_slug)
        if not rb_slug.startswith("nsm_rb_"):
            continue
        if str(rulebook_slug).endswith("_template"):
            continue
        cot = _get_cot_by_slug(rulebook_slug)
        if cot is None:
            continue
        updates: dict[str, Any] = {}
        if "rulebook" in block:
            updates["rulebook"] = block["rulebook"]
        if "types" in block:
            updates["types"] = block["types"]
        if "role" in block:
            updates["role"] = block["role"]
        if not updates:
            continue
        save_nsm_config_document_for_cot(cot, updates)
        rulebooks_count += 1

    from netbox_nsm.core.display_utils import get_display_template_map

    get_display_template_map.cache_clear()
    return {"types": types_count, "rulebooks": rulebooks_count}
