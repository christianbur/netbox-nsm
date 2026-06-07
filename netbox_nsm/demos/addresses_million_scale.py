"""Large-scale bench data: nested nsm_addresses + rules (NOT part of Setup wizard).

Hierarchy (nsm_addresses ``group`` M2M, groups-in-groups):

* 20 regions  ``bench-reg-000`` … ``bench-reg-019``
* 200 sites  ``bench-site-0000`` … (10 sites per region)
* 2 000 subnet groups ``bench-net-00000`` … (10 nets per site, each with a /24 Prefix)
* 200 000 leaf addresses ``bench-ip-0000000`` … (100 hosts per subnet, /32 each)

IP space: ``10.128.0.0/9`` (contiguous /24 blocks).

Run via ``scripts/create_addresses_million_scale.py`` only.
"""

from __future__ import annotations

import random
import time
from typing import Iterable

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ipam.models import IPAddress, Prefix
from netaddr import IPNetwork

from netbox_custom_objects.models import CustomObjectType
from netbox_nsm.models.rulebook import Rule, Rulebook, RuleObjectItem

__all__ = (
    "BENCH_PREFIX",
    "DEFAULT_LEAF_COUNT",
    "DEFAULT_RULEBOOK_ID",
    "DEFAULT_RULE_COUNT",
    "create_addresses_million_scale",
    "purge_bench_data",
)

BENCH_PREFIX = "bench-"
DEFAULT_RULEBOOK_ID = 2
DEFAULT_RULE_COUNT = 13_000
DEFAULT_LEAF_COUNT = 200_000
REGION_COUNT = 20
SITE_COUNT = 200
SUBNET_COUNT = 2_000
HOSTS_PER_SUBNET = 100
BATCH_SIZE = 5_000
ACTION_RANDOM_SEED = 20260612


