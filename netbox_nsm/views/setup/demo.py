"""Setup: demo rulebook creation (COT-only).

Starter-Demo (20×20 Zonen-Matrix, Template 0003 — nur Zonen, zufällig permit/deny)::

    # Über NetBox Setup (Abschnitt 4) → „Starter-Demo“ → Anlegen
    # oder per Django-Shell:
    from netbox_nsm.views.setup.demo import create_demo_starter
    create_demo_starter()

Address Bench (50.000 Adressen, nur bei leerem IPAM)::

    # Setup → „Address Bench (50.000 Adressen)“
    # RQ-Worker muss laufen (netbox-dev-worker). Volllauf 200k nur per CLI:
    # scripts/create_addresses_million_scale.py

Ausführung im Container::

    docker compose exec netbox python3 manage.py shell -c \\
        "from netbox_nsm.views.setup.demo import create_demo_starter; create_demo_starter()"
"""

import io
import random
import sys
from pathlib import Path

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ipam.models import IPAddress

from netbox_nsm.rulebooks.templates import (
    DEMO_RULEBOOK_SLUG,
    DEMO_RULEBOOK_TEMPLATE_SLUG,
    build_rulebook_document,
    format_rulebook_display_name,
)

from .custom_objects import import_rulebook_templates

__all__ = (
    "DEMO_ACTION_RANDOM_SEED",
    "DEMO_ACTIONS",
    "DEMO_GRID_SIZE",
    "DEMO_RULE_COUNT",
    "DEMO_ZONE_COUNT",
    "_count_active_rq_workers",
    "_find_pending_demo_job",
    "_queue_demo_import",
    "handles_action",
    "handle_demo_action",
)

DEMO_GRID_SIZE = 20
DEMO_ZONE_COUNT = 20
DEMO_RULE_COUNT = DEMO_GRID_SIZE * DEMO_GRID_SIZE
DEMO_ACTION_RANDOM_SEED = 7
DEMO_ZONE_NAME_PREFIX = "zone_"
DEMO_RULE_NAME_PREFIX = "demo-rule-"

DEMO_ACTIONS = frozenset(
    {
        "create_demo_starter",
        "create_demo_enterprise",
        "create_demo_scale_50k",
    }
)

SCALE_DEMO_50K_IMPORT = (
    "netbox_nsm.demos.addresses_million_scale.create_addresses_scale_demo_50k"
)
SCALE_DEMO_50K_RULEBOOK_NAME = "Bench Addresses"


def _demo_zone_name(zone_idx: int) -> str:
    return f"{DEMO_ZONE_NAME_PREFIX}{zone_idx + 1:02d}"


def _matrix_indices(rule_idx: int) -> tuple[int, int]:
    return rule_idx // DEMO_GRID_SIZE, rule_idx % DEMO_GRID_SIZE


def _ensure_demo_prerequisites():
    """Import built-in Custom Object Types + TypeConfigs if not yet present."""
    from .custom_objects import (
        all_cots_ok,
        custom_objects_db_ready,
        get_cot_status,
        get_rulebook_template_status,
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
    rulebook_template_status = get_rulebook_template_status()
    if not all_cots_ok(cot_status, rulebook_template_status):
        import_all_types()
    else:
        _ensure_builtin_default_objects()

    tc_status = get_typeconfig_status()
    if not all_typeconfigs_ok(cot_status, tc_status):
        create_all_typeconfigs()

    from netbox_nsm.views.custom_objects_sync import _prune_bundled_network_app_defaults

    for slug in ("nsm_app_network", "nsm_network_app", "nsm_network_apps"):
        _prune_bundled_network_app_defaults(slug)


def _ensure_rulebook_templates() -> None:
    """Deploy bundled rulebook templates (group NSM Rulebook Templates)."""
    import_rulebook_templates()


def _ensure_nsm_rb_demo_rulebook() -> None:
    """Create demo rulebook nsm_rb_demo from template 0003 (zones only)."""
    from netbox_custom_objects.models import CustomObjectType
    from netbox_custom_objects.schema.executor import apply_document

    if CustomObjectType.objects.filter(slug=DEMO_RULEBOOK_SLUG).exists():
        return

    document = build_rulebook_document(
        template_slug=DEMO_RULEBOOK_TEMPLATE_SLUG,
        rulebook_slug=DEMO_RULEBOOK_SLUG,
        verbose_name=format_rulebook_display_name("Demo"),
    )
    apply_document(document, allow_destructive=False)


def _ensure_builtin_default_objects() -> None:
    """Seed Permit/HTTPS/etc. when COTs exist but default rows were never created."""
    from netbox_custom_objects.models import CustomObjectType

    from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES
    from netbox_nsm.views.custom_objects_sync import _seed_default_objects

    needs_seed = False
    for slug in ("nsm_action", "nsm_service", "nsm_zone"):
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


def _queue_demo_import(
    request,
    *,
    import_path: str,
    label,
    rulebook_name: str,
    job_timeout: int = 900,
    processing_minutes: str = "1–2",
) -> bool:
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
                "allow about %(minutes)s minutes of processing after it begins."
            )
            % {
                "label": label,
                "job_id": pending.id,
                "rulebook": rulebook_name,
                "minutes": processing_minutes,
            },
        )
        return True

    queue = django_rq.get_queue("default")
    job = queue.enqueue(
        import_path,
        kwargs={"recreate": True},
        job_timeout=job_timeout,
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
                "recreated when this job starts (~%(minutes)s minutes of work). "
                "Find it under Security → Rulebooks."
            )
            % {
                "label": label,
                "job_id": job.id,
                "backlog": backlog,
                "rulebook": rulebook_name,
                "minutes": processing_minutes,
            },
        )
    else:
        messages.success(
            request,
            _(
                "%(label)s import started in the background (job %(job_id)s). "
                "The rulebook «%(rulebook)s» will be recreated in about %(minutes)s minutes "
                "(any existing rulebook with that name is removed when the job "
                "starts, not when you click Create). Find it under Security → Rulebooks."
            )
            % {
                "label": label,
                "job_id": job.id,
                "rulebook": rulebook_name,
                "minutes": processing_minutes,
            },
        )
    return True


