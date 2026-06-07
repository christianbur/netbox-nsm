"""Large-scale demo: 100×100 zone matrix with 10 000 policy rules (one per cell)."""

from __future__ import annotations

import random
import time

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from netbox_custom_objects.models import CustomObjectType
from netbox_nsm.models.rulebook import Rule, Rulebook, RuleObjectItem
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields

__all__ = (
    "GRID_SIZE",
    "RULE_COUNT",
    "RULEBOOK_NAME",
    "ZONE_COUNT",
    "ZONE_NAME_PREFIX",
    "create_scale_test_demo",
)

RULEBOOK_NAME = "Demo - Scale Test"
GRID_SIZE = 100
ZONE_COUNT = GRID_SIZE
RULE_COUNT = GRID_SIZE * GRID_SIZE
ZONE_NAME_PREFIX = "demo-"
ACTION_RANDOM_SEED = 42
BATCH_SIZE = 2500


def _zone_color(index: int) -> str:
    hue = (index * 37) % 360
    return f"hsl({hue} 55% 42%)"


def _get_cot_model(slug: str):
    cot = CustomObjectType.objects.get(slug=slug)
    model = cot.get_model()
    ct = ContentType.objects.get_for_model(model)
    return cot, model, ct


def _lookup_objects_by_name(model, *, prefix: str | None = None) -> dict[str, object]:
    qs = model.objects.all()
    if prefix:
        qs = qs.filter(name__startswith=prefix)
    return {obj.name.lower(): obj for obj in qs}


def _ensure_zones(zone_model, *, count: int) -> list:
    existing = list(
        zone_model.objects.filter(name__startswith=ZONE_NAME_PREFIX).order_by("name")
    )
    if len(existing) >= count:
        return existing[:count]

    start = len(existing)
    to_create = []
    for i in range(start, count):
        num = i + 1
        to_create.append(
            zone_model(
                name=f"{ZONE_NAME_PREFIX}{num:04d}",
                color=_zone_color(i),
            )
        )
    if to_create:
        zone_model.objects.bulk_create(to_create, batch_size=BATCH_SIZE)
    return list(
        zone_model.objects.filter(name__startswith=ZONE_NAME_PREFIX).order_by("name")[
            :count
        ]
    )


def _ensure_rulebook_fields(rb):
    from netbox_nsm.views.setup.demo import (
        _SECURITY_RULES_OBJECT_FIELD_SPECS,
        _ZONE_MATRIX_FIELD_TYPES,
        _apply_field_types,
        _upsert_object_fields,
    )

    ensure_system_rulebook_fields(rb)
    fields = _upsert_object_fields(rb, _SECURITY_RULES_OBJECT_FIELD_SPECS)
    _apply_field_types(fields, _ZONE_MATRIX_FIELD_TYPES)
    return fields


def _matrix_indices(rule_index: int) -> tuple[int, int]:
    """Map rule index 0..9999 to a full GRID_SIZE×GRID_SIZE source/destination pair."""
    src_idx = rule_index // GRID_SIZE
    dst_idx = rule_index % GRID_SIZE
    return src_idx, dst_idx