def _subnet_prefix_cidr(subnet_idx: int) -> str:
    if not 0 <= subnet_idx < SUBNET_COUNT:
        raise ValueError(f"subnet_idx out of range: {subnet_idx}")
    hi = 128 + (subnet_idx // 256)
    lo = subnet_idx % 256
    return f"10.{hi}.{lo}.0/24"


def _host_cidr(subnet_idx: int, host_idx: int) -> str:
    if not 0 <= host_idx < HOSTS_PER_SUBNET:
        raise ValueError(f"host_idx out of range: {host_idx}")
    hi = 128 + (subnet_idx // 256)
    lo = subnet_idx % 256
    return f"10.{hi}.{lo}.{host_idx + 1}/32"


def _region_name(region_idx: int) -> str:
    return f"{BENCH_PREFIX}reg-{region_idx:03d}"


def _site_name(site_idx: int) -> str:
    return f"{BENCH_PREFIX}site-{site_idx:04d}"


def _subnet_group_name(subnet_idx: int) -> str:
    return f"{BENCH_PREFIX}net-{subnet_idx:05d}"


def _leaf_name(leaf_idx: int) -> str:
    return f"{BENCH_PREFIX}ip-{leaf_idx:07d}"


def _leaf_indices(leaf_idx: int) -> tuple[int, int]:
    subnet_idx = leaf_idx // HOSTS_PER_SUBNET
    host_idx = leaf_idx % HOSTS_PER_SUBNET
    return subnet_idx, host_idx


def _get_cot_model(slug: str):
    cot = CustomObjectType.objects.get(slug=slug)
    model = cot.get_model()
    ct = ContentType.objects.get_for_model(model)
    return cot, model, ct


def _lookup_objects_by_name(model) -> dict[str, object]:
    return {obj.name.lower(): obj for obj in model.objects.all()}


def _bulk_link_groups(group_model, links: Iterable[tuple[int, int]]) -> int:
    through = group_model.group.through
    rows = [
        through(source_id=child_id, target_id=parent_id)
        for child_id, parent_id in links
    ]
    if not rows:
        return 0
    through.objects.bulk_create(rows, batch_size=BATCH_SIZE, ignore_conflicts=True)
    return len(rows)


def _existing_bench_leaf_count(addr_model) -> int:
    return addr_model.objects.filter(name__startswith=f"{BENCH_PREFIX}ip-").count()


def purge_bench_data(*, rulebook_id: int = DEFAULT_RULEBOOK_ID) -> dict:
    """Remove bench rules and all ``bench-*`` nsm_addresses (+ linked IPAM where safe)."""
    from netbox_nsm.models.rulebook import Rulebook

    started = time.monotonic()
    _addr_cot, addr_model, _addr_ct = _get_cot_model("nsm_addresses")

    rb = Rulebook.objects.filter(pk=rulebook_id).first()
    rules_deleted = 0
    if rb is not None:
        qs = Rule.objects.filter(rulebook=rb, name__startswith=f"{BENCH_PREFIX}rule-")
        rules_deleted = qs.count()
        qs.delete()

    addrs_deleted, _ = addr_model.objects.filter(name__startswith=BENCH_PREFIX).delete()

    prefixes_deleted, _ = Prefix.objects.filter(
        description__startswith="Bench subnet"
    ).delete()
    ips_deleted, _ = IPAddress.objects.filter(
        description__startswith="Bench bench-ip-"
    ).delete()

    elapsed = time.monotonic() - started
    return {
        "rules_deleted": rules_deleted,
        "addresses_deleted": addrs_deleted,
        "prefixes_deleted": prefixes_deleted,
        "ip_addresses_deleted": ips_deleted,
        "elapsed_s": round(elapsed, 1),
    }


def _ensure_group_containers(addr_model) -> dict[str, list[int]]:
    """Create region / site / subnet container objects; return id lists by level."""
    region_ids: list[int] = []
    for r in range(REGION_COUNT):
        obj, _ = addr_model.objects.get_or_create(
            name=_region_name(r),
            defaults={
                "description": f"Bench region {r} (container)",
                "comments": "bench-hierarchy:region",
            },
        )
        region_ids.append(obj.pk)

    site_ids: list[int] = []
    site_to_region: list[tuple[int, int]] = []
    for s in range(SITE_COUNT):
        obj, _ = addr_model.objects.get_or_create(
            name=_site_name(s),
            defaults={
                "description": f"Bench site {s} (container)",
                "comments": "bench-hierarchy:site",
            },
        )
        site_ids.append(obj.pk)
        site_to_region.append((obj.pk, region_ids[s // 10]))

    subnet_ids: list[int] = []
    net_to_site: list[tuple[int, int]] = []
    prefix_by_subnet: dict[int, Prefix] = {}
    for s in range(SUBNET_COUNT):
        cidr = _subnet_prefix_cidr(s)
        prefix, _ = Prefix.objects.get_or_create(
            prefix=cidr,
            defaults={
                "status": "active",
                "description": f"Bench subnet {s}",
            },
        )
        prefix_by_subnet[s] = prefix
        obj, _ = addr_model.objects.get_or_create(
            name=_subnet_group_name(s),
            defaults={
                "description": f"Bench subnet group {s} ({cidr})",
                "comments": "bench-hierarchy:subnet",
                "prefix": prefix,
            },
        )
        if obj.prefix_id != prefix.pk:
            obj.prefix = prefix
            obj.save(update_fields=["prefix_id"])
        subnet_ids.append(obj.pk)
        net_to_site.append((obj.pk, site_ids[s // 10]))

    _bulk_link_groups(addr_model, site_to_region)
    _bulk_link_groups(addr_model, net_to_site)

    return {
        "region_ids": region_ids,
        "site_ids": site_ids,
        "subnet_ids": subnet_ids,
        "prefix_by_subnet": prefix_by_subnet,
    }


def _ensure_leaf_addresses(
    addr_model,
    *,
    leaf_count: int,
    subnet_ids: list[int],
    prefix_by_subnet: dict[int, Prefix],
) -> list[int]:
    """Bulk-create leaf nsm_addresses with IPAM + link to subnet group."""
    existing = _existing_bench_leaf_count(addr_model)
    if existing >= leaf_count:
        print(f"  leaves: already {existing:,} >= {leaf_count:,}, skipping create")
        return _compact_leaf_pks(addr_model, leaf_count)

    ip_cache: dict[str, IPAddress] = {}
    group_links: list[tuple[int, int]] = []
    created = 0
    leaf_pks: list[int | None] = [None] * leaf_count

    for batch_start in range(0, leaf_count, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, leaf_count)
        with transaction.atomic():
            ip_rows = []
            ip_meta: list[tuple[int, int, str]] = []
            for leaf_idx in range(batch_start, batch_end):
                leaf_name = _leaf_name(leaf_idx)
                existing = addr_model.objects.filter(name=leaf_name).first()
                if existing is not None:
                    leaf_pks[leaf_idx] = existing.pk
                    continue
                subnet_idx, host_idx = _leaf_indices(leaf_idx)
                cidr = _host_cidr(subnet_idx, host_idx)
                ip_meta.append((leaf_idx, subnet_idx, cidr))
                if cidr not in ip_cache:
                    ip_rows.append(
                        IPAddress(
                            address=cidr,
                            status="active",
                            description=f"Bench {leaf_name} ({cidr})",
                        )
                    )

            if ip_rows:
                IPAddress.objects.bulk_create(ip_rows, batch_size=BATCH_SIZE)
                for ip in IPAddress.objects.filter(address__in=[m[2] for m in ip_meta]):
                    ip_cache[str(ip.address)] = ip

            addr_rows = []
            row_meta: list[tuple[int, int]] = []
            for leaf_idx, subnet_idx, cidr in ip_meta:
                ip_obj = ip_cache.get(cidr)
                if ip_obj is None:
                    ip_obj = IPAddress.objects.get(address=cidr)
                    ip_cache[cidr] = ip_obj
                prefix = prefix_by_subnet[subnet_idx]
                addr_rows.append(
                    addr_model(
                        name=_leaf_name(leaf_idx),
                        description=f"Bench {leaf_name} ({cidr})",
                        comments="bench-hierarchy:leaf",
                        ip_address=ip_obj,
                        prefix=prefix,
                    )
                )
                row_meta.append((leaf_idx, subnet_ids[subnet_idx]))

            if addr_rows:
                created_objs = addr_model.objects.bulk_create(
                    addr_rows, batch_size=BATCH_SIZE
                )
                created += len(created_objs)
                for (leaf_idx, subnet_group_id), obj in zip(row_meta, created_objs):
                    leaf_pks[leaf_idx] = obj.pk
                    group_links.append((obj.pk, subnet_group_id))

        if (batch_end % 50_000 == 0) or batch_end == leaf_count:
            print(
                f"  leaves: {batch_end:,} / {leaf_count:,} processed ({created:,} new)"
            )

    if group_links:
        for link_start in range(0, len(group_links), BATCH_SIZE):
            chunk = group_links[link_start : link_start + BATCH_SIZE]
            _bulk_link_groups(addr_model, chunk)

    return _compact_leaf_pks(addr_model, leaf_count)


def _compact_leaf_pks(addr_model, leaf_count: int) -> list[int]:
    pk_map = {
        int(name.rsplit("-", 1)[-1]): pk
        for pk, name in addr_model.objects.filter(
            name__startswith=f"{BENCH_PREFIX}ip-"
        ).values_list("pk", "name")
    }
    missing = [i for i in range(leaf_count) if i not in pk_map]
    if missing:
        raise RuntimeError(
            f"Missing {len(missing)} bench leaf addresses (first gap: {missing[0]})"
        )
    return [pk_map[i] for i in range(leaf_count)]


def _rulebook_fields(rulebook_id: int) -> dict:
    rb = Rulebook.objects.get(pk=rulebook_id)
    fields = {
        f.slug: f
        for f in rb.fields.filter(
            slug__in=("source", "destination", "service", "action")
        )
    }
    missing = [
        slug
        for slug in ("source", "destination", "service", "action")
        if slug not in fields
    ]
    if missing:
        raise RuntimeError(
            f"Rulebook {rulebook_id} ({rb.name}) missing fields: {', '.join(missing)}"
        )
    return {"rulebook": rb, **fields}


def _pick_object_pks(rng: random.Random, pool: list[int], count: int) -> list[int]:
    count = max(1, min(int(count), 20, len(pool)))
    if count >= len(pool):
        return list(pool)
    return rng.sample(pool, count)


def _ensure_rules(
    rb: Rulebook,
    fields: dict,
    addr_ct: ContentType,
    leaf_pks: list[int],
    *,
    rule_count: int,
    recreate: bool,
) -> tuple[int, int]:
    _svc_cot, svc_model, svc_ct = _get_cot_model("nsm_services")
    _act_cot, act_model, act_ct = _get_cot_model("nsm_action")

    services = _lookup_objects_by_name(svc_model)
    actions = _lookup_objects_by_name(act_model)
    svc_pool = [
        services[k] for k in ("https", "ssh", "dns-udp", "http") if k in services
    ]
    if not svc_pool:
        svc_pool = list(services.values())[:5]
    act_permit = actions.get("permit")
    act_deny = actions.get("deny")
    if not svc_pool or not act_permit or not act_deny:
        raise RuntimeError("Missing default Services/Action COT objects.")

    if recreate:
        Rule.objects.filter(
            rulebook=rb, name__startswith=f"{BENCH_PREFIX}rule-"
        ).delete()

    existing = Rule.objects.filter(
        rulebook=rb, name__startswith=f"{BENCH_PREFIX}rule-"
    ).count()
    if existing >= rule_count:
        print(f"  rules: already {existing:,} >= {rule_count:,}, skipping create")
        return 0, RuleObjectItem.objects.filter(rule__rulebook=rb).count()

    field_source = fields["source"]
    field_dest = fields["destination"]
    field_service = fields["service"]
    field_action = fields["action"]

    rng = random.Random(ACTION_RANDOM_SEED)
    rules_created = 0
    items_created = 0

    for batch_start in range(0, rule_count, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, rule_count)
        with transaction.atomic():
            rule_rows = []
            meta: list[tuple[int, int, int]] = []
            for i in range(batch_start, batch_end):
                src_n = rng.randint(1, 20)
                dst_n = rng.randint(1, 20)
                meta.append((i, src_n, dst_n))
                rule_rows.append(
                    Rule(
                        rulebook=rb,
                        name=f"{BENCH_PREFIX}rule-{i + 1:05d}",
                        index=(i + 1) * 10,
                        enabled=True,
                        description=f"Bench rule src×{src_n} dst×{dst_n}",
                    )
                )
            Rule.objects.bulk_create(rule_rows, batch_size=BATCH_SIZE)
            rules_created += len(rule_rows)

            created_rules = list(
                Rule.objects.filter(
                    rulebook=rb,
                    name__gte=f"{BENCH_PREFIX}rule-{batch_start + 1:05d}",
                    name__lte=f"{BENCH_PREFIX}rule-{batch_end:05d}",
                ).order_by("index")
            )

            item_rows = []
            for rule, (i, src_n, dst_n) in zip(created_rules, meta):
                rule_rng = random.Random(ACTION_RANDOM_SEED + i)
                src_pks = _pick_object_pks(rule_rng, leaf_pks, src_n)
                dst_pks = _pick_object_pks(
                    random.Random(ACTION_RANDOM_SEED + i + 100_000), leaf_pks, dst_n
                )
                svc = svc_pool[i % len(svc_pool)]
                act = act_permit if rule_rng.random() < 0.55 else act_deny

                for pk in src_pks:
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_source,
                            content_type=addr_ct,
                            object_id=pk,
                            exclude=False,
                        )
                    )
                for pk in dst_pks:
                    item_rows.append(
                        RuleObjectItem(
                            rule=rule,
                            field=field_dest,
                            content_type=addr_ct,
                            object_id=pk,
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

        print(f"  rules: {batch_end:,} / {rule_count:,}")

    return rules_created, items_created


def create_addresses_million_scale(
    *,
    rulebook_id: int = DEFAULT_RULEBOOK_ID,
    leaf_count: int = DEFAULT_LEAF_COUNT,
    rule_count: int = DEFAULT_RULE_COUNT,
    skip_addresses: bool = False,
    skip_rules: bool = False,
    recreate_rules: bool = True,
) -> dict:
    """
    Populate nested ``nsm_addresses`` bench data and policy rules on an existing rulebook.

    Does not touch Setup wizard or demo imports.
    """
    if leaf_count > SUBNET_COUNT * HOSTS_PER_SUBNET:
        raise ValueError(
            f"leaf_count {leaf_count} exceeds capacity "
            f"{SUBNET_COUNT * HOSTS_PER_SUBNET}"
        )

    started = time.monotonic()
    _addr_cot, addr_model, addr_ct = _get_cot_model("nsm_addresses")
    field_bundle = _rulebook_fields(rulebook_id)
    rb = field_bundle["rulebook"]

    hierarchy = None
    leaf_pks: list[int] = []

    if not skip_addresses:
        print("Phase 1/2: group containers + IPAM + leaf addresses …")
        t0 = time.monotonic()
        hierarchy = _ensure_group_containers(addr_model)
        leaf_pks = _ensure_leaf_addresses(
            addr_model,
            leaf_count=leaf_count,
            subnet_ids=hierarchy["subnet_ids"],
            prefix_by_subnet=hierarchy["prefix_by_subnet"],
        )
        print(
            f"  addresses done in {time.monotonic() - t0:.1f}s "
            f"({len(leaf_pks):,} leaves)"
        )
    else:
        leaf_pks = _compact_leaf_pks(addr_model, leaf_count)

    rules_created = 0
    items_created = 0
    if not skip_rules:
        print("Phase 2/2: policy rules …")
        t1 = time.monotonic()
        rules_created, items_created = _ensure_rules(
            rb,
            field_bundle,
            addr_ct,
            leaf_pks,
            rule_count=rule_count,
            recreate=recreate_rules,
        )
        print(f"  rules done in {time.monotonic() - t1:.1f}s")

    elapsed = time.monotonic() - started
    return {
        "rulebook": rb.name,
        "rulebook_id": rb.pk,
        "regions": REGION_COUNT,
        "sites": SITE_COUNT,
        "subnets": SUBNET_COUNT,
        "leaves": len(leaf_pks),
        "rules": rules_created,
        "object_items": items_created,
        "elapsed_s": round(elapsed, 1),
    }
