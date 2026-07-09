"""Shared helpers for integration tests (NSM schema/rulebook prerequisites)."""

from __future__ import annotations

from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError

from netbox_custom_objects.models import CustomObjectType
from netbox_custom_objects.schema.executor import apply_document

from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.bundles.schema_builder import (
    iter_types,
    slugify_identifier,
)
from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS
from netbox_nsm.rulebooks.templates import (
    RULEBOOK_TEMPLATE_SLUGS,
    build_rulebook_document,
    build_rulebook_document_from_schema,
    build_rulebook_template_type_defs,
    default_rulebook_schema_yaml,
    format_rulebook_display_name,
)


def _expected_cot_slugs() -> list[str]:
    """Discovered policy COT slugs (Phase A), falling back to the static list."""
    try:
        from netbox_nsm.bundles.discovery import discovered_policy_cot_slugs

        discovered = discovered_policy_cot_slugs()
    except Exception:
        discovered = []
    return discovered or list(REQUIRED_COT_SLUGS)

__all__ = (
    "ensure_nsm_prerequisites",
    "ensure_rulebook_cot",
    "ensure_zone_address_rulebook_deployed",
    "get_cot_field_through_model",
    "get_cot_model",
    "resolve_rulebook_address_field_names",
    "resolve_rulebook_zone_field_names",
)


def _custom_objects_db_ready() -> bool:
    try:
        import netbox_custom_objects  # noqa: F401

        CustomObjectType.objects.exists()
        return True
    except (ImportError, ProgrammingError, OperationalError):
        return False


def _cot_status() -> dict[str, CustomObjectType | None]:
    slugs = _expected_cot_slugs()
    if not _custom_objects_db_ready():
        return {slug: None for slug in slugs}
    existing = {
        cot.slug: cot
        for cot in CustomObjectType.objects.filter(slug__in=slugs)
    }
    return {slug: existing.get(slug) for slug in slugs}


def _all_cots_ok(cot_status: dict) -> bool:
    return _custom_objects_db_ready() and all(v is not None for v in cot_status.values())


def _ensure_choice_sets(specs) -> None:
    from extras.models import CustomFieldChoiceSet

    for spec in specs:
        extra_choices = [(c, c) for c in spec["choices"]]
        CustomFieldChoiceSet.objects.update_or_create(
            name=spec["name"],
            defaults={"extra_choices": extra_choices},
        )


def _seed_default_objects(builtin_types) -> None:
    for typedef, _base_slug, slug, _areas in iter_types(builtin_types):
        defaults_list = typedef.get("default_objects") or []
        if not defaults_list:
            continue
        try:
            cot = CustomObjectType.objects.get(slug=slug)
        except CustomObjectType.DoesNotExist:
            continue
        model = cot.get_model()
        for entry in defaults_list:
            if not isinstance(entry, dict):
                continue
            obj_name = str(entry.get("name", "")).strip()
            if not obj_name:
                continue
            payload = {"name": obj_name}
            for key, value in (entry.get("field_data") or {}).items():
                payload[slugify_identifier(key)] = value
            try:
                model.objects.update_or_create(name=obj_name, defaults=payload)
            except Exception:
                continue


def _import_all_types() -> None:
    from netbox_nsm.bundles.dispatch import apply_bundle, load_bundle
    from netbox_nsm.bundles.paths import bundle_json_path

    bundle = load_bundle(bundle_json_path("nsm_schema"))
    apply_bundle(bundle, allow_destructive=True)


def _create_all_typeconfigs() -> None:
    from netbox_nsm.type_metadata.config import apply_schema_bundle_metadata

    apply_schema_bundle_metadata()


def _typeconfigs_ok(cot_status: dict) -> bool:
    from netbox_nsm.type_metadata.config import has_nsm_config_in_comments

    if not _all_cots_ok(cot_status):
        return False
    for slug in _expected_cot_slugs():
        cot = cot_status.get(slug)
        if cot is None:
            return False
        if not has_nsm_config_in_comments(cot.comments or ""):
            return False
    return True


def _ensure_rulebook_templates() -> None:
    missing = [
        slug
        for slug in RULEBOOK_TEMPLATE_SLUGS
        if not CustomObjectType.objects.filter(slug=slug).exists()
    ]
    if not missing:
        return
    document = {
        "schema_version": "1",
        "types": [
            type_def
            for type_def in build_rulebook_template_type_defs()
            if type_def["slug"] in missing
        ],
    }
    apply_document(document, allow_destructive=False)


def _ensure_builtin_default_objects() -> None:
    needs_seed = False
    for slug in ("nsm_action", "nsm_service", "nsm_zone"):
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is None or not cot.get_model().objects.exists():
            needs_seed = True
            break
    if needs_seed:
        _seed_default_objects(BUILTIN_CUSTOM_TYPES)


def ensure_nsm_prerequisites() -> None:
    """Import bundled COT types, TypeConfigs, templates, and default objects if needed."""
    if not _custom_objects_db_ready():
        raise RuntimeError(
            "netbox-custom-objects database tables are missing "
            "(migrate netbox_custom_objects first)."
        )

    cot_status = _cot_status()
    if not _all_cots_ok(cot_status):
        _import_all_types()
    else:
        _ensure_builtin_default_objects()

    cot_status = _cot_status()
    if not _typeconfigs_ok(cot_status):
        _create_all_typeconfigs()

    _ensure_rulebook_templates()


def get_cot_model(*slugs: str):
    """Return the dynamic model for the first existing COT slug."""
    for slug in slugs:
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is not None:
            return cot.get_model(), cot
    raise RuntimeError(
        f"Missing Custom Object Type (tried: {', '.join(slugs)}). "
        "Apply the NSM Schema bundle first (Security → Configuration → Bundles)."
    )


def get_cot_field_through_model(cot, field_name: str):
    """Return the dynamic M2M through model for a COT multiobject field."""
    from django.apps import apps

    from netbox_custom_objects import constants

    field = cot.fields.get(name=field_name)
    return apps.get_model(constants.APP_LABEL, field.through_model_name)


def resolve_rulebook_address_field_names(cot) -> tuple[str, str]:
    """Return source/destination field names for address + address-group refs."""
    field_names = set(cot.fields.values_list("name", flat=True))
    if "source_addresses" in field_names:
        return "source_addresses", "destination_addresses"
    return "source", "destination"


def resolve_rulebook_zone_field_names(cot) -> tuple[str, str]:
    """Return source/destination field names for zone refs."""
    field_names = set(cot.fields.values_list("name", flat=True))
    if "source_zones" in field_names:
        return "source_zones", "destination_zones"
    return "source", "destination"


def ensure_rulebook_cot(
    *,
    slug: str,
    template_slug: str | None = None,
    schema_yaml: str | None = None,
    display_name: str,
    literal_verbose_name: bool = False,
) -> CustomObjectType:
    """Deploy a concrete ``nsm_rb_*`` rulebook COT from a template or YAML schema."""
    existing = CustomObjectType.objects.filter(slug=slug).first()
    if existing is not None:
        return existing

    verbose_name = (
        display_name.strip()
        if literal_verbose_name
        else format_rulebook_display_name(display_name)
    )
    if schema_yaml is not None:
        from netbox_nsm.rulebooks.templates import parse_rulebook_schema_yaml

        schema_type_def = parse_rulebook_schema_yaml(schema_yaml)
        document = build_rulebook_document_from_schema(
            schema_type_def=schema_type_def,
            rulebook_slug=slug,
            verbose_name=verbose_name,
        )
    else:
        document = build_rulebook_document(
            template_slug=template_slug or "",
            rulebook_slug=slug,
            verbose_name=verbose_name,
        )
    apply_document(document, allow_destructive=False)
    return CustomObjectType.objects.get(slug=slug)


def ensure_zone_address_rulebook_deployed():
    """Deploy ``nsm_rb_demo_zone_addresses`` COT + metadata from the demo bundle."""
    from netbox_nsm.bundles.dispatch import apply_bundle, load_bundle
    from netbox_nsm.bundles.paths import bundle_json_path
    from netbox_nsm.rulebooks.templates import DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG

    existing = CustomObjectType.objects.filter(slug=DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG).first()
    if existing is not None:
        return existing

    bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
    schema_bundle = {**bundle, "bundle_kind": "schema"}
    apply_bundle(schema_bundle, allow_destructive=False)
    return CustomObjectType.objects.get(slug=DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG)
