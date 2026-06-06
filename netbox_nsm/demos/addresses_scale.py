"""Demo - Addresses: 6 000 fully populated policy rules (zones + matching addresses)."""

from __future__ import annotations

import random
import time

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ipam.models import IPAddress, IPRange, Prefix
from netaddr import IPNetwork

from netbox_custom_objects.models import CustomObjectType
from netbox_nsm.models.rulebook import Rule, Rulebook, RuleObjectItem

__all__ = (
    "OBJECT_COUNT_VARIANTS",
    "PAIR_COUNT",
    "RULE_COUNT",
    "RULEBOOK_NAME",
    "create_addresses_scale_demo",
)

RULEBOOK_NAME = "Demo - Addresses"
RULE_COUNT = 6000
PAIR_COUNT = 80
OBJECT_COUNT_VARIANTS = (1, 2, 3, 6, 8)
PAIR_PREFIX = "demo-addr-"
DEMO_IPAM_PARENT = "10.245.0.0/16"
DEMO_IPAM_STATUS = "active"
ACTION_RANDOM_SEED = 202606
BATCH_SIZE = 2000


def _zone_color(index: int) -> str:
    hue = (index * 29) % 360
    return f"hsl({hue} 52% 40%)"


def _get_cot_model(slug: str):
    cot = CustomObjectType.objects.get(slug=slug)
    model = cot.get_model()
    ct = ContentType.objects.get_for_model(model)
    return cot, model, ct


def _lookup_objects_by_name(model) -> dict[str, object]:
    return {obj.name.lower(): obj for obj in model.objects.all()}


def _ensure_demo_ipam_parent() -> Prefix:
    parent, _ = Prefix.objects.get_or_create(
        prefix=DEMO_IPAM_PARENT,
        defaults={
            "status": DEMO_IPAM_STATUS,
            "description": "Demo - Addresses (scale demo IP space)",
        },
    )
    return parent


def _ipam_ref_for_pair_index(index: int) -> dict:
    """
    One IPAM object per address pair: prefix, host (/32), or range (rotating).

    Dedicated demo space: 10.245.0.0/16 (prefixes), 10.246.0.0/16 (hosts),
    10.247.0.0/16 (ranges).
    """
    subnet = index + 1
    kind = index % 3

    if kind == 0:
        cidr = f"10.245.{subnet}.0/24"
        prefix_obj, _ = Prefix.objects.get_or_create(
            prefix=cidr,
            defaults={
                "status": DEMO_IPAM_STATUS,
                "description": f"Demo - Addresses prefix for {PAIR_PREFIX}{index + 1:04d}",
            },
        )
        return {
            "prefix": prefix_obj,
            "ip_address": None,
            "range": None,
            "ipam_label": cidr,
        }

    if kind == 1:
        host = f"10.246.{subnet}.1/32"
        ip_obj, _ = IPAddress.objects.get_or_create(
            address=host,
            defaults={
                "status": DEMO_IPAM_STATUS,
                "description": f"Demo - Addresses host for {PAIR_PREFIX}{index + 1:04d}",
            },
        )
        return {
            "prefix": None,
            "ip_address": ip_obj,
            "range": None,
            "ipam_label": host,
        }

    start = f"10.247.{subnet}.10/32"
    end = f"10.247.{subnet}.50/32"
    start_net = IPNetwork(start)
    end_net = IPNetwork(end)
    range_obj = IPRange.objects.filter(
        start_address=start_net, end_address=end_net
    ).first()
    if range_obj is None:
        range_obj = IPRange.objects.create(
            start_address=start_net,
            end_address=end_net,
            status=DEMO_IPAM_STATUS,
            description=f"Demo - Addresses range for {PAIR_PREFIX}{index + 1:04d}",
        )
    return {
        "prefix": None,
        "ip_address": None,
        "range": range_obj,
        "ipam_label": f"{start} – {end}",
    }


def _apply_ipam_to_address(addr, ipam_ref: dict) -> None:
    addr.prefix = ipam_ref.get("prefix")
    addr.ip_address = ipam_ref.get("ip_address")
    addr.range = ipam_ref.get("range")
    addr.comments = ipam_ref.get("ipam_label") or ""
    addr.save(update_fields=["prefix_id", "ip_address_id", "range_id", "comments"])


