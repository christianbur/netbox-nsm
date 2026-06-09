"""100×100 zone matrix demo (10 000 COT rules) — not part of Setup wizard.

Creates ``demo-0001`` … ``demo-0100`` zones and rules on ``nsm_rb_scale_test``
(template 0003 — zones only). Rules are Custom Object rows with
``source_zones`` / ``destination_zones`` multiobject fields.

Ausführung::

    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_scale_demo.py
"""

from __future__ import annotations

import random
import time
from typing import Any

from django.db import transaction

from netbox_nsm.demos.cot_demo_common import (
    ensure_nsm_prerequisites,
    ensure_rulebook_cot,
    get_cot_model,
)

__all__ = (
    "ACTION_RANDOM_SEED",
    "GRID_SIZE",
    "RULE_COUNT",
    "SCALE_RULEBOOK_SLUG",
    "ZONE_COUNT",
    "ZONE_NAME_PREFIX",
    "create_scale_test_demo",
    "_matrix_indices",
)

GRID_SIZE = 100
ZONE_COUNT = 100
RULE_COUNT = GRID_SIZE * GRID_SIZE
ZONE_NAME_PREFIX = "demo-"
ACTION_RANDOM_SEED = 7

SCALE_RULEBOOK_SLUG = "nsm_rb_scale_test"
SCALE_RULEBOOK_TEMPLATE = "nsm_rb_0003_template"
_DEMO_RULE_PREFIX = "demo-rule-"


def _matrix_indices(rule_idx: int) -> tuple[int, int]:
    return rule_idx // GRID_SIZE, rule_idx % GRID_SIZE


def _zone_name(zone_idx: int) -> str:
    return f"{ZONE_NAME_PREFIX}{zone_idx + 1:04d}"


def _ensure_scale_rulebook():
    return ensure_rulebook_cot(
        slug=SCALE_RULEBOOK_SLUG,
        template_slug=SCALE_RULEBOOK_TEMPLATE,
        display_name="Scale Test",
    )


def _ensure_zones(ZoneModel, *, recreate: bool) -> list[Any]:
    if recreate:
        ZoneModel.objects.filter(name__startswith=ZONE_NAME_PREFIX).delete()

    zones: list[Any] = []
    for i in range(ZONE_COUNT):
        zone, _ = ZoneModel.objects.get_or_create(name=_zone_name(i))
        zones.append(zone)
    return zones


def _create_matrix_rules(
    rulebook_cot,
    *,
    zones: list[Any],
    recreate: bool,
) -> tuple[int, int]:
    RuleModel = rulebook_cot.get_model()
    if recreate:
        RuleModel.objects.filter(name__startswith=_DEMO_RULE_PREFIX).delete()

    services = list(get_cot_model("nsm_service", "nsm_services")[0].objects.all())
    actions = {
        obj.name.lower(): obj
        for obj in get_cot_model("nsm_action")[0].objects.all()
    }
    if not services or not actions:
        raise RuntimeError("Missing nsm_service or nsm_action seed objects.")

    act_rng = random.Random(ACTION_RANDOM_SEED)
    object_items = 0

    for rule_idx in range(RULE_COUNT):
        src_i, dst_i = _matrix_indices(rule_idx)
        index = rule_idx + 1
        name = f"{_DEMO_RULE_PREFIX}{rule_idx + 1:05d}"
        rule = RuleModel.objects.create(index=index, status=True, name=name)
        rule.source_zones.set([zones[src_i]])
        rule.destination_zones.set([zones[dst_i]])
        rule.services_applications.set([services[rule_idx % len(services)]])
        action_key = "permit" if act_rng.random() < 0.5 else "deny"
        rule.actions.set([actions.get(action_key) or next(iter(actions.values()))])
        object_items += 4

    return RULE_COUNT, object_items


def create_scale_test_demo(*, recreate: bool = False) -> dict[str, Any]:
    """Create zones and 10k COT matrix rules; return summary dict."""
    t0 = time.perf_counter()
    ensure_nsm_prerequisites()
    rulebook_cot = _ensure_scale_rulebook()
    ZoneModel, _ = get_cot_model("nsm_zone", "nsm_zones")

    with transaction.atomic():
        zones = _ensure_zones(ZoneModel, recreate=recreate)
        rules, object_items = _create_matrix_rules(
            rulebook_cot,
            zones=zones,
            recreate=recreate,
        )

    return {
        "rulebook": rulebook_cot.verbose_name or rulebook_cot.name,
        "rulebook_slug": rulebook_cot.slug,
        "rulebook_id": rulebook_cot.pk,
        "zones": len(zones),
        "rules": rules,
        "object_items": object_items,
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }
