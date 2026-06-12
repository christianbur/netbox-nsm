"""Bench scale: nested ``nsm_address`` hosts + policy rules on a COT rulebook.

Creates ``bench-*`` objects (separate from Setup demos). Rules are rows in an
``nsm_rb_*`` Custom Object Type with ``source`` / ``destination``
multiobject fields — not native ``Rulebook`` / ``Rule`` / ``RuleObjectItem``.

Ausführung (netbox-dev)::

    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

Voraussetzungen: Setup → Import all types + Create all TypeConfigs (oder Starter-Demo).
"""

from __future__ import annotations

import random
import time
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ipam.models import IPAddress, Prefix

from netbox_nsm.demos.cot_demo_common import (
    ensure_nsm_prerequisites,
    ensure_rulebook_cot,
    get_cot_model,
)
from netbox_nsm.rulebooks.templates import default_rulebook_schema_yaml

__all__ = (
    "DEFAULT_LEAF_COUNT",
    "DEFAULT_RULE_COUNT",
    "DEFAULT_RULEBOOK_ID",
    "DEFAULT_RULEBOOK_SLUG",
    "HOSTS_PER_SUBNET",
    "REGION_COUNT",
    "SCALE_DEMO_50K_LEAF_COUNT",
    "SCALE_DEMO_50K_RULE_COUNT",
    "SITES_PER_REGION",
    "SUBNET_COUNT",
    "SUBNETS_PER_SITE",
    "create_addresses_million_scale",
    "create_addresses_scale_demo_50k",
    "purge_bench_data",
    "_host_cidr",
    "_leaf_indices",
    "_leaf_name",
    "_subnet_prefix_cidr",
)

# Hierarchy: 20 × 10 × 10 subnets × 100 hosts = 200 000 leaves
REGION_COUNT = 20
SITES_PER_REGION = 10
SUBNETS_PER_SITE = 10
SUBNET_COUNT = REGION_COUNT * SITES_PER_REGION * SUBNETS_PER_SITE
HOSTS_PER_SUBNET = 100

DEFAULT_LEAF_COUNT = SUBNET_COUNT * HOSTS_PER_SUBNET
DEFAULT_RULE_COUNT = 13_000
SCALE_DEMO_50K_LEAF_COUNT = 50_000
SCALE_DEMO_50K_RULE_COUNT = round(
    DEFAULT_RULE_COUNT * SCALE_DEMO_50K_LEAF_COUNT / DEFAULT_LEAF_COUNT
)
DEFAULT_RULEBOOK_SLUG = "nsm_rb_bench_addresses"
DEFAULT_RULEBOOK_ID = None  # legacy CLI default; resolved at runtime to COT pk

RULE_RANDOM_SEED = 42
SERVICE_RANDOM_SEED = 43
ACTION_RANDOM_SEED = 44
ADDR_PICK_MIN = 1
ADDR_PICK_MAX = 20
BATCH_SIZE = 2000

_BENCH_NET_PREFIX = "bench-net-"
_BENCH_IP_PREFIX = "bench-ip-"
_BENCH_RULE_PREFIX = "bench-rule-"

_IP_CT_ID: int | None = None
_PREFIX_CT_ID: int | None = None


def _ip_content_type_id() -> int:
    global _IP_CT_ID
    if _IP_CT_ID is None:
        _IP_CT_ID = ContentType.objects.get_for_model(IPAddress).pk
    return _IP_CT_ID


def _prefix_content_type_id() -> int:
    global _PREFIX_CT_ID
    if _PREFIX_CT_ID is None:
        _PREFIX_CT_ID = ContentType.objects.get_for_model(Prefix).pk
    return _PREFIX_CT_ID


def _address_polymorphic_kwargs(ipam_obj) -> dict[str, int]:
    """Map an IPAM row to polymorphic ``nsm_address.address`` column values."""
    if isinstance(ipam_obj, IPAddress):
        return {
            "address_content_type_id": _ip_content_type_id(),
            "address_object_id": ipam_obj.pk,
        }
    if isinstance(ipam_obj, Prefix):
        return {
            "address_content_type_id": _prefix_content_type_id(),
            "address_object_id": ipam_obj.pk,
        }
    raise TypeError(f"Unsupported nsm_address target: {type(ipam_obj)!r}")


def _subnet_prefix_cidr(subnet_idx: int) -> str:
    """Map subnet index to a contiguous /24 in 10.128.0.0/9."""
    third = subnet_idx // 256
    fourth = subnet_idx % 256
    return f"10.{128 + third}.{fourth}.0/24"


def _host_cidr(subnet_idx: int, host_idx: int) -> str:
    third = subnet_idx // 256
    fourth = subnet_idx % 256
    host_octet = host_idx + 1
    return f"10.{128 + third}.{fourth}.{host_octet}/32"


def _leaf_indices(leaf_idx: int) -> tuple[int, int]:
    return leaf_idx // HOSTS_PER_SUBNET, leaf_idx % HOSTS_PER_SUBNET


def _leaf_name(leaf_idx: int) -> str:
    return f"{_BENCH_IP_PREFIX}{leaf_idx:07d}"


