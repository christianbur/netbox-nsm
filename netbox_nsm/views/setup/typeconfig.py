"""Setup: NSM TypeConfig status and creation."""

from django.contrib import messages
from django.db.utils import OperationalError, ProgrammingError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import TypeConfig
from netbox_nsm.type_config_specs import TYPECONFIG_SPEC_BY_SLUG, TYPECONFIG_SPECS

from .custom_objects import custom_objects_db_ready

__all__ = (
    "get_typeconfig_status",
    "all_typeconfigs_ok",
    "handle_typeconfig_action",
)


def empty_typeconfig_status():
    return [
        {"spec": spec, "cot": None, "typeconfig": None} for spec in TYPECONFIG_SPECS
    ]


def get_typeconfig_status():
    from django.contrib.contenttypes.models import ContentType as DjCT

    if not custom_objects_db_ready():
        return [
            {"spec": spec, "cot": None, "typeconfig": None} for spec in TYPECONFIG_SPECS
        ]

    result = []
    try:
        from netbox_custom_objects.models import CustomObjectType

        for spec in TYPECONFIG_SPECS:
            cot = tc = None
            try:
                cot = CustomObjectType.objects.get(slug=spec["slug"])
                ct = DjCT.objects.get_for_model(cot.get_model())
                tc = TypeConfig.objects.filter(
                    content_type=ct,
                    matching_class=spec["matching_class"],
                ).first()
            except Exception:
                pass
            result.append({"spec": spec, "cot": cot, "typeconfig": tc})
    except (ProgrammingError, OperationalError):
        return [
            {"spec": spec, "cot": None, "typeconfig": None} for spec in TYPECONFIG_SPECS
        ]
    return result


def all_typeconfigs_ok(cot_status, tc_status) -> bool:
    if not all(v is not None for v in cot_status.values()):
        return False
    return all(e["typeconfig"] is not None for e in tc_status)


def create_typeconfig_for_slug(slug: str) -> None:
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    spec = TYPECONFIG_SPEC_BY_SLUG.get(slug)
    if not spec:
        raise ValueError(f"No TypeConfig spec for slug {slug!r}")

    cot = CustomObjectType.objects.get(slug=slug)
    ct = DjCT.objects.get_for_model(cot.get_model())
    TypeConfig.objects.update_or_create(
        content_type=ct,
        matching_class=spec["matching_class"],
        defaults={
            "name": spec["label"],
            "display_template": spec["display_template"],
            "panel_slugs": spec["panel_slugs"],
            "order_id": spec.get("order_id", 100),
            "panel_linkable_types": spec.get("panel_linkable_types", []),
        },
    )


def create_all_typeconfigs() -> None:
    """Create/update TypeConfigs and link NSM sections (same as TypeConfig sync)."""
    from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
    from netbox_nsm.views.custom_objects_sync import _sync_type_configs_and_sections

    _sync_type_configs_and_sections(BUILTIN_CUSTOM_TYPES)


def handles_action(action: str) -> bool:
    return action.startswith("create_typeconfig_") or action == "create_all_typeconfigs"


def handle_typeconfig_action(request, action: str):
    if action.startswith("create_typeconfig_"):
        slug = action[len("create_typeconfig_") :]
        create_typeconfig_for_slug(slug)
        messages.success(
            request, _("TypeConfig for '%(slug)s' created.") % {"slug": slug}
        )
    elif action == "create_all_typeconfigs":
        create_all_typeconfigs()
        messages.success(
            request,
            _("All TypeConfigs created/updated (including NSM section links)."),
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