def _ensure_zone_address_pairs(
    zone_model, addr_model, *, count: int
) -> list[tuple[object, object]]:
    _ensure_demo_ipam_parent()
    pairs: list[tuple[object, object]] = []
    for i in range(count):
        name = f"{PAIR_PREFIX}{i + 1:04d}"
        ipam_ref = _ipam_ref_for_pair_index(i)
        zone, _ = zone_model.objects.get_or_create(
            name=name,
            defaults={"color": _zone_color(i)},
        )
        addr_defaults = {
            "description": f"Address object for zone {name}",
            "comments": ipam_ref["ipam_label"],
            "prefix": ipam_ref["prefix"],
            "ip_address": ipam_ref["ip_address"],
            "range": ipam_ref["range"],
        }
        addr, created = addr_model.objects.get_or_create(
            name=name,
            defaults=addr_defaults,
        )
        if not created:
            linked = bool(addr.prefix_id or addr.ip_address_id or addr.range_id)
            needs_ipam = (
                not linked
                or (ipam_ref["prefix"] and addr.prefix_id != ipam_ref["prefix"].pk)
                or (
                    ipam_ref["ip_address"]
                    and addr.ip_address_id != ipam_ref["ip_address"].pk
                )
                or (ipam_ref["range"] and addr.range_id != ipam_ref["range"].pk)
            )
            if needs_ipam:
                _apply_ipam_to_address(addr, ipam_ref)
        pairs.append((zone, addr))
    return pairs


def _ensure_addresses_rulebook():
    from netbox_nsm.views.setup.demo import _create_addresses_rulebook

    return _create_addresses_rulebook()


def _object_count_for_side(rule_index: int, *, side: str) -> int:
    """Deterministic 1/2/3/6/8 object counts; source and destination differ per rule."""
    variants = OBJECT_COUNT_VARIANTS
    if side == "source":
        return variants[rule_index % len(variants)]
    return variants[(rule_index * 3 + 2) % len(variants)]


def _side_indices(rule_index: int, *, offset: int, count: int) -> tuple[int, ...]:
    count = max(1, min(int(count), PAIR_COUNT))
    start = (rule_index + offset) % PAIR_COUNT
    return tuple((start + step) % PAIR_COUNT for step in range(count))


