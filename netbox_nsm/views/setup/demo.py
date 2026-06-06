"""Setup: demo rulebook creation."""

import io
import sys
from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ipam.models import IPAddress

from netbox_nsm.models import TypeConfig
from netbox_nsm.models.rulebook import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldType,
    RuleObjectItem,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields

__all__ = (
    "DEMO_ACTIONS",
    "handles_action",
    "handle_demo_action",
)

_DEMO_MATRIX_RULES = [
    {
        "name": "trust-to-untrust",
        "src": "trust",
        "dst": "untrust",
        "svc": "HTTPS",
        "action": "permit",
    },
    {
        "name": "trust-to-dmz",
        "src": "trust",
        "dst": "dmz",
        "svc": "HTTPS",
        "action": "permit",
    },
    {
        "name": "trust-to-mgmt",
        "src": "trust",
        "dst": "mgmt",
        "svc": "SSH",
        "action": "permit",
    },
    {
        "name": "untrust-to-dmz",
        "src": "untrust",
        "dst": "dmz",
        "svc": "HTTPS",
        "action": "permit",
    },
    {
        "name": "untrust-to-mgmt",
        "src": "untrust",
        "dst": "mgmt",
        "svc": "SSH",
        "action": "deny",
    },
    {
        "name": "dmz-to-mgmt",
        "src": "dmz",
        "dst": "mgmt",
        "svc": "SSH",
        "action": "deny",
    },
]

DEMO_ACTIONS = frozenset({"create_demo_starter", "create_demo_enterprise"})

# Object columns shared by starter demos (system columns come from ensure_system_rulebook_fields).
_POLICY_OBJECT_FIELD_SPECS = (
    {"slug": "source", "name": "Source", "sort_order": 10, "placement": "source"},
    {
        "slug": "destination",
        "name": "Destination",
        "sort_order": 20,
        "placement": "destination",
    },
    {"slug": "service", "name": "Service", "sort_order": 30, "placement": "fixed"},
    {"slug": "action", "name": "Action", "sort_order": 40, "placement": "fixed"},
)

# (field_slug, [(cot_slug, type_sort_order), ...])
_ZONE_MATRIX_FIELD_TYPES = {
    "source": (("nsm_zones", 10),),
    "destination": (("nsm_zones", 10),),
    "service": (("nsm_services", 10),),
    "action": (("nsm_action", 10),),
}

_ADDRESSES_FIELD_TYPES = {
    "source": (("nsm_zones", 10), ("nsm_addresses", 20)),
    "destination": (("nsm_zones", 10), ("nsm_addresses", 20)),
    "service": (("nsm_services", 10), ("nsm_network_apps", 20)),
    "action": (("nsm_action", 10),),
}


def _upsert_object_fields(rb, specs):
    fields = {}
    for spec in specs:
        field, _ = RulebookField.objects.update_or_create(
            rulebook=rb,
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "sort_order": spec["sort_order"],
                "placement": spec["placement"],
                "visible": True,
                "max_visible_pills": 5,
            },
        )
        fields[spec["slug"]] = field
    return fields


def _attach_typeconfig(field, cot_slug, *, sort_order=10, visible=True):
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    try:
        cot = CustomObjectType.objects.get(slug=cot_slug)
        ct = DjCT.objects.get_for_model(cot.get_model())
        tc = TypeConfig.objects.get(content_type=ct)
    except Exception:
        return None

    ft, created = RulebookFieldType.objects.get_or_create(
        field=field,
        type_config=tc,
        defaults={"sort_order": sort_order, "visible": visible},
    )
    if not created and (ft.sort_order != sort_order or ft.visible != visible):
        ft.sort_order = sort_order
        ft.visible = visible
        ft.save(update_fields=["sort_order", "visible"])
    return tc


def _apply_field_types(fields, type_map):
    for field_slug, type_specs in type_map.items():
        field = fields.get(field_slug)
        if field is None:
            continue
        for cot_slug, sort_order in type_specs:
            _attach_typeconfig(field, cot_slug, sort_order=sort_order, visible=True)


def _ensure_demo_prerequisites():
    """Import built-in Custom Object Types + TypeConfigs if not yet present."""
    from netbox_custom_objects.models import CustomObjectType

    from .custom_objects import custom_objects_db_ready, import_all_types
    from .typeconfig import create_all_typeconfigs

    if not custom_objects_db_ready():
        raise RuntimeError(
            "netbox-custom-objects database tables are missing "
            "(migrate netbox_custom_objects first)."
        )

    if not CustomObjectType.objects.filter(slug="nsm_zones").exists():
        import_all_types()
        create_all_typeconfigs()