def create_scale_test_demo(*, recreate: bool = True) -> dict:
    """
    Create ``Demo - Scale Test`` with *ZONE_COUNT* zones and *RULE_COUNT* rules.

    Each rule maps to one matrix cell (source row × destination column).
    Returns a summary dict with counts and elapsed seconds.
    """
    from netbox_nsm.views.setup.demo import _ensure_demo_prerequisites

    started = time.monotonic()
    _ensure_demo_prerequisites()

    _zone_cot, zone_model, zone_ct = _get_cot_model("nsm_zones")
    _svc_cot, svc_model, svc_ct = _get_cot_model("nsm_services")
    _act_cot, act_model, act_ct = _get_cot_model("nsm_action")

    if recreate:
        with transaction.atomic():
            for existing in Rulebook.objects.filter(name=RULEBOOK_NAME):
                Rule.objects.filter(rulebook=existing).delete()
                existing.delete()

    with transaction.atomic():
        rb, _ = Rulebook.objects.get_or_create(
            name=RULEBOOK_NAME,
            defaults={
                "rulebook_type": "security_rules",
                "description": "100×100 matrix performance / UI scale test",
            },
        )
        fields = _ensure_rulebook_fields(rb)
        zones = _ensure_zones(zone_model, count=ZONE_COUNT)

    if len(zones) < ZONE_COUNT:
        raise RuntimeError(
            f"Expected {ZONE_COUNT} zones, got {len(zones)} after bulk create."
        )

    services = _lookup_objects_by_name(svc_model)
    actions = _lookup_objects_by_name(act_model)
    svc_https = services.get("https")
    svc_ssh = services.get("ssh")
    svc_dns = services.get("dns-udp")
    act_permit = actions.get("permit")
    act_deny = actions.get("deny")
    if not all((svc_https, svc_ssh, act_permit, act_deny)):
        raise RuntimeError(
            "Missing default Services/Action objects. Run Setup → Custom Objects import first."
        )
    svc_pool = [svc_https, svc_ssh, svc_dns or svc_https]
    rng = random.Random(ACTION_RANDOM_SEED)
    rule_actions = [
        act_permit if rng.random() < 0.5 else act_deny for _ in range(RULE_COUNT)
    ]

    existing_rules = Rule.objects.filter(rulebook=rb).count()
    if existing_rules >= RULE_COUNT:
        elapsed = time.monotonic() - started
        return {
            "rulebook": rb.name,
            "rulebook_id": rb.pk,
            "grid_size": GRID_SIZE,
            "zones": len(zones),
            "rules": existing_rules,
            "object_items": RuleObjectItem.objects.filter(rule__rulebook=rb).count(),
            "elapsed_s": round(elapsed, 1),
            "skipped": True,
        }

    rules_created = 0
    items_created = 0
    field_source = fields["source"]
    field_dest = fields["destination"]
    field_service = fields["service"]
    field_action = fields["action"]

    for batch_start in range(0, RULE_COUNT, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, RULE_COUNT)
        with transaction.atomic():
            rule_rows = []
            for i in range(batch_start, batch_end):
                src_idx, dst_idx = _matrix_indices(i)
                rule_rows.append(
                    Rule(
                        rulebook=rb,
                        name=f"matrix-{src_idx + 1:03d}x{dst_idx + 1:03d}",
                        index=(i + 1) * 10,
                        enabled=True,
                    )
                )
            Rule.objects.bulk_create(rule_rows, batch_size=BATCH_SIZE)
            rules_created += len(rule_rows)

            created_rules = list(
                Rule.objects.filter(
                    rulebook=rb,
                    index__gte=(batch_start + 1) * 10,
                    index__lte=batch_end * 10,
                ).order_by("index")
            )
            if len(created_rules) != len(rule_rows):
                raise RuntimeError("Rule bulk_create count mismatch after reload.")

            item_rows = []
            for offset, rule in enumerate(created_rules):
                i = batch_start + offset
                src_idx, dst_idx = _matrix_indices(i)
                src_zone = zones[src_idx]
                dst_zone = zones[dst_idx]
                svc = svc_pool[i % len(svc_pool)]
                act = rule_actions[i]

                item_rows.extend(
                    [
                        RuleObjectItem(
                            rule=rule,
                            field=field_source,
                            content_type=zone_ct,
                            object_id=src_zone.pk,
                            exclude=False,
                        ),
                        RuleObjectItem(
                            rule=rule,
                            field=field_dest,
                            content_type=zone_ct,
                            object_id=dst_zone.pk,
                            exclude=False,
                        ),
                        RuleObjectItem(
                            rule=rule,
                            field=field_service,
                            content_type=svc_ct,
                            object_id=svc.pk,
                            exclude=False,
                        ),
                        RuleObjectItem(
                            rule=rule,
                            field=field_action,
                            content_type=act_ct,
                            object_id=act.pk,
                            exclude=False,
                        ),
                    ]
                )
            RuleObjectItem.objects.bulk_create(item_rows, batch_size=BATCH_SIZE)
            items_created += len(item_rows)

    elapsed = time.monotonic() - started
    return {
        "rulebook": rb.name,
        "rulebook_id": rb.pk,
        "grid_size": GRID_SIZE,
        "zones": len(zones),
        "rules": rules_created,
        "object_items": items_created,
        "elapsed_s": round(elapsed, 1),
        "skipped": False,
    }
