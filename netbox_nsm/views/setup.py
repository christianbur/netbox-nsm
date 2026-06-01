"""Setup wizard for netbox-nsm.

Accessible from: Plugins > Security > Configuration > Setup

Checks whether the netbox-custom-objects plugin is installed, verifies that
the required NSM CustomObjectTypes and TypeConfigs exist, and provides one-click
import/creation for any that are missing.  Also offers demo Rulebook creation.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from ipam.models import IPAddress

from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
from netbox_nsm.custom_objects_schema import (
    build_choice_set_specs,
    build_schema_document,
    iter_types,
    slugify_identifier,
)
from netbox_nsm.models import TypeConfig
from netbox_nsm.models.security_policy import (
    RulebookField,
    RulebookFieldType,
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyRuleObjectItem,
)

__all__ = ("SetupView",)

# ─── Required Custom Object Types ─────────────────────────────────────────────

REQUIRED_COT_SLUGS = [
    "nsm_zones",
    "nsm_addresses",
    "nsm_labels",
    "nsm_services",
    "nsm_action",
]

# ─── Desired TypeConfig specs ─────────────────────────────────────────────────

TYPECONFIG_SPECS = [
    {
        "slug": "nsm_zones",
        "label": "Zones",
        "matching_class": "zone",
        "display_template": "{name}",
        "allowed_placements": ["source", "destination"],
    },
    {
        "slug": "nsm_addresses",
        "label": "Addresses",
        "matching_class": "address",
        "display_template": "{name}",
        "allowed_placements": ["source", "destination"],
    },
    {
        "slug": "nsm_labels",
        "label": "Labels",
        "matching_class": "label",
        "display_template": "{label_type[0]!u}:{name}",
        "allowed_placements": ["source", "destination"],
    },
    {
        "slug": "nsm_services",
        "label": "Services",
        "matching_class": "service",
        "display_template": "{name} ({protocol}/{port})",
        "allowed_placements": ["fixed"],
    },
    {
        "slug": "nsm_action",
        "label": "Action",
        "matching_class": "action",
        "display_template": "{name!u}",
        "allowed_placements": ["fixed"],
    },
]

# ─── Demo rulebook definitions ────────────────────────────────────────────────

_DEMO_MATRIX_RULES = [
    # 6 unique zone pairs (one rule per unordered pair)
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


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _check_custom_objects_installed():
    try:
        import netbox_custom_objects  # noqa: F401

        return True
    except ImportError:
        return False


def _get_cot_status():
    """Return ``{slug: cot_or_None}`` for all required slugs."""
    try:
        from netbox_custom_objects.models import CustomObjectType

        existing = {
            cot.slug: cot
            for cot in CustomObjectType.objects.filter(slug__in=REQUIRED_COT_SLUGS)
        }
        return {slug: existing.get(slug) for slug in REQUIRED_COT_SLUGS}
    except Exception:
        return {slug: None for slug in REQUIRED_COT_SLUGS}


def _get_typeconfig_status():
    """Return list of ``{"spec", "cot", "typeconfig"}`` dicts."""
    from django.contrib.contenttypes.models import ContentType as DjCT

    result = []
    try:
        from netbox_custom_objects.models import CustomObjectType

        for spec in TYPECONFIG_SPECS:
            cot = tc = None
            try:
                cot = CustomObjectType.objects.get(slug=spec["slug"])
                ct = DjCT.objects.get_for_model(cot.get_model())
                tc = TypeConfig.objects.filter(content_type=ct).first()
            except Exception:
                pass
            result.append({"spec": spec, "cot": cot, "typeconfig": tc})
    except Exception:
        for spec in TYPECONFIG_SPECS:
            result.append({"spec": spec, "cot": None, "typeconfig": None})
    return result


def _import_single_type(slug):
    """Import a single builtin NSM type into netbox-custom-objects."""
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.views.custom_objects_sync import (
        _ensure_choice_sets,
        _seed_default_objects,
        _sync_type_configs_and_sections,
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
        _sync_type_configs_and_sections(matching_types)


def _import_all_types():
    """Full sync of all BUILTIN_CUSTOM_TYPES."""
    from netbox_custom_objects.schema.executor import apply_document
    from netbox_nsm.views.custom_objects_sync import (
        _ensure_choice_sets,
        _prune_stale,
        _seed_default_objects,
        _sync_type_configs_and_sections,
    )

    choice_specs = build_choice_set_specs(BUILTIN_CUSTOM_TYPES)
    document = build_schema_document(BUILTIN_CUSTOM_TYPES)
    with transaction.atomic():
        _ensure_choice_sets(choice_specs)
        apply_document(document, allow_destructive=True)
        _prune_stale(document)
        _seed_default_objects(BUILTIN_CUSTOM_TYPES)
        _sync_type_configs_and_sections(BUILTIN_CUSTOM_TYPES)


def _create_typeconfig_for_slug(slug):
    """Create/update a TypeConfig for the given COT slug."""
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    spec = next((s for s in TYPECONFIG_SPECS if s["slug"] == slug), None)
    if not spec:
        raise ValueError(f"No TypeConfig spec for slug {slug!r}")

    cot = CustomObjectType.objects.get(slug=slug)
    ct = DjCT.objects.get_for_model(cot.get_model())
    TypeConfig.objects.update_or_create(
        content_type=ct,
        defaults={
            "matching_class": spec["matching_class"],
            "display_template": spec["display_template"],
            "allowed_placements": spec["allowed_placements"],
        },
    )


def _create_all_typeconfigs():
    """Create/update TypeConfigs for all TYPECONFIG_SPECS."""
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    for spec in TYPECONFIG_SPECS:
        try:
            cot = CustomObjectType.objects.get(slug=spec["slug"])
            ct = DjCT.objects.get_for_model(cot.get_model())
            TypeConfig.objects.update_or_create(
                content_type=ct,
                defaults={
                    "matching_class": spec["matching_class"],
                    "display_template": spec["display_template"],
                    "allowed_placements": spec["allowed_placements"],
                },
            )
        except Exception:
            pass


def _get_or_create_fields(rb, specs):
    """Create/get RulebookFields for a rulebook from a list of dicts."""
    fields = {}
    for s in specs:
        f, _ = RulebookField.objects.get_or_create(
            rulebook=rb,
            slug=s["slug"],
            defaults={
                "name": s["name"],
                "sort_order": s["sort_order"],
                "placement": s["placement"],
            },
        )
        fields[s["slug"]] = f
    return fields


def _attach_typeconfig(field, cot_slug):
    """Link a TypeConfig (by COT slug) to a RulebookField if the TC exists."""
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    try:
        cot = CustomObjectType.objects.get(slug=cot_slug)
        ct = DjCT.objects.get_for_model(cot.get_model())
        tc = TypeConfig.objects.get(content_type=ct)
        RulebookFieldType.objects.get_or_create(
            field=field, type_config=tc, defaults={"sort_order": 10}
        )
        return tc
    except Exception:
        return None


def _create_demo_matrix():
    """Create 'Demo - Zone Matrix' rulebook with 12 rules (full 4-zone matrix)."""
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    with transaction.atomic():
        rb, _ = SecurityPolicyRulebook.objects.get_or_create(
            name="Demo - Zone Matrix",
            defaults={"rulebook_type": "policy"},
        )

        field_specs = [
            {
                "slug": "source",
                "name": "Source",
                "sort_order": 10,
                "placement": "source",
            },
            {
                "slug": "destination",
                "name": "Destination",
                "sort_order": 20,
                "placement": "destination",
            },
            {
                "slug": "service",
                "name": "Service",
                "sort_order": 30,
                "placement": "fixed",
            },
            {
                "slug": "action",
                "name": "Action",
                "sort_order": 40,
                "placement": "fixed",
            },
        ]
        fields = _get_or_create_fields(rb, field_specs)

        _attach_typeconfig(fields["source"], "nsm_zones")
        _attach_typeconfig(fields["destination"], "nsm_zones")
        _attach_typeconfig(fields["service"], "nsm_services")
        _attach_typeconfig(fields["action"], "nsm_action")

        # Try to attach objects to rules if available
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
            rule, _ = SecurityPolicyRule.objects.get_or_create(
                rulebook=rb,
                name=rule_def["name"],
                defaults={"index": (i + 1) * 10, "enabled": True},
            )

            def _add_object(field_obj, lookup_dict, key):
                entry = lookup_dict.get(key.lower())
                if not entry:
                    return
                obj, ct = entry
                SecurityPolicyRuleObjectItem.objects.get_or_create(
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


def _create_demo_addresses():
    """Create 'Demo - Addresses' rulebook without rules."""
    with transaction.atomic():
        rb, _ = SecurityPolicyRulebook.objects.get_or_create(
            name="Demo - Addresses",
            defaults={"rulebook_type": "policy"},
        )

        field_specs = [
            {
                "slug": "source",
                "name": "Source",
                "sort_order": 10,
                "placement": "source",
            },
            {
                "slug": "destination",
                "name": "Destination",
                "sort_order": 20,
                "placement": "destination",
            },
            {
                "slug": "service",
                "name": "Service",
                "sort_order": 30,
                "placement": "fixed",
            },
            {
                "slug": "action",
                "name": "Action",
                "sort_order": 40,
                "placement": "fixed",
            },
        ]
        fields = _get_or_create_fields(rb, field_specs)

        _attach_typeconfig(fields["source"], "nsm_zones")
        _attach_typeconfig(fields["source"], "nsm_addresses")
        _attach_typeconfig(fields["destination"], "nsm_zones")
        _attach_typeconfig(fields["destination"], "nsm_addresses")
        _attach_typeconfig(fields["service"], "nsm_services")
        _attach_typeconfig(fields["action"], "nsm_action")

    return rb


def _run_enterprise_demo(request):
    """Execute the enterprise_dc import script in the current Django shell context."""
    import io
    import sys
    from pathlib import Path

    script_path = (
        Path(__file__).resolve().parent.parent / "demos" / "enterprise_dc" / "import.py"
    )
    if not script_path.exists():
        raise FileNotFoundError(f"Import script not found: {script_path}")

    # Capture stdout so we can surface a summary message
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        with open(script_path) as fh:
            code = compile(fh.read(), str(script_path), "exec")
        exec(
            code, {"__name__": "__main__"}
        )  # noqa: S102  (controlled path, plugin context)
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue()
    # Extract the last section (summary) for the success message
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


# ─── View ─────────────────────────────────────────────────────────────────────


class SetupView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/setup.html"

    def get(self, request):
        plugin_installed = _check_custom_objects_installed()
        cot_status = _get_cot_status() if plugin_installed else None
        tc_status = _get_typeconfig_status() if plugin_installed else None
        all_cots_ok = plugin_installed and all(
            v is not None for v in (cot_status or {}).values()
        )
        all_tcs_ok = all_cots_ok and all(
            e["typeconfig"] is not None for e in (tc_status or [])
        )

        enterprise_demo_blocked = IPAddress.objects.exists()

        return render(
            request,
            self.template_name,
            {
                "plugin_installed": plugin_installed,
                "cot_status": cot_status,
                "tc_status": tc_status,
                "all_cots_ok": all_cots_ok,
                "all_tcs_ok": all_tcs_ok,
                "enterprise_demo_blocked": enterprise_demo_blocked,
            },
        )

    def post(self, request):
        action = request.POST.get("action", "")

        try:
            if action.startswith("import_type_"):
                slug = action[len("import_type_") :]
                _import_single_type(slug)
                messages.success(
                    request,
                    _("Type '%(slug)s' imported successfully.") % {"slug": slug},
                )

            elif action == "import_all_types":
                _import_all_types()
                messages.success(request, _("All NSM types synchronised successfully."))

            elif action.startswith("create_typeconfig_"):
                slug = action[len("create_typeconfig_") :]
                _create_typeconfig_for_slug(slug)
                messages.success(
                    request, _("TypeConfig for '%(slug)s' created.") % {"slug": slug}
                )

            elif action == "create_all_typeconfigs":
                _create_all_typeconfigs()
                messages.success(request, _("All TypeConfigs created/updated."))

            elif action == "create_demo_matrix":
                rb = _create_demo_matrix()
                messages.success(
                    request,
                    _("Demo rulebook '%(name)s' created.") % {"name": rb.name},
                )

            elif action == "create_demo_addresses":
                rb = _create_demo_addresses()
                messages.success(
                    request,
                    _("Demo rulebook '%(name)s' created.") % {"name": rb.name},
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
                _run_enterprise_demo(request)

        except Exception as exc:
            messages.error(request, _("Error: %(error)s") % {"error": exc})

        return redirect(reverse("plugins:netbox_nsm:setup"))
