"""Setup: netbox-custom-objects plugin status and type import."""

from django.contrib import messages
from django.db import transaction
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.custom_objects_schema import (
    build_choice_set_specs,
    build_schema_document,
    iter_types,
)
from netbox_nsm.type_config_specs import REQUIRED_COT_SLUGS

__all__ = (
    "custom_objects_plugin_loaded",
    "custom_objects_db_ready",
    "get_cot_status",
    "all_cots_ok",
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


def all_cots_ok(cot_status) -> bool:
    return custom_objects_db_ready() and all(v is not None for v in cot_status.values())


def import_single_type(slug: str) -> None:
    from netbox_custom_objects.schema.executor import apply_document
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


def import_all_types() -> None:
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.views.custom_objects_sync import (
        _ensure_choice_sets,
        _prune_stale,
        _seed_default_objects,
    )

    choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
    document = build_schema_document(BUILTIN_CUSTOM_TYPES)
    with transaction.atomic():
        _ensure_choice_sets(choice_specs)
        apply_document(document, allow_destructive=True)
        _prune_stale(document)
        _seed_default_objects(BUILTIN_CUSTOM_TYPES)


def handles_action(action: str) -> bool:
    return action.startswith("import_type_") or action == "import_all_types"


def handle_custom_objects_action(request, action: str):
    if action.startswith("import_type_"):
        slug = action[len("import_type_") :]
        import_single_type(slug)
        messages.success(
            request,
            _("Custom Object Type '%(slug)s' imported (TypeConfigs: use step 2).")
            % {"slug": slug},
        )
    elif action == "import_all_types":
        import_all_types()
        messages.success(
            request,
            _("All Custom Object Types imported. Create TypeConfigs in step 2."),
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