def _create_zone_matrix_rulebook():
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    rb, _ = Rulebook.objects.get_or_create(
        name="Demo - Zone Matrix",
        defaults={"rulebook_type": "policy"},
    )
    ensure_system_rulebook_fields(rb)
    fields = _upsert_object_fields(rb, _POLICY_OBJECT_FIELD_SPECS)
    _apply_field_types(fields, _ZONE_MATRIX_FIELD_TYPES)

    def _get_objects_by_name(slug):
        try:
            cot = CustomObjectType.objects.get(slug=slug)
            model = cot.get_model()
            return {
                obj.name.lower(): (obj, DjCT.objects.get_for_model(model))
                for obj in model.objects.all()
            }
        except Exception:
            return {}

    zones_by_name = _get_objects_by_name("nsm_zones")
    services_by_name = _get_objects_by_name("nsm_services")
    actions_by_name = _get_objects_by_name("nsm_action")

    for i, rule_def in enumerate(_DEMO_MATRIX_RULES):
        rule, _ = Rule.objects.get_or_create(
            rulebook=rb,
            name=rule_def["name"],
            defaults={"index": (i + 1) * 10, "enabled": True},
        )

        def _add_object(field_obj, lookup_dict, key):
            entry = lookup_dict.get(key.lower())
            if not entry:
                return
            obj, ct = entry
            RuleObjectItem.objects.get_or_create(
                rule=rule,
                field=field_obj,
                content_type=ct,
                object_id=obj.pk,
                defaults={"exclude": False},
            )

        _add_object(fields["source"], zones_by_name, rule_def["src"])
        _add_object(fields["destination"], zones_by_name, rule_def["dst"])
        _add_object(fields["service"], services_by_name, rule_def["svc"])
        _add_object(fields["action"], actions_by_name, rule_def["action"])
    return rb


def _create_addresses_rulebook():
    rb, _ = Rulebook.objects.get_or_create(
        name="Demo - Addresses",
        defaults={"rulebook_type": "policy"},
    )
    ensure_system_rulebook_fields(rb)
    fields = _upsert_object_fields(rb, _POLICY_OBJECT_FIELD_SPECS)
    _apply_field_types(fields, _ADDRESSES_FIELD_TYPES)
    return rb


def create_demo_starter():
    """Built-in COTs/TypeConfigs (if needed), Zone Matrix + Addresses rulebooks."""
    _ensure_demo_prerequisites()
    with transaction.atomic():
        matrix_rb = _create_zone_matrix_rulebook()
        addresses_rb = _create_addresses_rulebook()
    return matrix_rb, addresses_rb


def run_enterprise_demo(request):
    script_path = (
        Path(__file__).resolve().parent.parent.parent
        / "demos"
        / "enterprise_dc"
        / "import.py"
    )
    if not script_path.exists():
        raise FileNotFoundError(f"Import script not found: {script_path}")

    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        with open(script_path) as fh:
            code = compile(fh.read(), str(script_path), "exec")
        exec(code, {"__name__": "__main__"})  # noqa: S102
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    summary_lines = [
        ln
        for ln in output.splitlines()
        if ln.startswith("  ") or "===" in ln or "complete" in ln.lower()
    ]
    summary = " | ".join(summary_lines[-8:]) if summary_lines else _("Import finished.")
    messages.success(
        request,
        _("Enterprise Demo imported successfully. %(summary)s") % {"summary": summary},
    )


def handles_action(action: str) -> bool:
    return action in DEMO_ACTIONS


def handle_demo_action(request, action: str):
    if action == "create_demo_starter":
        matrix_rb, addresses_rb = create_demo_starter()
        messages.success(
            request,
            _(
                "Starter demos created: '%(matrix)s' (with rules when zone objects exist) "
                "and '%(addresses)s' (zones + addresses, no rules). "
                "Custom Object Types / TypeConfigs were imported if missing."
            )
            % {"matrix": matrix_rb.name, "addresses": addresses_rb.name},
        )
    elif action == "create_demo_enterprise":
        if IPAddress.objects.exists():
            messages.error(
                request,
                _(
                    "Enterprise Demo cannot be imported: IP addresses already exist in the database."
                ),
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))
        run_enterprise_demo(request)
    return redirect(reverse("plugins:netbox_nsm:setup"))