def _subnet_name(subnet_idx: int) -> str:
    return f"{_BENCH_NET_PREFIX}{subnet_idx:05d}"


def _resolve_rulebook_slug(rulebook_id: int | None, rulebook_slug: str | None) -> str:
    if rulebook_slug:
        return rulebook_slug
    if rulebook_id is not None:
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(pk=rulebook_id).first()
        if cot is not None and cot.slug.startswith("nsm_rb_"):
            return cot.slug
    return DEFAULT_RULEBOOK_SLUG


def _load_lookup_map(*slugs: str) -> dict[str, Any]:
    model, _cot = get_cot_model(*slugs)
    return {obj.name.lower(): obj for obj in model.objects.all()}


def _ensure_bench_rulebook(slug: str):
    return ensure_rulebook_cot(
        slug=slug,
        schema_yaml=default_rulebook_schema_yaml(),
        display_name="Bench Addresses",
    )


def _create_subnet_addresses(
    AddrModel,
    *,
    subnet_count: int,
) -> dict[int, Prefix]:
    """Create /24 prefixes and parent ``bench-net-*`` address rows."""
    prefix_by_subnet: dict[int, Prefix] = {}
    for subnet_idx in range(subnet_count):
        cidr = _subnet_prefix_cidr(subnet_idx)
        prefix, _ = Prefix.objects.get_or_create(
            prefix=cidr,
            defaults={"status": "active"},
        )
        prefix_by_subnet[subnet_idx] = prefix
        AddrModel.objects.get_or_create(
            name=_subnet_name(subnet_idx),
            defaults=_address_polymorphic_kwargs(prefix),
        )
    return prefix_by_subnet


