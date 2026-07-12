"""Structural COT slug lists — instance metadata lives in bundle JSON / COT comments."""

from __future__ import annotations

import json
from pathlib import Path

__all__ = (
    "REQUIRED_COT_SLUGS",
    "RULEBOOK_TEMPLATE_SLUGS",
    "TYPECONFIG_LIST_EXCLUDED_SLUGS",
    "content_type_ids_for_cot_slugs",
)


def _schema_json_path() -> Path:
    return Path(__file__).resolve().parents[1] / "bundles" / "builtin" / "nsm_schema.json"


def _load_schema_document() -> dict:
    try:
        with _schema_json_path().open(encoding="utf-8") as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) else {}
    except Exception:
        return {}


def _load_required_cot_slugs_from_schema() -> list[str]:
    doc = _load_schema_document()
    slugs: list[str] = []
    for entry in doc.get("types") or []:
        if not isinstance(entry, dict):
            continue
        slug = str(entry.get("slug") or "").strip()
        if not slug or slug.startswith("nsm_rb_"):
            continue
        slugs.append(slug)
    return slugs


def _load_required_cot_slugs_from_db() -> list[str]:
    """Return deployed COT slugs from DB (runtime source of truth)."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except Exception:
        return []

    try:
        slugs = [
            str(slug).strip()
            for slug in CustomObjectType.objects.order_by("pk").values_list("slug", flat=True)
        ]
    except Exception:
        return []

    return [slug for slug in slugs if slug and slug.startswith("nsm_") and not slug.startswith("nsm_rb_")]


def _load_typeconfig_excluded_slugs_from_schema() -> frozenset[str]:
    doc = _load_schema_document()
    metadata_types = ((doc.get("metadata") or {}).get("types") or {})
    if isinstance(metadata_types, dict):
        excluded = {
            str(slug).strip()
            for slug, block in metadata_types.items()
            if isinstance(block, dict) and bool(block.get("link_table"))
        }
        if excluded:
            return frozenset(excluded)
    # Safe fallback when schema metadata is unavailable.
    return frozenset({"nsm_object_link"})


def _load_typeconfig_excluded_slugs_from_db() -> frozenset[str]:
    """Return slugs hidden from typeconfig list based on deployed COT flags."""
    try:
        from netbox_custom_objects.models import CustomObjectType
    except Exception:
        return frozenset()

    try:
        if hasattr(CustomObjectType, "link_table"):
            slugs = {
                str(slug).strip()
                for slug in CustomObjectType.objects.filter(link_table=True).values_list("slug", flat=True)
                if slug
            }
            return frozenset(slugs)
    except Exception:
        return frozenset()
    return frozenset()


TYPECONFIG_LIST_EXCLUDED_SLUGS: frozenset[str] = (
    _load_typeconfig_excluded_slugs_from_db()
    or _load_typeconfig_excluded_slugs_from_schema()
)


def content_type_ids_for_cot_slugs(slugs) -> list[int]:
    """Resolve COT slugs to Django ContentType PKs (skips missing types)."""
    try:
        from django.contrib.contenttypes.models import ContentType
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        return []

    ids: list[int] = []
    for slug in slugs:
        try:
            cot = CustomObjectType.objects.get(slug=slug)
            ct = ContentType.objects.get_for_model(cot.get_model())
            ids.append(ct.pk)
        except Exception:
            continue
    return ids


REQUIRED_COT_SLUGS = _load_required_cot_slugs_from_db() or _load_required_cot_slugs_from_schema() or [
    "nsm_action",
    "nsm_service",
    "nsm_service_group",
    "nsm_address",
    "nsm_address_custom",
    "nsm_address_group",
    "nsm_label",
    "nsm_zone",
    "nsm_app_business",
    "nsm_app_network",
    "nsm_object_link",
]

from netbox_nsm.rulebooks.templates import RULEBOOK_TEMPLATE_SLUGS  # noqa: E402