def _get_custom_objects_by_name(slug):
    from netbox_custom_objects.models import CustomObjectType

    try:
        cot = CustomObjectType.objects.get(slug=slug)
        model = cot.get_model()
        return {obj.name.lower(): obj for obj in model.objects.all()}
    except Exception:
        return {}


def _ensure_demo_zones():
    """Create zone_01 … zone_20 for the starter matrix demo."""
    from netbox_custom_objects.models import CustomObjectType

    zone_cot = CustomObjectType.objects.get(slug="nsm_zone")
    zone_model = zone_cot.get_model()
    zones = []
    for zone_idx in range(DEMO_ZONE_COUNT):
        zone, _ = zone_model.objects.get_or_create(name=_demo_zone_name(zone_idx))
        zones.append(zone)
    return zones


def _create_rb_demo_starter_rules():
    """Seed nsm_rb_demo with a 20×20 zone matrix (400 rules, random permit/deny)."""
    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.get(slug=DEMO_RULEBOOK_SLUG)
    model = cot.get_model()
    model.objects.all().delete()

    zones = _ensure_demo_zones()
    services_by_name = _get_custom_objects_by_name("nsm_service")
    actions_by_name = _get_custom_objects_by_name("nsm_action")
    https = services_by_name.get("https")
    act_rng = random.Random(DEMO_ACTION_RANDOM_SEED)

    rules = model.objects.bulk_create(
        [
            model(
                index=rule_idx + 1,
                status=True,
                name=(
                    f"{DEMO_RULE_NAME_PREFIX}"
                    f"{_demo_zone_name(src_i)}-to-{_demo_zone_name(dst_i)}"
                ),
            )
            for rule_idx in range(DEMO_RULE_COUNT)
            for src_i, dst_i in [_matrix_indices(rule_idx)]
        ],
        batch_size=100,
    )

    for rule_idx, rule in enumerate(rules):
        src_i, dst_i = _matrix_indices(rule_idx)
        rule.source_zones.set([zones[src_i]])
        rule.destination_zones.set([zones[dst_i]])
        action_key = "permit" if act_rng.random() < 0.5 else "deny"
        action = actions_by_name.get(action_key) or next(
            iter(actions_by_name.values()), None
        )
        if action is not None:
            rule.actions.set([action])
        if https is not None:
            rule.services_applications.set([https])

    return cot


def create_demo_starter():
    """Built-in COTs/TypeConfigs (if needed) and nsm_rb_demo with 20×20 zone matrix."""
    _ensure_demo_prerequisites()
    _ensure_rulebook_templates()
    _ensure_nsm_rb_demo_rulebook()
    with transaction.atomic():
        rb_demo_cot = _create_rb_demo_starter_rules()
    return rb_demo_cot


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
        rb_demo_cot = create_demo_starter()
        messages.success(
            request,
            _(
                "Starter demo created: %(zone_count)s zones, %(rule_count)s rules "
                "(random permit/deny) in custom-object type '%(rb_slug)s' "
                "(template 0003, zones only). "
                "Custom Object Types / TypeConfigs were imported if missing."
            )
            % {
                "zone_count": DEMO_ZONE_COUNT,
                "rule_count": DEMO_RULE_COUNT,
                "rb_slug": rb_demo_cot.slug,
            },
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
    elif action == "create_demo_scale_50k":
        if IPAddress.objects.exists():
            messages.error(
                request,
                _(
                    "%(label)s requires an empty IP address database "
                    "(IPAM → IP addresses)."
                )
                % {"label": _("Address bench (50k)")},
            )
            return redirect(reverse("plugins:netbox_nsm:setup"))
        _queue_demo_import(
            request,
            import_path=SCALE_DEMO_50K_IMPORT,
            label=_("Address bench (50k)"),
            rulebook_name=SCALE_DEMO_50K_RULEBOOK_NAME,
            job_timeout=3600,
            processing_minutes="5–15",
        )
    return redirect(reverse("plugins:netbox_nsm:setup"))