def _create_leaf_addresses(
    AddrModel,
    *,
    leaf_count: int,
    prefix_by_subnet: dict[int, Prefix],
) -> list[Any]:
    """Bulk-create host ``bench-ip-*`` rows with linked IPAM /32 objects."""
    leaves: list[Any] = []
    subnet_count = (leaf_count + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET

    for subnet_idx in range(subnet_count):
        hosts_in_subnet = min(
            HOSTS_PER_SUBNET,
            leaf_count - subnet_idx * HOSTS_PER_SUBNET,
        )
        if hosts_in_subnet <= 0:
            break

        ip_objects: list[IPAddress] = []
        for host_idx in range(hosts_in_subnet):
            ip_objects.append(
                IPAddress(address=_host_cidr(subnet_idx, host_idx), status="active")
            )

        for batch_start in range(0, len(ip_objects), BATCH_SIZE):
            ip_batch = ip_objects[batch_start : batch_start + BATCH_SIZE]
            created_ips = IPAddress.objects.bulk_create(ip_batch, batch_size=BATCH_SIZE)

            addr_batch = []
            for offset, ip in enumerate(created_ips):
                host_idx = batch_start + offset
                global_leaf = subnet_idx * HOSTS_PER_SUBNET + host_idx
                addr_batch.append(
                    AddrModel(
                        name=_leaf_name(global_leaf),
                        **_address_polymorphic_kwargs(ip),
                    )
                )
            leaves.extend(
                AddrModel.objects.bulk_create(addr_batch, batch_size=BATCH_SIZE)
            )

    return leaves


def _create_bench_rules(
    rulebook_cot,
    *,
    leaves: list[Any],
    rule_count: int,
    recreate_rules: bool,
) -> tuple[int, int]:
    """Create COT rule rows with multiobject source/destination/service/action."""
    RuleModel = rulebook_cot.get_model()
    if recreate_rules:
        RuleModel.objects.filter(name__startswith=_BENCH_RULE_PREFIX).delete()

    services = list(_load_lookup_map("nsm_service", "nsm_services").values())
    actions = _load_lookup_map("nsm_action")
    if not services:
        raise RuntimeError("No nsm_service objects found — run Setup seed/import first.")
    if not actions:
        raise RuntimeError("No nsm_action objects found — run Setup seed/import first.")

    addr_rng = random.Random(RULE_RANDOM_SEED)
    svc_rng = random.Random(SERVICE_RANDOM_SEED)
    act_rng = random.Random(ACTION_RANDOM_SEED)

    object_items = 0
    for i in range(rule_count):
        index = i + 1
        name = f"{_BENCH_RULE_PREFIX}{i + 1:05d}"
        src_n = addr_rng.randint(ADDR_PICK_MIN, ADDR_PICK_MAX)
        dst_n = addr_rng.randint(ADDR_PICK_MIN, ADDR_PICK_MAX)
        srcs = addr_rng.sample(leaves, min(src_n, len(leaves)))
        dsts = addr_rng.sample(leaves, min(dst_n, len(leaves)))

        rule = RuleModel.objects.create(index=index, status=True, name=name)
        rule.source.set(srcs)
        rule.destination.set(dsts)
        rule.services_applications.set([svc_rng.choice(services)])
        action_key = "permit" if act_rng.random() < 0.5 else "deny"
        action = actions.get(action_key) or next(iter(actions.values()))
        rule.actions.set([action])
        object_items += len(srcs) + len(dsts) + 2

    return rule_count, object_items


def create_addresses_million_scale(
    *,
    rulebook_id: int | None = None,
    rulebook_slug: str | None = None,
    leaf_count: int = DEFAULT_LEAF_COUNT,
    rule_count: int = DEFAULT_RULE_COUNT,
    skip_addresses: bool = False,
    skip_rules: bool = False,
    recreate_rules: bool = True,
) -> dict[str, Any]:
    """Create bench addresses and/or COT policy rules; return summary dict."""
    if leaf_count < 1:
        raise ValueError("leaf_count must be >= 1")
    if rule_count < 0:
        raise ValueError("rule_count must be >= 0")
    if leaf_count > SUBNET_COUNT * HOSTS_PER_SUBNET:
        raise ValueError(
            f"leaf_count exceeds hierarchy maximum ({SUBNET_COUNT * HOSTS_PER_SUBNET:,})"
        )

    slug = _resolve_rulebook_slug(rulebook_id, rulebook_slug)
    t0 = time.perf_counter()

    ensure_nsm_prerequisites()
    rulebook_cot = _ensure_bench_rulebook(slug)

    leaves: list[Any] = []
    with transaction.atomic():
        if not skip_addresses:
            AddrModel, _addr_cot = get_cot_model("nsm_address", "nsm_addresses")
            subnet_count = (leaf_count + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET
            prefix_by_subnet = _create_subnet_addresses(
                AddrModel,
                subnet_count=subnet_count,
            )
            leaves = _create_leaf_addresses(
                AddrModel,
                leaf_count=leaf_count,
                prefix_by_subnet=prefix_by_subnet,
            )
        else:
            AddrModel, _addr_cot = get_cot_model("nsm_address", "nsm_addresses")
            leaves = list(
                AddrModel.objects.filter(name__startswith=_BENCH_IP_PREFIX).order_by(
                    "name"
                )
            )
            if not leaves:
                raise RuntimeError(
                    "No bench-ip-* addresses found; run without --skip-addresses first."
                )

        rules_created = 0
        object_items = 0
        if not skip_rules and rule_count > 0:
            rules_created, object_items = _create_bench_rules(
                rulebook_cot,
                leaves=leaves,
                rule_count=rule_count,
                recreate_rules=recreate_rules,
            )

    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "rulebook": rulebook_cot.verbose_name or rulebook_cot.name,
        "rulebook_slug": rulebook_cot.slug,
        "rulebook_id": rulebook_cot.pk,
        "leaves": len(leaves),
        "rules": rules_created,
        "object_items": object_items,
        "elapsed_s": elapsed,
    }


def create_addresses_scale_demo_50k(*, recreate: bool = True) -> dict[str, Any]:
    """Setup wizard entry: 50k bench addresses + proportional COT rules (RQ-safe)."""
    return create_addresses_million_scale(
        leaf_count=SCALE_DEMO_50K_LEAF_COUNT,
        rule_count=SCALE_DEMO_50K_RULE_COUNT,
        recreate_rules=recreate,
    )


def purge_bench_data(
    *,
    rulebook_id: int | None = None,
    rulebook_slug: str | None = None,
) -> dict[str, Any]:
    """Remove bench-* rules, addresses, and linked IPAM rows."""
    slug = _resolve_rulebook_slug(rulebook_id, rulebook_slug)
    t0 = time.perf_counter()

    rules_deleted = 0
    from netbox_custom_objects.models import CustomObjectType

    rulebook_cot = CustomObjectType.objects.filter(slug=slug).first()
    if rulebook_cot is not None:
        RuleModel = rulebook_cot.get_model()
        rules_deleted, _ = RuleModel.objects.filter(
            name__startswith=_BENCH_RULE_PREFIX
        ).delete()

    AddrModel, _ = get_cot_model("nsm_address", "nsm_addresses")
    ip_ct_id = _ip_content_type_id()
    prefix_ct_id = _prefix_content_type_id()
    host_qs = AddrModel.objects.filter(name__startswith=_BENCH_IP_PREFIX)
    ip_ids = [
        pk
        for pk in host_qs.filter(address_content_type_id=ip_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]
    net_qs = AddrModel.objects.filter(name__startswith=_BENCH_NET_PREFIX)
    prefix_ids = [
        pk
        for pk in net_qs.filter(address_content_type_id=prefix_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]

    addresses_deleted, _ = AddrModel.objects.filter(
        name__startswith="bench-"
    ).delete()

    ip_addresses_deleted = 0
    if ip_ids:
        ip_addresses_deleted, _ = IPAddress.objects.filter(pk__in=ip_ids).delete()

    prefixes_deleted = 0
    if prefix_ids:
        prefixes_deleted, _ = Prefix.objects.filter(pk__in=prefix_ids).delete()

    return {
        "rules_deleted": rules_deleted,
        "addresses_deleted": addresses_deleted,
        "ip_addresses_deleted": ip_addresses_deleted,
        "prefixes_deleted": prefixes_deleted,
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }
