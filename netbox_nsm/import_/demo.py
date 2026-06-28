"""Setup: demo rulebook creation (COT-only).

Zone-Matrix (250×250, portable-schema YAML) via run_bundle::

    # Setup → „NSM Demo Zone Matrix" → Anlegen (via nsm_demo_zone_matrix bundle)
    # oder per Django-Shell:
    from netbox_nsm.import_.demo import create_demo_starter_data_only
    create_demo_starter_data_only()

Address Bench (50.000 Adressen) via run_bundle::

    # Setup → „NSM Demo Zone/Address/AdressGroup" (needs_confirm=true, RQ worker required)

Ausführung im Container::

    docker compose exec netbox python3 manage.py shell -c \\
        "from netbox_nsm.import_.demo import create_demo_starter_data_only; create_demo_starter_data_only()"
"""

import random

from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from netbox_nsm.core.plugin_labels import get_nsm_menu_label
from netbox_nsm.rulebooks.templates import (
    DEMO_RULEBOOK_SLUG,
)

from .custom_objects import custom_objects_db_ready

__all__ = (
    "DEMO_ACTION_RANDOM_SEED",
    "DEMO_GRID_SIZE",
    "DEMO_RULE_COUNT",
    "DEMO_ZONE_COUNT",
    "SCALE_DEMO_50K_IMPORT",
    "SCALE_DEMO_50K_RULEBOOK_NAME",
    "_count_active_rq_workers",
    "_find_pending_demo_job",
    "_queue_demo_import",
    "create_demo_starter_data_only",
)

DEMO_GRID_SIZE = 250
DEMO_ZONE_COUNT = 250
DEMO_RULE_COUNT = DEMO_GRID_SIZE * DEMO_GRID_SIZE
DEMO_ACTION_RANDOM_SEED = 7
DEMO_ZONE_NAME_PREFIX = "zone_"
DEMO_RULE_NAME_PREFIX = "demo-rule-"
DEMO_M2M_BATCH_SIZE = 5000
DEMO_RULE_BATCH_SIZE = 1000

SCALE_DEMO_50K_IMPORT = (
    "netbox_nsm.import_.demo_scale.create_addresses_scale_demo_50k"
)
SCALE_DEMO_50K_RULEBOOK_NAME = "Bench Addresses"


def _demo_zone_name_width() -> int:
    return max(2, len(str(DEMO_ZONE_COUNT)))


def _demo_zone_name(zone_idx: int) -> str:
    return f"{DEMO_ZONE_NAME_PREFIX}{zone_idx + 1:0{_demo_zone_name_width()}d}"


def _matrix_indices(rule_idx: int) -> tuple[int, int]:
    return rule_idx // DEMO_GRID_SIZE, rule_idx % DEMO_GRID_SIZE


def _ensure_demo_prerequisites():
    """Ensure NSM Schema is applied before demo data creation."""
    from netbox_nsm.import_.custom_objects import core_bundle_applied

    if not custom_objects_db_ready():
        raise RuntimeError(
            "netbox-custom-objects database tables are missing "
            "(migrate netbox_custom_objects first)."
        )
    if not core_bundle_applied():
        raise RuntimeError("Apply nsm_schema.json from Setup before running demos.")


def create_demo_starter_data_only():
    """Populate nsm_rb_demo with 250×250 zone matrix (schema must exist)."""
    from django.db import transaction

    from netbox_custom_objects.models import CustomObjectType

    if not CustomObjectType.objects.filter(slug=DEMO_RULEBOOK_SLUG).exists():
        raise RuntimeError(
            f"Rulebook {DEMO_RULEBOOK_SLUG} missing — apply nsm_schema.json first."
        )
    _ensure_demo_prerequisites()
    with transaction.atomic():
        return _create_rb_demo_starter_rules()


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
                "Find it under %(menu_label)s → Rulebooks."
            )
            % {
                "label": label,
                "job_id": job.id,
                "backlog": backlog,
                "rulebook": rulebook_name,
                "minutes": processing_minutes,
                "menu_label": get_nsm_menu_label(),
            },
        )
    else:
        messages.success(
            request,
            _(
                "%(label)s import started in the background (job %(job_id)s). "
                "The rulebook «%(rulebook)s» will be recreated in about %(minutes)s minutes "
                "(any existing rulebook with that name is removed when the job "
                "starts, not when you click Create). Find it under %(menu_label)s → Rulebooks."
            )
            % {
                "label": label,
                "job_id": job.id,
                "rulebook": rulebook_name,
                "minutes": processing_minutes,
                "menu_label": get_nsm_menu_label(),
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
    """Create zone_001 … zone_N for the starter matrix demo."""
    from netbox_custom_objects.models import CustomObjectType

    zone_cot = CustomObjectType.objects.get(slug="nsm_zone")
    zone_model = zone_cot.get_model()
    zones = []
    for zone_idx in range(DEMO_ZONE_COUNT):
        zone, _ = zone_model.objects.get_or_create(name=_demo_zone_name(zone_idx))
        zones.append(zone)
    return zones


def _get_cot_field_through_model(cot, field_name: str):
    from django.apps import apps

    from netbox_custom_objects import constants

    field = cot.fields.get(name=field_name)
    return apps.get_model(constants.APP_LABEL, field.through_model_name)


def _bulk_seed_demo_matrix_relations(
    *,
    cot,
    rules,
    zones,
    actions_by_name: dict,
    act_rng: random.Random,
) -> None:
    from django.contrib.contenttypes.models import ContentType

    zone_ct_id = ContentType.objects.get_for_model(zones[0]).pk
    fallback_action = next(iter(actions_by_name.values()), None)

    for field_name, zone_index in (("source", 0), ("destination", 1)):
        Through = _get_cot_field_through_model(cot, field_name)
        rows = [
            Through(
                source_id=rule.pk,
                content_type_id=zone_ct_id,
                object_id=zones[_matrix_indices(rule_idx)[zone_index]].pk,
            )
            for rule_idx, rule in enumerate(rules)
        ]
        Through.objects.bulk_create(rows, batch_size=DEMO_M2M_BATCH_SIZE)

    if not fallback_action:
        return

    ActionsThrough = _get_cot_field_through_model(cot, "actions")
    action_rows = []
    for rule in rules:
        action_key = "permit" if act_rng.random() < 0.5 else "deny"
        action = actions_by_name.get(action_key) or fallback_action
        action_rows.append(
            ActionsThrough(source_id=rule.pk, target_id=action.pk)
        )
    ActionsThrough.objects.bulk_create(action_rows, batch_size=DEMO_M2M_BATCH_SIZE)


def _create_rb_demo_starter_rules():
    """Seed nsm_rb_demo with a 250×250 zone matrix (62.5k rules, random permit/deny)."""
    from netbox_custom_objects.models import CustomObjectType

    cot = CustomObjectType.objects.get(slug=DEMO_RULEBOOK_SLUG)
    model = cot.get_model()
    model.objects.all().delete()

    zones = _ensure_demo_zones()
    actions_by_name = _get_custom_objects_by_name("nsm_action")
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
        batch_size=DEMO_RULE_BATCH_SIZE,
    )

    _bulk_seed_demo_matrix_relations(
        cot=cot,
        rules=rules,
        zones=zones,
        actions_by_name=actions_by_name,
        act_rng=act_rng,
    )

    return cot
