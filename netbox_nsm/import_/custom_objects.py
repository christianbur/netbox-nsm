"""Setup: bundle status helpers and COT setup group metadata."""

from __future__ import annotations

from django.db.utils import OperationalError, ProgrammingError
from django.utils.translation import gettext_lazy as _

from netbox_nsm.bundles.schema_builder import (
    build_portable_schema_preview_types,
    export_portable_schema_yaml,
)
from netbox_nsm.objects.type_config_specs import REQUIRED_COT_SLUGS
from netbox_nsm.bundles.dispatch import get_bundle_status, list_setup_bundles, load_bundle
from netbox_nsm.bundles.paths import bundle_json_path

NSM_PANEL_COT_SLUGS = ("nsm_object_link",)

COT_BUILTIN_OBJECT_SLUGS = tuple(
    slug for slug in REQUIRED_COT_SLUGS if slug not in NSM_PANEL_COT_SLUGS
)

COT_GROUP_OBJECTS = {
    "id": "objects",
    "label": _("Security Objects"),
    "description": _(
        "Built-in policy object types (zones, addresses, services, actions, …)."
    ),
}

COT_GROUP_NSM_PANEL = {
    "id": "nsm_panel",
    "label": _("NSM Panel"),
    "description": _(
        "Panel assignment links (inventory ↔ policy objects)."
    ),
}

COT_SETUP_GROUPS = (
    COT_GROUP_OBJECTS,
    COT_GROUP_NSM_PANEL,
)


def core_bundle_applied() -> bool:
    return get_bundle_status("nsm_schema") == "applied"


__all__ = (
    "COT_GROUP_OBJECTS",
    "COT_GROUP_NSM_PANEL",
    "COT_SETUP_GROUPS",
    "COT_BUILTIN_OBJECT_SLUGS",
    "NSM_PANEL_COT_SLUGS",
    "all_cots_ok",
    "core_bundle_applied",
    "custom_objects_db_ready",
    "custom_objects_plugin_loaded",
    "empty_cot_status",
    "get_builtin_object_entries",
    "get_cot_schema_preview",
    "get_cot_schema_yaml",
    "get_cot_setup_groups",
    "get_cot_status",
    "get_nsm_panel_entries",
    "get_schema_bundles",
    "handles_action",
    "handle_custom_objects_action",
)


def custom_objects_plugin_loaded() -> bool:
    try:
        import netbox_custom_objects  # noqa: F401

        return True
    except ImportError:
        return False


def custom_objects_db_ready() -> bool:
    if not custom_objects_plugin_loaded():
        return False
    try:
        from netbox_custom_objects.models import CustomObjectType

        CustomObjectType.objects.exists()
        return True
    except (ProgrammingError, OperationalError):
        return False


def empty_cot_status():
    return {slug: None for slug in REQUIRED_COT_SLUGS}


def get_cot_status():
    if not custom_objects_db_ready():
        return empty_cot_status()
    try:
        from netbox_custom_objects.models import CustomObjectType

        existing = {
            cot.slug: cot
            for cot in CustomObjectType.objects.filter(slug__in=REQUIRED_COT_SLUGS)
        }
        return {slug: existing.get(slug) for slug in REQUIRED_COT_SLUGS}
    except (ProgrammingError, OperationalError):
        return empty_cot_status()


def _type_metadata_by_slug() -> dict[str, dict]:
    bundle = load_bundle(bundle_json_path("nsm_schema"))
    return {
        str(type_def.get("slug", "")): type_def
        for type_def in bundle.get("types") or []
        if isinstance(type_def, dict) and type_def.get("slug")
    }


def get_builtin_object_entries(*, cot_status=None):
    if cot_status is None:
        cot_status = empty_cot_status()
    metadata = _type_metadata_by_slug()
    return [
        {
            "slug": slug,
            "label": metadata.get(slug, {}).get("verbose_name", slug),
            "description": metadata.get(slug, {}).get("description", ""),
            "cot": cot_status.get(slug),
        }
        for slug in COT_BUILTIN_OBJECT_SLUGS
    ]


def get_nsm_panel_entries(*, cot_status=None):
    if cot_status is None:
        cot_status = empty_cot_status()
    metadata = _type_metadata_by_slug()
    return [
        {
            "slug": slug,
            "label": metadata.get(slug, {}).get("verbose_name", slug),
            "description": metadata.get(slug, {}).get("description", ""),
            "cot": cot_status.get(slug),
        }
        for slug in NSM_PANEL_COT_SLUGS
    ]


def get_cot_schema_yaml() -> str:
    return export_portable_schema_yaml(slugs=set(REQUIRED_COT_SLUGS))


def get_cot_schema_preview() -> list[dict]:
    return build_portable_schema_preview_types(slugs=set(REQUIRED_COT_SLUGS))


def get_cot_setup_groups(*, cot_status=None, rulebook_template_status=None):
    del rulebook_template_status
    if cot_status is None:
        cot_status = empty_cot_status()
    return [
        {
            **COT_GROUP_OBJECTS,
            "entries": get_builtin_object_entries(cot_status=cot_status),
        },
        {
            **COT_GROUP_NSM_PANEL,
            "entries": get_nsm_panel_entries(cot_status=cot_status),
        },
    ]


def all_cots_ok(cot_status, rulebook_template_status=None) -> bool:
    del rulebook_template_status
    if not all(v is not None for v in cot_status.values()):
        return False
    return core_bundle_applied()


def get_schema_bundles():
    return list_setup_bundles()


def handles_action(action: str) -> bool:
    return False


def handle_custom_objects_action(request, action: str):
    del request, action
    return None
