"""Setup: nsm_config status in COT comments."""

from django.contrib import messages
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.objects.nsm_config import (
    has_nsm_config_in_comments,
    sync_cot_nsm_config_comments,
)
from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG, TYPECONFIG_UI_SPECS

from .custom_objects import custom_objects_db_ready

__all__ = (
    "get_typeconfig_status",
    "all_typeconfigs_ok",
    "create_all_typeconfigs",
    "create_typeconfig_for_slug",
    "handle_typeconfig_action",
)


def empty_typeconfig_status():
    return [
        {"spec": spec, "cot": None, "typeconfig": None}
        for spec in TYPECONFIG_UI_SPECS
    ]


def get_typeconfig_status():
    if not custom_objects_db_ready():
        return empty_typeconfig_status()

    result = []
    try:
        from netbox_custom_objects.models import CustomObjectType

        from netbox_nsm.objects.nsm_config import resolve_nsm_config_for_cot

        for spec in TYPECONFIG_UI_SPECS:
            cot = config = None
            try:
                cot = CustomObjectType.objects.get(slug=spec["slug"])
                if has_nsm_config_in_comments(cot.comments or ""):
                    config = resolve_nsm_config_for_cot(cot)
            except Exception:
                pass
            result.append({"spec": spec, "cot": cot, "typeconfig": config})
    except (ProgrammingError, OperationalError):
        return empty_typeconfig_status()
    return result


def all_typeconfigs_ok(cot_status, tc_status) -> bool:
    if not all(v is not None for v in cot_status.values()):
        return False
    return all(e["typeconfig"] is not None for e in tc_status)


def create_typeconfig_for_slug(slug: str) -> None:
    from netbox_custom_objects.models import CustomObjectType

    spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
    if not spec:
        raise ValueError(f"No TypeConfig spec for slug {slug!r}")

    cot = CustomObjectType.objects.get(slug=slug)
    sync_cot_nsm_config_comments(cot, spec=spec)


def create_all_typeconfigs() -> None:
    """Write bundled nsm_config YAML to all UI Custom Object Types."""
    from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
    from netbox_nsm.views.custom_objects_sync import _sync_type_configs_and_sections

    _sync_type_configs_and_sections(BUILTIN_CUSTOM_TYPES)


def handles_action(action: str) -> bool:
    return action.startswith("create_typeconfig_") or action == "create_all_typeconfigs"


def handle_typeconfig_action(request, action: str):
    if action.startswith("create_typeconfig_"):
        slug = action[len("create_typeconfig_") :]
        create_typeconfig_for_slug(slug)
        messages.success(
            request, _("Object Config for '%(slug)s' created.") % {"slug": slug}
        )
    elif action == "create_all_typeconfigs":
        create_all_typeconfigs()
        messages.success(
            request,
            _("All Object Configs created/updated (including NSM section links)."),
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
