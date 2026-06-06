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
    "_count_active_rq_workers",
    "_find_pending_demo_job",
    "_queue_demo_import",
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

DEMO_ACTIONS = frozenset(
    {
        "create_demo_starter",
        "create_demo_enterprise",
        "create_demo_addresses_scale",
    }
)

# Object columns shared by starter demos (system columns come from ensure_system_rulebook_fields).
_SECURITY_RULES_OBJECT_FIELD_SPECS = (
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
    from .custom_objects import (
        all_cots_ok,
        custom_objects_db_ready,
        get_cot_status,
        import_all_types,
    )
    from .typeconfig import (
        all_typeconfigs_ok,
        create_all_typeconfigs,
        get_typeconfig_status,
    )

    if not custom_objects_db_ready():
        raise RuntimeError(
            "netbox-custom-objects database tables are missing "
            "(migrate netbox_custom_objects first)."
        )

    cot_status = get_cot_status()
    if not all_cots_ok(cot_status):
        import_all_types()
    else:
        _ensure_builtin_default_objects()

    tc_status = get_typeconfig_status()
    if not all_typeconfigs_ok(cot_status, tc_status):
        create_all_typeconfigs()


def _ensure_builtin_default_objects() -> None:
    """Seed Permit/HTTPS/etc. when COTs exist but default rows were never created."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.builtin_types import BUILTIN_CUSTOM_TYPES
    from netbox_nsm.views.custom_objects_sync import _seed_default_objects

    needs_seed = False
    for slug in ("nsm_action", "nsm_services", "nsm_zones"):
        try:
            cot = CustomObjectType.objects.get(slug=slug)
        except CustomObjectType.DoesNotExist:
            needs_seed = True
            break
        if not cot.get_model().objects.exists():
            needs_seed = True
            break
    if needs_seed:
        _seed_default_objects(BUILTIN_CUSTOM_TYPES)


def _count_active_rq_workers() -> int:
    import django_rq
    from rq.worker import Worker

    conn = django_rq.get_connection()
    return len(Worker.all(connection=conn))


def _find_pending_demo_job(import_path: str):
    """Return a queued or started RQ job for the same import callable, if any."""
    import django_rq
    from rq.job import Job
    from rq.registry import StartedJobRegistry

    conn = django_rq.get_connection()
    queue = django_rq.get_queue("default")

    started = StartedJobRegistry(queue=queue)
    for job_id in started.get_job_ids():
        try:
            job = Job.fetch(job_id, connection=conn)
        except Exception:
            continue
        if job.func_name == import_path:
            return job

    for job_id in queue.job_ids:
        try:
            job = Job.fetch(job_id, connection=conn)
        except Exception:
            continue
        if job.func_name == import_path:
            return job
    return None


def _queue_demo_import(request, *, import_path: str, label, rulebook_name: str) -> bool:
    """Run large demos in RQ so the HTTP request does not time out."""
    import django_rq

    if _count_active_rq_workers() < 1:
        messages.error(
            request,
            _(
                "%(label)s import could not be queued: no RQ worker is running. "
                "Start the NetBox RQ worker (e.g. container netbox-dev-worker or "
                "`manage.py rqworker`) and try again."
            )
            % {"label": label},
        )
        return False

    pending = _find_pending_demo_job(import_path)
    if pending is not None:
        messages.info(
            request,
            _(
                "%(label)s import is already queued or running (job %(job_id)s). "
                "The rulebook «%(rulebook)s» is replaced when that job starts; "
                "allow about 1–2 minutes of processing after it begins."
            )
            % {
                "label": label,
                "job_id": pending.id,
                "rulebook": rulebook_name,
            },
        )
        return True

    queue = django_rq.get_queue("default")
    job = queue.enqueue(
        import_path,
        kwargs={"recreate": True},
        job_timeout=900,
        failure_ttl=3600,
        result_ttl=3600,
    )
    backlog = max(len(queue.job_ids) - 1, 0)
    if backlog:
        messages.success(
            request,
            _(
                "%(label)s import queued (job %(job_id)s); %(backlog)s other job(s) "
                "are ahead in the worker queue. The rulebook «%(rulebook)s» will be "
                "recreated when this job starts (~1–2 minutes of work). "
                "Find it under Security → Rulebooks."
            )
            % {
                "label": label,
                "job_id": job.id,
                "backlog": backlog,
                "rulebook": rulebook_name,
            },
        )
    else:
        messages.success(
            request,
            _(
                "%(label)s import started in the background (job %(job_id)s). "
                "The rulebook «%(rulebook)s» will be recreated in about 1–2 minutes "
                "(any existing rulebook with that name is removed when the job "
                "starts, not when you click Create). Find it under Security → Rulebooks."
            )
            % {"label": label, "job_id": job.id, "rulebook": rulebook_name},
        )
    return True


def _create_zone_matrix_rulebook():
    from django.contrib.contenttypes.models import ContentType as DjCT
    from netbox_custom_objects.models import CustomObjectType

    rb, _ = Rulebook.objects.get_or_create(
        name="Demo - Zone Matrix",
        defaults={"rulebook_type": "security_rules"},
    )
    ensure_system_rulebook_fields(rb)
    fields = _upsert_object_fields(rb, _SECURITY_RULES_OBJECT_FIELD_SPECS)
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
        defaults={"rulebook_type": "security_rules"},
    )
    ensure_system_rulebook_fields(rb)
    fields = _upsert_object_fields(rb, _SECURITY_RULES_OBJECT_FIELD_SPECS)
    _apply_field_types(fields, _ADDRESSES_FIELD_TYPES)
    return rb


def _format_demo_summary(summary: dict) -> str:
    parts = []
    if summary.get("skipped"):
        parts.append(_("already complete"))
    if summary.get("rules") is not None:
        parts.append(_("%(count)s rules") % {"count": summary["rules"]})
    if summary.get("zones") is not None:
        parts.append(_("%(count)s zones") % {"count": summary["zones"]})
    if summary.get("pairs") is not None:
        parts.append(_("%(count)s address pairs") % {"count": summary["pairs"]})
    if summary.get("object_items") is not None:
        parts.append(_("%(count)s object items") % {"count": summary["object_items"]})
    if summary.get("elapsed_s") is not None:
        parts.append(_("%(seconds)s s") % {"seconds": summary["elapsed_s"]})
    return ", ".join(str(part) for part in parts)


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
    elif action == "create_demo_addresses_scale":
        _ensure_demo_prerequisites()
        _queue_demo_import(
            request,
            import_path="netbox_nsm.demos.addresses_scale.create_addresses_scale_demo",
            label=_("Addresses demo"),
            rulebook_name="Demo - Addresses",
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