def create_addresses_scale_demo(*, recreate: bool = True) -> dict:
    """
    Populate ``Demo - Addresses`` with *RULE_COUNT* rules.

    Each rule includes a varying number of matching zone + address pairs per side
    (counts cycle through 1, 2, 3, 6, 8), plus service(s) and action.
    """
    from netbox_nsm.views.setup.demo import _ensure_demo_prerequisites

    started = time.monotonic()
    _ensure_demo_prerequisites()

    _zone_cot, zone_model, zone_ct = _get_cot_model("nsm_zones")
    _addr_cot, addr_model, addr_ct = _get_cot_model("nsm_addresses")
    _svc_cot, svc_model, svc_ct = _get_cot_model("nsm_services")
    _act_cot, act_model, act_ct = _get_cot_model("nsm_action")

    netapp_ct = None
    netapp_model = None
    try:
        _na_cot, netapp_model, netapp_ct = _get_cot_model("nsm_network_apps")
    except Exception:
        netapp_model = None
        netapp_ct = None

    with transaction.atomic():
        rb = _ensure_addresses_rulebook()
        if recreate:
            Rule.objects.filter(rulebook=rb).delete()

        fields = {
            f.slug: f
            for f in rb.fields.filter(
                slug__in=("source", "destination", "service", "action")
            )
        }
        required = ("source", "destination", "service", "action")
        missing = [slug for slug in required if slug not in fields]
        if missing:
            raise RuntimeError(f"Rulebook missing fields: {', '.join(missing)}")

        pairs = _ensure_zone_address_pairs(zone_model, addr_model, count=PAIR_COUNT)

    services = _lookup_objects_by_name(svc_model)
    actions = _lookup_objects_by_name(act_model)
    netapps = _lookup_objects_by_name(netapp_model) if netapp_model else {}

    svc_https = services.get("https")
    svc_ssh = services.get("ssh")
    svc_dns = services.get("dns-udp")
    act_permit = actions.get("permit")
    act_deny = actions.get("deny")
    netapp_web = (
        netapps.get("web") or netapps.get("ssl") or next(iter(netapps.values()), None)
    )

    if not all((svc_https, act_permit, act_deny)):
        raise RuntimeError(
            "Missing default Services/Action objects. Run Setup → Custom Objects import first."
        )
    svc_pool = [svc for svc in (svc_https, svc_ssh, svc_dns) if svc]
    rng = random.Random(ACTION_RANDOM_SEED)
    rule_actions = [
        act_permit if rng.random() < 0.55 else act_deny for _ in range(RULE_COUNT)
    ]

    existing_rules = Rule.objects.filter(rulebook=rb).count()
    if existing_rules >= RULE_COUNT:
        elapsed = time.monotonic() - started
        return {
            "rulebook": rb.name,
            "rulebook_id": rb.pk,
            "pairs": len(pairs),
            "rules": existing_rules,
            "object_items": RuleObjectItem.objects.filter(rule__rulebook=rb).count(),
            "elapsed_s": round(elapsed, 1),
            "skipped": True,
        }

    field_source = fields["source"]
    field_dest = fields["destination"]
    field_service = fields["service"]
    field_action = fields["action"]

    rules_created = 0
    items_created = 0

    for batch_start in range(0, RULE_COUNT, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, RULE_COUNT)
        with transaction.atomic():
            rule_rows = []
            for i in range(batch_start, batch_end):
                src_count = _object_count_for_side(i, side="source")
                dst_count = _object_count_for_side(i, side="destination")
                src_idxs = _side_indices(i, offset=0, count=src_count)
                dst_idxs = _side_indices(i, offset=31, count=dst_count)
                src_names = [pairs[idx][0].name for idx in src_idxs]
                dst_names = [pairs[idx][0].name for idx in dst_idxs]
                desc = (
                    f"Source ×{len(src_names)} ({', '.join(src_names[:3])}"
                    f"{'…' if len(src_names) > 3 else ''}) → "
                    f"Dest ×{len(dst_names)} ({', '.join(dst_names[:3])}"
                    f"{'…' if len(dst_names) > 3 else ''})"
                )
                rule_rows.append(
                    Rule(
                        rulebook=rb,
                        name=f"addr-rule-{i + 1:05d}",
                        index=(i + 1) * 10,
                        enabled=True,
                        description=desc[:200],
                    )
                )
            Rule.objects.bulk_create(rule_rows, batch_size=BATCH_SIZE)
            rules_created += len(rule_rows)

            created_rules = list(
                Rule.objects.filter(
                    rulebook=rb,
                    name__gte=f"addr-rule-{batch_start + 1:05d}",
                    name__lte=f"addr-rule-{batch_end:05d}",
                ).order_by("index")
            )
            if len(created_rules) != len(rule_rows):
                raise RuntimeError("Rule bulk_create count mismatch after reload.")

            item_rows = []
            for offset, rule in enumerate(created_rules):
                i = batch_start + offset
                src_idxs = _side_indices(
                    i,
                    offset=0,
                    count=_object_count_for_side(i, side="source"),
                )
                dst_idxs = _side_indices(
                    i,
                    offset=31,
                    count=_object_count_for_side(i, side="destination"),
                )
                svc = svc_pool[i % len(svc_pool)]
                act = rule_actions[i]

                for idx in src_idxs:
                    zone, addr = pairs[idx]
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_source,
                            content_type=zone_ct,
                            object_id=zone.pk,
                            exclude=False,
                        )
                    )
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_source,
                            content_type=addr_ct,
                            object_id=addr.pk,
                            exclude=False,
                        )
                    )
                for idx in dst_idxs:
                    zone, addr = pairs[idx]
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_dest,
                            content_type=zone_ct,
                            object_id=zone.pk,
                            exclude=False,
                        )
                    )
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_dest,
                            content_type=addr_ct,
                            object_id=addr.pk,
                            exclude=False,
                        )
                    )
                item_rows.append(
                    RuleObjectItem(
                        rule=rule,
                        field=field_service,
                        content_type=svc_ct,
                        object_id=svc.pk,
                        exclude=False,
                    )
                )
                if netapp_web and netapp_ct and i % 3 == 0:
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_service,
                            content_type=netapp_ct,
                            object_id=netapp_web.pk,
                            exclude=False,
                        )
                    )
                item_rows.append(
                    RuleObjectItem(
                        rule=rule,
                        field=field_action,
                        content_type=act_ct,
                        object_id=act.pk,
                        exclude=False,
                    )
                )
            RuleObjectItem.objects.bulk_create(item_rows, batch_size=BATCH_SIZE)
            items_created += len(item_rows)

    elapsed = time.monotonic() - started
    return {
        "rulebook": rb.name,
        "rulebook_id": rb.pk,
        "pairs": len(pairs),
        "rules": rules_created,
        "object_items": items_created,
        "elapsed_s": round(elapsed, 1),
        "skipped": False,
    }
