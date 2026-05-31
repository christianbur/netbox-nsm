"""
Generates N firewall rules in bulk for load testing.
Run with:
  docker compose exec netbox python /app/netbox/netbox/manage.py shell < /netbox-nsm/gen_rules.py
"""

import random
import sys
import time

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from netbox_nsm.models import (
    SecurityArea,
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyRuleObjectItem,
)

# ── Config ────────────────────────────────────────────────────────────────────
RULEBOOK_PK   = 1
N_RULES       = 10_000
BATCH_SIZE    = 500       # rules per DB transaction
START_INDEX   = None      # None = auto-detect (max existing + 1)
# ─────────────────────────────────────────────────────────────────────────────

# Load areas
areas = {a.slug: a for a in SecurityArea.objects.all()}
area_src  = areas["source"]
area_dst  = areas["destination"]
area_svc  = areas["service"]
area_act  = areas["action"]

rulebook = SecurityPolicyRulebook.objects.get(pk=RULEBOOK_PK)

# Load available objects per area (as list of (ct_id, pk) tuples)
def _objs(ct_id):
    ct = ContentType.objects.get(pk=ct_id)
    mc = ct.model_class()
    ids = list(mc.objects.values_list("pk", flat=True))
    return ct_id, ct, ids

ct_zone_id, ct_zone, zone_pks   = _objs(188)   # zones  → src + dst
ct_svc_id,  ct_svc,  svc_pks    = _objs(187)   # services
ct_act_id,  ct_act,  act_pks    = _objs(184)   # actions

print(f"Zones: {len(zone_pks)}, Services: {len(svc_pks)}, Actions: {len(act_pks)}")

# Determine starting index
if START_INDEX is None:
    from django.db.models import Max
    max_idx = SecurityPolicyRule.objects.filter(rulebook=rulebook).aggregate(m=Max("index"))["m"] or 0
    START_INDEX = max_idx + 1

# Existing names (for duplicate avoidance)
existing_names = set(
    SecurityPolicyRule.objects.filter(rulebook=rulebook).values_list("name", flat=True)
)
print(f"Existing rules: {len(existing_names)}, starting index: {START_INDEX}")

created_total = 0
t0 = time.time()

for batch_start in range(0, N_RULES, BATCH_SIZE):
    batch_end = min(batch_start + BATCH_SIZE, N_RULES)
    batch_n   = batch_end - batch_start

    # 1. Build Rule objects
    rules_to_create = []
    names_this_batch = []
    for i in range(batch_n):
        global_i = batch_start + i
        idx      = START_INDEX + global_i
        name     = f"rule-gen-{idx:06d}"
        # skip if somehow duplicate
        if name in existing_names:
            name = f"rule-gen-{idx:06d}-x{random.randint(1000,9999)}"
        existing_names.add(name)
        names_this_batch.append(name)
        rules_to_create.append(SecurityPolicyRule(
            rulebook=rulebook,
            index=idx,
            enabled=random.choice([True, True, True, False]),  # 75% enabled
            name=name,
        ))

    with transaction.atomic():
        created_rules = SecurityPolicyRule.objects.bulk_create(rules_to_create)

        # 2. Build object items for each created rule
        items = []
        for rule in created_rules:
            src_pk  = random.choice(zone_pks)
            dst_pk  = random.choice(zone_pks)
            svc_pk  = random.choice(svc_pks)
            act_pk  = random.choice(act_pks)

            items.append(SecurityPolicyRuleObjectItem(
                rule=rule,
                area=area_src,
                placement="source",
                content_type_id=ct_zone_id,
                object_id=src_pk,
            ))
            items.append(SecurityPolicyRuleObjectItem(
                rule=rule,
                area=area_dst,
                placement="destination",
                content_type_id=ct_zone_id,
                object_id=dst_pk,
            ))
            items.append(SecurityPolicyRuleObjectItem(
                rule=rule,
                area=area_svc,
                placement="fixed",
                content_type_id=ct_svc_id,
                object_id=svc_pk,
            ))
            items.append(SecurityPolicyRuleObjectItem(
                rule=rule,
                area=area_act,
                placement="fixed",
                content_type_id=ct_act_id,
                object_id=act_pk,
            ))

        SecurityPolicyRuleObjectItem.objects.bulk_create(items, ignore_conflicts=True)

    created_total += len(created_rules)
    elapsed = time.time() - t0
    rate = created_total / elapsed if elapsed > 0 else 0
    eta  = (N_RULES - created_total) / rate if rate > 0 else 0
    print(f"  {created_total}/{N_RULES} rules  ({rate:.0f}/s  ETA {eta:.0f}s)", end="\r", flush=True)

print(f"\nDone. {created_total} rules created in {time.time()-t0:.1f}s")
