"""Setup: netbox-custom-objects plugin status and type import."""

from django.contrib import messages
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.objects.custom_objects_schema import (
    build_choice_set_specs,
    build_portable_schema_preview_types,
    build_schema_document,
    export_portable_schema_yaml,
    iter_types,
    prepare_document_for_apply,
    validate_custom_objects_schema_yaml,
)
from netbox_nsm.objects.nsm_config import format_nsm_config_comment_yaml
from netbox_nsm.objects.type_config_specs import REQUIRED_COT_SLUGS
from netbox_nsm.rulebooks.templates import (
    BUNDLED_RULEBOOK_TEMPLATE_SLUGS,
    RULEBOOK_TEMPLATE_GROUP,
    build_rulebook_template_type_defs,
)

NSM_PANEL_COT_SLUGS = ("nsm_object_link",)

COT_BUILTIN_OBJECT_SLUGS = tuple(
    slug for slug in REQUIRED_COT_SLUGS if slug not in NSM_PANEL_COT_SLUGS
)

COT_GROUP_OBJECTS = {
    "id": "objects",
    "label": _("NSM Objects"),
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

__all__ = (
    "COT_GROUP_OBJECTS",
    "COT_GROUP_NSM_PANEL",
    "COT_SETUP_GROUPS",
    "COT_BUILTIN_OBJECT_SLUGS",
    "NSM_PANEL_COT_SLUGS",
    "custom_objects_plugin_loaded",
    "custom_objects_db_ready",
    "get_cot_status",
    "get_rulebook_template_status",
    "get_builtin_object_entries",
    "get_nsm_panel_entries",
    "get_rulebook_template_entries",
    "get_cot_setup_groups",
    "get_cot_schema_yaml",
    "get_cot_schema_preview",
    "all_cots_ok",
    "import_rulebook_templates",
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


def _empty_cot_status():
    return empty_cot_status()


def get_cot_status():
    if not custom_objects_db_ready():
        return _empty_cot_status()
    try:
        from netbox_custom_objects.models import CustomObjectType

        existing = {
            cot.slug: cot
            for cot in CustomObjectType.objects.filter(slug__in=REQUIRED_COT_SLUGS)
        }
        return {slug: existing.get(slug) for slug in REQUIRED_COT_SLUGS}
    except (ProgrammingError, OperationalError):
        return _empty_cot_status()


def empty_rulebook_template_status():
    return {slug: None for slug in BUNDLED_RULEBOOK_TEMPLATE_SLUGS}


def get_rulebook_template_status():
    if not custom_objects_db_ready():
        return empty_rulebook_template_status()
    try:
        from netbox_custom_objects.models import CustomObjectType

        status = {slug: None for slug in BUNDLED_RULEBOOK_TEMPLATE_SLUGS}
        for cot in CustomObjectType.objects.filter(
            slug__in=BUNDLED_RULEBOOK_TEMPLATE_SLUGS
        ):
            status[cot.slug] = cot
        for cot in (
            CustomObjectType.objects.filter(group_name=RULEBOOK_TEMPLATE_GROUP)
            .exclude(slug__in=BUNDLED_RULEBOOK_TEMPLATE_SLUGS)
            .order_by("slug")
        ):
            status[cot.slug] = cot
        return status
    except (ProgrammingError, OperationalError):
        return empty_rulebook_template_status()


def _builtin_metadata_by_slug():
    return {
        prefixed: typedef
        for typedef, _base, prefixed, _areas in iter_types(BUILTIN_CUSTOM_TYPES)
    }


def get_builtin_object_entries(*, cot_status=None):
    if cot_status is None:
        cot_status = get_cot_status()
    metadata = _builtin_metadata_by_slug()
    return [
        {
            "slug": slug,
            "label": metadata.get(slug, {}).get("name", slug),
            "description": metadata.get(slug, {}).get("description", ""),
            "cot": cot_status.get(slug),
        }
        for slug in COT_BUILTIN_OBJECT_SLUGS
    ]


def get_nsm_panel_entries(*, cot_status=None):
    if cot_status is None:
        cot_status = get_cot_status()
    metadata = _builtin_metadata_by_slug()
    return [
        {
            "slug": slug,
            "label": metadata.get(slug, {}).get("name", slug),
            "description": metadata.get(slug, {}).get("description", ""),
            "cot": cot_status.get(slug),
        }
        for slug in NSM_PANEL_COT_SLUGS
    ]


def get_rulebook_template_entries(*, template_status=None):
    if template_status is None:
        template_status = get_rulebook_template_status()
    entries = []
    for slug in sorted(template_status):
        cot = template_status[slug]
        entries.append(
            {
                "slug": slug,
                "label": (cot.verbose_name or cot.name or slug) if cot else slug,
                "description": (cot.description or "").strip() if cot else "",
                "cot": cot,
            }
        )
    return entries


def get_cot_schema_yaml() -> str:
    return export_portable_schema_yaml(include_rulebook_templates=False)


def get_cot_schema_preview() -> list[dict]:
    return build_portable_schema_preview_types(include_rulebook_templates=False)


def get_cot_setup_groups(*, cot_status=None, rulebook_template_status=None):
    if cot_status is None:
        cot_status = get_cot_status()
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
    return all(v is not None for v in cot_status.values())


def import_rulebook_templates() -> None:
    from netbox_custom_objects.models import CustomObjectType
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.rulebooks.rulebook_groups import sync_all_rulebook_cots

    existing_slugs = set(
        CustomObjectType.objects.filter(
            slug__in=BUNDLED_RULEBOOK_TEMPLATE_SLUGS
        ).values_list("slug", flat=True)
    )
    missing_types = [
        type_def
        for type_def in build_rulebook_template_type_defs()
        if type_def.get("slug") not in existing_slugs
    ]
    if missing_types:
        apply_document(
            {"schema_version": "1", "types": missing_types},
            allow_destructive=False,
        )
    sync_all_rulebook_cots()


def import_single_type(slug: str) -> None:
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.objects.type_config_export import sync_cot_nsm_config_comments_for_slugs
    from netbox_nsm.views.custom_objects_sync import (
        _ensure_choice_sets,
        _seed_default_objects,
    )

    matching_types = [
        typedef
        for typedef, _base, prefixed, _areas in iter_types(BUILTIN_CUSTOM_TYPES)
        if prefixed == slug
    ]
    if not matching_types:
        raise ValueError(f"No builtin type found for slug {slug!r}")

    choice_specs = build_choice_set_specs(matching_types)
    document = build_schema_document(matching_types)
    with transaction.atomic():
        _ensure_choice_sets(choice_specs)
        apply_document(document, allow_destructive=False)
        _seed_default_objects(matching_types)
        sync_cot_nsm_config_comments_for_slugs([slug])


def _apply_nsm_configs_by_slug(configs_by_slug: dict[str, dict]) -> None:
    from netbox_custom_objects.models import CustomObjectType

    for slug, config in configs_by_slug.items():
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if not cot:
            continue
        cot.comments = format_nsm_config_comment_yaml(config).rstrip()
        cot.save(update_fields=["comments"])


def import_all_types(*, schema_yaml: str | None = None) -> None:
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.objects.type_config_export import sync_cot_nsm_config_comments_for_slugs
    from netbox_nsm.views.custom_objects_sync import (
        _ensure_choice_sets,
        _prune_stale,
        _seed_default_objects,
    )

    configs_by_slug: dict[str, dict] = {}
    if schema_yaml:
        apply_document_data, configs_by_slug = prepare_document_for_apply(schema_yaml)
        choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
    else:
        choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
        apply_document_data = build_schema_document(BUILTIN_CUSTOM_TYPES)

    with transaction.atomic():
        _ensure_choice_sets(choice_specs)
        apply_document(apply_document_data, allow_destructive=True)
        _prune_stale(apply_document_data)
        _seed_default_objects(BUILTIN_CUSTOM_TYPES)
        if configs_by_slug:
            _apply_nsm_configs_by_slug(configs_by_slug)
        else:
            sync_cot_nsm_config_comments_for_slugs(
                t["slug"] for t in apply_document_data["types"]
            )
    import_rulebook_templates()


def handles_action(action: str) -> bool:
    return (
        action.startswith("import_type_")
        or action == "import_all_types"
        or action == "import_all_custom_objects"
    )


def handle_custom_objects_action(request, action: str):
    if action.startswith("import_type_"):
        slug = action[len("import_type_") :]
        import_single_type(slug)
        messages.success(
            request,
            _("Custom Object Type '%(slug)s' imported.") % {"slug": slug},
        )
    elif action in ("import_all_types", "import_all_custom_objects"):
        schema_yaml = request.POST.get("schema_yaml", "").strip()
        if schema_yaml:
            try:
                validate_custom_objects_schema_yaml(schema_yaml)
            except Exception as exc:
                messages.error(
                    request,
                    _("Schema YAML invalid: %(error)s") % {"error": exc},
                )
                return redirect(reverse("plugins:netbox_nsm:setup"))
        import_all_types(schema_yaml=schema_yaml or None)
        messages.success(
            request,
            _("All Custom Object Types imported with Object Config (nsm_config)."),
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
