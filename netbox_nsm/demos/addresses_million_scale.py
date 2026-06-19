"""Bench scale: nested ``nsm_address`` hosts + policy rules on a COT rulebook.

Creates ``bench-*`` objects (separate from Setup demos). Rules are rows in an
``nsm_rb_*`` Custom Object Type with ``source_zones`` / ``destination_zones``
and ``source_addresses`` / ``destination_addresses`` multiobject fields — not
native ``Rulebook`` / ``Rule`` / ``RuleObjectItem``.

Ausführung (netbox-dev)::

    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

Nach Änderungen an der Regel-Generierung zuerst ``--purge`` und neu erzeugen::

    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py --purge
    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

**Overlap-Demos:** Regeln 1–20 sind fest verdrahtete Overlap-Showcases — **beide**
Seiten (``source_addresses`` und ``destination_addresses``) mit je 1–10 Objekten
(Adressen und/oder Adressgruppen), jeweils mit Overlap-Sets (/32+/24, /16+/24,
/16+/32, canonical+alias+dup, Gruppe+Mitglieder). IPA auf Regel 1 öffnen.
Für die betroffenen ``bench-ip-*`` Leaf-Indizes legt der Generator zusätzlich
``bench-host-*`` / ``bench-iface-*`` (VirtualMachine + VMInterface) an und weist
die bestehenden ``/32``-IPAM-Adressen dem Interface zu — ``nsm_address`` bleibt
über die polymorphe ``address``-GFK mit derselben ``IPAddress`` verknüpft.

Voraussetzungen: Setup → Import all types + Create all TypeConfigs (oder Starter-Demo).
"""

from __future__ import annotations

import random
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from ipam.models import IPAddress, Prefix

from netbox_nsm.demos.cot_demo_common import (
    ensure_nsm_prerequisites,
    ensure_rulebook_cot,
    get_cot_field_through_model,
    get_cot_model,
    resolve_rulebook_address_field_names,
    resolve_rulebook_zone_field_names,
)
from netbox_nsm.rulebooks.templates import bench_rulebook_schema_yaml

__all__ = (
    "ADDR_PICK_MAX",
    "ADDR_PICK_MIN",
    "ALIAS_STRIDE",
    "BENCH_ZONE_COUNT",
    "DEFAULT_LEAF_COUNT",
    "DEFAULT_RULE_COUNT",
    "DEFAULT_RULEBOOK_ID",
    "DEFAULT_RULEBOOK_SLUG",
    "GROUP_PICK_MAX",
    "GROUP_PICK_MIN",
    "HOSTS_PER_SUBNET",
    "OVERLAP_ALIAS_STRIDE",
    "OVERLAP_BUCKET_RATIO",
    "BENCH_OVERLAP_SHOWCASE_RULE_COUNT",
    "SHOWCASE_CELL_ITEM_MIN",
    "SHOWCASE_CELL_ITEM_MAX",
    "OVERLAP_BUCKET_PICK_PROBABILITY",
    "OVERLAP_DEMO_LEAF_IDX",
    "OVERLAP_DEMO_RULE_COUNT",
    "OVERLAP_DUP_NAME_STRIDE",
    "OVERLAP_LEAVES_PER_GROUP",
    "SHOWCASE_ADDR_PICK_MAX",
    "SHOWCASE_ADDR_PICK_MIN",
    "SHOWCASE_GROUP_PICK_MAX",
    "SHOWCASE_GROUP_PICK_MIN",
    "overlap_demo_rule_descriptions",
    "PREFIX_LEN_SUPER",
    "PREFIX_LEN_WIDE",
    "REGION_COUNT",
    "SCALE_DEMO_50K_LEAF_COUNT",
    "SCALE_DEMO_50K_RULE_COUNT",
    "SITES_PER_REGION",
    "SUBNET_COUNT",
    "SUBNETS_PER_SITE",
    "SUBNETS_PER_SUPER",
    "SUBNETS_PER_WIDE",
    "create_addresses_million_scale",
    "create_addresses_scale_demo_50k",
    "purge_bench_data",
    "_address_polymorphic_kwargs",
    "_alias_comments",
    "_alias_name",
    "_alias_stride_for_leaf",
    "_bench_host_name",
    "_bench_iface_name",
    "_bench_zone_name",
    "_dup_name",
    "_group_name",
    "_grp_ovlp_name",
    "_host_cidr",
    "_leaf_indices",
    "_leaf_in_overlap_bucket",
    "_leaf_name",
    "_overlap_bucket_leaf_count",
    "_overlap_bucket_subnet_count",
    "_build_bench_address_lookups",
    "_showcase_bench_leaf_indices",
    "_showcase_host_leaf_for_side",
    "_showcase_leaf_for_side_alias_dup",
    "_overlap_demo_cell_selection",
    "_pick_regular_addresses",
    "_pick_counts",
    "_subnet_prefix_cidr",
    "_super_name",
    "_wide_name",
    "_wider_prefix_cidr",
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
BENCH_ZONE_COUNT = 50

RULE_RANDOM_SEED = 42
SERVICE_RANDOM_SEED = 43
ACTION_RANDOM_SEED = 44
GROUP_RANDOM_SEED = 45
ZONE_RANDOM_SEED = 46
ADDR_PICK_MIN = 1
ADDR_PICK_MAX = 8
GROUP_PICK_MIN = 1
GROUP_PICK_MAX = 5
SHOWCASE_ADDR_PICK_MIN = 1
SHOWCASE_ADDR_PICK_MAX = 10
SHOWCASE_GROUP_PICK_MIN = 1
SHOWCASE_GROUP_PICK_MAX = 10
SHOWCASE_COUNT_SEED = 47
_SHOWCASE_ALIAS_DUP_STRIDE = 12
ALIAS_STRIDE = 8
OVERLAP_BUCKET_RATIO = 0.075
OVERLAP_ALIAS_STRIDE = 4
OVERLAP_DUP_NAME_STRIDE = 6
OVERLAP_LEAVES_PER_GROUP = 5
BENCH_OVERLAP_SHOWCASE_RULE_COUNT = 20
SHOWCASE_CELL_ITEM_MIN = 1
SHOWCASE_CELL_ITEM_MAX = 10
OVERLAP_DEMO_RULE_COUNT = BENCH_OVERLAP_SHOWCASE_RULE_COUNT
OVERLAP_DEMO_LEAF_IDX = 0
OVERLAP_BUCKET_PICK_PROBABILITY = 0.55
PREFIX_LEN_WIDE = 20
PREFIX_LEN_SUPER = 16
SUBNETS_PER_WIDE = 16
SUBNETS_PER_SUPER = 256
BATCH_SIZE = 2000
RULE_BATCH_SIZE = 1000

_BENCH_NET_PREFIX = "bench-net-"
_BENCH_NET_WIDE_PREFIX = "bench-net-wide-"
_BENCH_NET_SUPER_PREFIX = "bench-net-super-"
_BENCH_IP_PREFIX = "bench-ip-"
_BENCH_ALIAS_PREFIX = "bench-alias-"
_BENCH_DUP_PREFIX = "bench-dup-"
_BENCH_GRP_PREFIX = "bench-grp-"
_BENCH_GRP_OVLP_PREFIX = "bench-grp-ovlp-"
_BENCH_ZONE_PREFIX = "bench-zone-"
_BENCH_RULE_PREFIX = "bench-rule-"
_BENCH_HOST_PREFIX = "bench-host-"
_BENCH_IFACE_PREFIX = "bench-iface-"
_BENCH_SITE_NAME = "bench-site"
_BENCH_SITE_SLUG = "bench-site"
_BENCH_CLUSTER_TYPE_SLUG = "bench-cluster-type"
_BENCH_CLUSTER_NAME = "bench-cluster"
_STARTER_ZONE_PREFIX = "zone_"

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


def _wider_prefix_cidr(block_subnet_idx: int, prefix_len: int) -> str:
    """Map block start subnet index to a /20 or /16 in 10.128.0.0/9."""
    third = block_subnet_idx // 256
    fourth = block_subnet_idx % 256
    return f"10.{128 + third}.{fourth}.0/{prefix_len}"


def _overlap_bucket_leaf_count(leaf_count: int) -> int:
    """Dedicated overlap subset (~7.5% of hosts) for duplicate/overlap tests."""
    if leaf_count < 1:
        return 0
    return max(1, round(leaf_count * OVERLAP_BUCKET_RATIO))


def _overlap_bucket_subnet_count(leaf_count: int) -> int:
    overlap_leaves = _overlap_bucket_leaf_count(leaf_count)
    return (overlap_leaves + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET


def _leaf_in_overlap_bucket(global_leaf: int, overlap_leaf_limit: int) -> bool:
    return global_leaf < overlap_leaf_limit


def _alias_stride_for_leaf(global_leaf: int, overlap_leaf_limit: int) -> int:
    if _leaf_in_overlap_bucket(global_leaf, overlap_leaf_limit):
        return OVERLAP_ALIAS_STRIDE
    return ALIAS_STRIDE


def _host_cidr(subnet_idx: int, host_idx: int) -> str:
    third = subnet_idx // 256
    fourth = subnet_idx % 256
    host_octet = host_idx + 1
    return f"10.{128 + third}.{fourth}.{host_octet}/32"


def _leaf_indices(leaf_idx: int) -> tuple[int, int]:
    return leaf_idx // HOSTS_PER_SUBNET, leaf_idx % HOSTS_PER_SUBNET


def _leaf_name(leaf_idx: int) -> str:
    return f"{_BENCH_IP_PREFIX}{leaf_idx:07d}"


def _bench_host_name(leaf_idx: int) -> str:
    return f"{_BENCH_HOST_PREFIX}{leaf_idx:07d}"


def _bench_iface_name(leaf_idx: int) -> str:
    return f"{_BENCH_IFACE_PREFIX}{leaf_idx:07d}"


def _subnet_name(subnet_idx: int) -> str:
    return f"{_BENCH_NET_PREFIX}{subnet_idx:05d}"


def _wide_name(wide_idx: int) -> str:
    return f"{_BENCH_NET_WIDE_PREFIX}{wide_idx:05d}"


def _super_name(super_idx: int) -> str:
    return f"{_BENCH_NET_SUPER_PREFIX}{super_idx:05d}"


def _alias_name(leaf_idx: int) -> str:
    return f"{_BENCH_ALIAS_PREFIX}{leaf_idx:07d}"


def _dup_name(leaf_idx: int) -> str:
    return f"{_BENCH_DUP_PREFIX}{leaf_idx:07d}"


def _alias_comments(canonical_name: str, network: str) -> str:
    """Shared logical name + network literal (COT ``name`` stays unique)."""
    return f"bench_canonical={canonical_name}; network={network}"


def _group_name(subnet_idx: int) -> str:
    return f"{_BENCH_GRP_PREFIX}{subnet_idx:05d}"


def _grp_ovlp_name(pair_idx: int) -> str:
    return f"{_BENCH_GRP_OVLP_PREFIX}{pair_idx:05d}"


def _bench_zone_name(zone_idx: int) -> str:
    return f"{_BENCH_ZONE_PREFIX}{zone_idx + 1:03d}"


def _bench_net_address_queryset(AddrModel):
    """``bench-net-*`` /24 rows only (exclude wide/super parent prefixes)."""
    return (
        AddrModel.objects.filter(name__startswith=_BENCH_NET_PREFIX)
        .exclude(name__startswith=_BENCH_NET_WIDE_PREFIX)
        .exclude(name__startswith=_BENCH_NET_SUPER_PREFIX)
    )


def _bench_subnet_group_queryset(GroupModel):
    """Per-subnet ``bench-grp-*`` rows (exclude ``bench-grp-ovlp-*``)."""
    return (
        GroupModel.objects.filter(name__startswith=_BENCH_GRP_PREFIX)
        .exclude(name__startswith=_BENCH_GRP_OVLP_PREFIX)
    )


def _pick_counts(rng: random.Random, *, pool_size: int, min_n: int, max_n: int) -> int:
    if pool_size <= 0:
        return 0
    upper = min(max_n, pool_size)
    lower = min(min_n, upper)
    return rng.randint(lower, upper)


@dataclass(frozen=True)
class _BenchAddressLookups:
    """Name-indexed bench objects for overlap-demo rule co-selection."""

    leaf_by_idx: dict[int, Any]
    alias_by_leaf: dict[int, Any]
    dup_by_leaf: dict[int, Any]
    net_by_subnet: dict[int, Any]
    wide_by_idx: dict[int, Any]
    super_by_idx: dict[int, Any]
    subnet_group_by_subnet: dict[int, Any]
    overlap_group_by_pair: dict[int, Any]
    overlap_leaf_limit: int


def _build_bench_address_lookups(
    leaves: list[Any],
    aliases: list[Any],
    dup_names: list[Any],
    net_addrs: list[Any],
    wide_addrs: list[Any],
    super_addrs: list[Any],
    groups: list[Any],
    overlap_groups: list[Any],
    *,
    overlap_leaf_limit: int,
) -> _BenchAddressLookups:
    leaf_by_idx = {
        int(obj.name.removeprefix(_BENCH_IP_PREFIX)): obj for obj in leaves
    }
    alias_by_leaf = {
        int(obj.name.removeprefix(_BENCH_ALIAS_PREFIX)): obj for obj in aliases
    }
    dup_by_leaf = {
        int(obj.name.removeprefix(_BENCH_DUP_PREFIX)): obj for obj in dup_names
    }
    net_by_subnet = {
        int(obj.name.removeprefix(_BENCH_NET_PREFIX)): obj for obj in net_addrs
    }
    wide_by_idx = {
        int(obj.name.removeprefix(_BENCH_NET_WIDE_PREFIX)): obj for obj in wide_addrs
    }
    super_by_idx = {
        int(obj.name.removeprefix(_BENCH_NET_SUPER_PREFIX)): obj for obj in super_addrs
    }
    subnet_group_by_subnet = {
        int(obj.name.removeprefix(_BENCH_GRP_PREFIX)): obj
        for obj in groups
        if not obj.name.startswith(_BENCH_GRP_OVLP_PREFIX)
    }
    overlap_group_by_pair = {
        int(obj.name.removeprefix(_BENCH_GRP_OVLP_PREFIX)): obj
        for obj in overlap_groups
    }
    return _BenchAddressLookups(
        leaf_by_idx=leaf_by_idx,
        alias_by_leaf=alias_by_leaf,
        dup_by_leaf=dup_by_leaf,
        net_by_subnet=net_by_subnet,
        wide_by_idx=wide_by_idx,
        super_by_idx=super_by_idx,
        subnet_group_by_subnet=subnet_group_by_subnet,
        overlap_group_by_pair=overlap_group_by_pair,
        overlap_leaf_limit=overlap_leaf_limit,
    )


def _dedupe_objects(objects: list[Any]) -> list[Any]:
    seen: set[int] = set()
    unique: list[Any] = []
    for obj in objects:
        if obj is None:
            continue
        if obj.pk in seen:
            continue
        seen.add(obj.pk)
        unique.append(obj)
    return unique


def _showcase_leaf_with_alias_and_dup(
    rule_index: int,
    *,
    overlap_leaf_limit: int,
) -> int:
    """Leaf index where alias (stride 4) and dup (stride 6) both exist in overlap bucket."""
    return ((rule_index - 1) * 12) % max(1, overlap_leaf_limit)


def _showcase_host_leaf(rule_index: int, *, overlap_leaf_limit: int) -> int:
    """Distinct overlap-bucket hosts for prefix-containment demos (rules 6–10)."""
    return ((rule_index - 6) * 100) % max(1, overlap_leaf_limit)


def _showcase_cell_counts(rule_index: int) -> tuple[int, int, int, int]:
    """Deterministic per-rule counts: src/dst addresses and groups (each 1–10)."""
    rng = random.Random(SHOWCASE_COUNT_SEED + rule_index * 997)
    return (
        rng.randint(SHOWCASE_ADDR_PICK_MIN, SHOWCASE_ADDR_PICK_MAX),
        rng.randint(SHOWCASE_ADDR_PICK_MIN, SHOWCASE_ADDR_PICK_MAX),
        rng.randint(SHOWCASE_GROUP_PICK_MIN, SHOWCASE_GROUP_PICK_MAX),
        rng.randint(SHOWCASE_GROUP_PICK_MIN, SHOWCASE_GROUP_PICK_MAX),
    )


def _showcase_leaf_for_side_alias_dup(
    rule_index: int,
    side: str,
    overlap_leaf_limit: int,
) -> int:
    """Leaf with alias + dup peers; src/dst use distinct indices when possible."""
    stride = _SHOWCASE_ALIAS_DUP_STRIDE
    limit = max(1, overlap_leaf_limit)
    base = ((rule_index - 1) * stride) % limit
    if side == "dst":
        offset = max(stride, (limit // 2 // stride) * stride)
        base = (base + offset) % limit
    return (base // stride) * stride


def _showcase_host_leaf_for_side(
    rule_index: int,
    side: str,
    overlap_leaf_limit: int,
) -> int:
    base = _showcase_host_leaf(rule_index, overlap_leaf_limit=overlap_leaf_limit)
    if side == "dst":
        base = (base + max(1, overlap_leaf_limit // 4)) % max(1, overlap_leaf_limit)
    return base


def _overlap_subnet_count_from_limit(overlap_leaf_limit: int) -> int:
    if overlap_leaf_limit < 1:
        return 0
    return (overlap_leaf_limit + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET


def _showcase_max_pair_idx(
    lookups: _BenchAddressLookups,
    *,
    overlap_leaf_limit: int,
) -> int:
    if lookups.overlap_group_by_pair:
        return max(lookups.overlap_group_by_pair)
    return max(0, _overlap_subnet_count_from_limit(overlap_leaf_limit) - 2)


def _showcase_pair_idx_for_side(
    rule_index: int,
    side: str,
    lookups: _BenchAddressLookups,
) -> int:
    max_pair = _showcase_max_pair_idx(
        lookups, overlap_leaf_limit=lookups.overlap_leaf_limit
    )
    pair_idx = (rule_index - 11) % max(1, max_pair + 1)
    if side == "dst":
        pair_idx = (pair_idx + max(1, (max_pair + 1) // 2)) % max(1, max_pair + 1)
    return pair_idx


def _showcase_subnet_idx_for_side(
    rule_index: int,
    side: str,
    *,
    max_subnet: int,
) -> int:
    subnet_idx = (rule_index - 16) % max(1, max_subnet + 1)
    if side == "dst":
        subnet_idx = (subnet_idx + max(1, (max_subnet + 1) // 2)) % max(1, max_subnet + 1)
    return subnet_idx


def _showcase_group_padding_pool(lookups: _BenchAddressLookups) -> list[Any]:
    groups = list(lookups.subnet_group_by_subnet.values())
    groups.extend(lookups.overlap_group_by_pair.values())
    return sorted(groups, key=lambda obj: obj.name)


def _pad_showcase_cell(
    core: list[Any],
    pool: list[Any],
    target: int,
    *,
    rule_index: int,
    slot: int,
    max_items: int,
) -> list[Any]:
    """Pad overlap ``core`` toward ``target``; never trim below ``core`` size."""
    result = _dedupe_objects([obj for obj in core if obj is not None])
    floor = len(result)
    if floor:
        target = max(target, floor)
    target = min(max(target, 1), max_items)
    if target <= 0:
        return []
    if len(result) >= target:
        return result[:target]
    seen = {obj.pk for obj in result}
    extras = [obj for obj in pool if obj is not None and obj.pk not in seen]
    rng = random.Random(SHOWCASE_COUNT_SEED + rule_index * 131 + slot)
    rng.shuffle(extras)
    for obj in extras:
        if len(result) >= target:
            break
        result.append(obj)
    return result[:target] if len(result) >= target else result


def _showcase_bench_leaf_indices(*, overlap_leaf_limit: int) -> list[int]:
    """Leaf indices that need ``bench-host-*`` / ``bench-iface-*`` for rules 1–20."""
    if overlap_leaf_limit < 1:
        return []

    indices: set[int] = set()
    overlap_subnet_count = _overlap_subnet_count_from_limit(overlap_leaf_limit)
    max_subnet = max(0, overlap_subnet_count - 1)
    max_pair = max(0, overlap_subnet_count - 2)

    for rule_index in range(1, 6):
        for side in ("src", "dst"):
            indices.add(
                _showcase_leaf_for_side_alias_dup(
                    rule_index, side, overlap_leaf_limit
                )
            )
    for rule_index in range(6, 11):
        for side in ("src", "dst"):
            indices.add(
                _showcase_host_leaf_for_side(rule_index, side, overlap_leaf_limit)
            )
    for rule_index in range(11, 16):
        for side in ("src", "dst"):
            pair_idx = (rule_index - 11) % max(1, max_pair + 1)
            if side == "dst":
                pair_idx = (pair_idx + max(1, (max_pair + 1) // 2)) % max(
                    1, max_pair + 1
                )
            for subnet_idx in (pair_idx, pair_idx + 1):
                indices.add(subnet_idx * HOSTS_PER_SUBNET)
    for rule_index in range(16, 21):
        for side in ("src", "dst"):
            subnet_idx = _showcase_subnet_idx_for_side(
                rule_index,
                side,
                max_subnet=max_subnet,
            )
            indices.add(subnet_idx * HOSTS_PER_SUBNET)
    return sorted(indices)


def _overlap_demo_objects(
    lookups: _BenchAddressLookups,
    *,
    leaf_idx: int = OVERLAP_DEMO_LEAF_IDX,
) -> dict[str, Any | None]:
    subnet_idx, _host_idx = _leaf_indices(leaf_idx)
    wide_idx = subnet_idx // SUBNETS_PER_WIDE
    super_idx = subnet_idx // SUBNETS_PER_SUPER
    return {
        "canonical": lookups.leaf_by_idx.get(leaf_idx),
        "alias": lookups.alias_by_leaf.get(leaf_idx),
        "dup": lookups.dup_by_leaf.get(leaf_idx),
        "net24": lookups.net_by_subnet.get(subnet_idx),
        "net20": lookups.wide_by_idx.get(wide_idx),
        "net16": lookups.super_by_idx.get(super_idx),
        "subnet_group": lookups.subnet_group_by_subnet.get(subnet_idx),
        "overlap_group": lookups.overlap_group_by_pair.get(subnet_idx),
        "subnet_idx": subnet_idx,
        "wide_idx": wide_idx,
        "super_idx": super_idx,
    }


def _canonical_alias_dup_cell(
    lookups: _BenchAddressLookups,
    leaf_idx: int,
) -> list[Any]:
    objs = _overlap_demo_objects(lookups, leaf_idx=leaf_idx)
    return _dedupe_objects(
        [objs["canonical"], objs["alias"], objs["dup"], objs["net24"]]
    )


def _host_prefix_cell(
    lookups: _BenchAddressLookups,
    leaf_idx: int,
    *,
    include_wider: bool,
) -> list[Any]:
    objs = _overlap_demo_objects(lookups, leaf_idx=leaf_idx)
    parts = [objs["canonical"], objs["net24"]]
    if include_wider:
        parts.extend([objs["net20"], objs["net16"]])
    return _dedupe_objects(parts)


def _overlap_group_member_cell(
    lookups: _BenchAddressLookups,
    pair_idx: int,
) -> tuple[list[Any], list[Any]]:
    """Co-select overlap group plus member addresses in the same side."""
    ovlp_grp = lookups.overlap_group_by_pair.get(pair_idx)
    if ovlp_grp is None:
        return [], []

    members: list[Any] = []
    for subnet_idx in (pair_idx, pair_idx + 1):
        net = lookups.net_by_subnet.get(subnet_idx)
        if net is not None:
            members.append(net)
        first_leaf = lookups.leaf_by_idx.get(subnet_idx * HOSTS_PER_SUBNET)
        if first_leaf is not None:
            members.append(first_leaf)
    return _dedupe_objects(members), [ovlp_grp]


def _subnet_only_cell(
    lookups: _BenchAddressLookups,
    subnet_idx: int,
    *,
    pattern: str,
) -> list[Any]:
    wide_idx = subnet_idx // SUBNETS_PER_WIDE
    super_idx = subnet_idx // SUBNETS_PER_SUPER
    net24 = lookups.net_by_subnet.get(subnet_idx)
    net20 = lookups.wide_by_idx.get(wide_idx)
    net16 = lookups.super_by_idx.get(super_idx)
    if pattern == "all":
        return _dedupe_objects([net24, net20, net16])
    if pattern == "24_20":
        return _dedupe_objects([net24, net20])
    if pattern == "20_16":
        return _dedupe_objects([net20, net16])
    if pattern == "24_16":
        return _dedupe_objects([net24, net16])
    return _dedupe_objects([net24])


def _subnet_overlap_bundle(
    lookups: _BenchAddressLookups,
    subnet_idx: int,
    *,
    pattern: str,
) -> list[Any]:
    """Prefix pattern plus a /32 host member for overlap demos (rules 16–20)."""
    host = lookups.leaf_by_idx.get(subnet_idx * HOSTS_PER_SUBNET)
    prefixes = _subnet_only_cell(lookups, subnet_idx, pattern=pattern)
    if host is None:
        return prefixes
    return _dedupe_objects([host, *prefixes])


def _overlap_demo_cell_selection(
    rule_index: int,
    lookups: _BenchAddressLookups,
) -> tuple[list[Any], list[Any], list[Any], list[Any]]:
    """Populate both src/dst cells for showcase rules 1–20 (overlap bundles + padding)."""
    empty: list[Any] = []
    if not (1 <= rule_index <= BENCH_OVERLAP_SHOWCASE_RULE_COUNT):
        return empty, empty, empty, empty

    src_n, dst_n, src_gn, dst_gn = _showcase_cell_counts(rule_index)
    addr_pool = _build_overlap_address_pool(
        lookups, overlap_leaf_limit=lookups.overlap_leaf_limit
    )
    grp_pool = _showcase_group_padding_pool(lookups)
    limit = lookups.overlap_leaf_limit

    src_core: list[Any] = []
    dst_core: list[Any] = []
    src_grp_core: list[Any] = []
    dst_grp_core: list[Any] = []

    if 1 <= rule_index <= 5:
        src_leaf = _showcase_leaf_for_side_alias_dup(rule_index, "src", limit)
        dst_leaf = _showcase_leaf_for_side_alias_dup(rule_index, "dst", limit)
        src_core = _canonical_alias_dup_cell(lookups, src_leaf)
        dst_core = _canonical_alias_dup_cell(lookups, dst_leaf)
        subnet_src, _ = _leaf_indices(src_leaf)
        subnet_dst, _ = _leaf_indices(dst_leaf)
        src_grp_core = [
            g
            for g in [lookups.subnet_group_by_subnet.get(subnet_src)]
            if g is not None
        ]
        dst_grp_core = [
            g
            for g in [lookups.subnet_group_by_subnet.get(subnet_dst)]
            if g is not None
        ]

    elif 6 <= rule_index <= 10:
        include_wider = rule_index in (7, 9, 10)
        src_leaf = _showcase_host_leaf_for_side(rule_index, "src", limit)
        dst_leaf = _showcase_host_leaf_for_side(rule_index, "dst", limit)
        src_core = _host_prefix_cell(lookups, src_leaf, include_wider=include_wider)
        dst_core = _host_prefix_cell(lookups, dst_leaf, include_wider=include_wider)
        subnet_src, _ = _leaf_indices(src_leaf)
        subnet_dst, _ = _leaf_indices(dst_leaf)
        src_grp_core = [
            g
            for g in [
                lookups.subnet_group_by_subnet.get(subnet_src),
                lookups.overlap_group_by_pair.get(subnet_src),
            ]
            if g is not None
        ]
        dst_grp_core = [
            g
            for g in [
                lookups.subnet_group_by_subnet.get(subnet_dst),
                lookups.overlap_group_by_pair.get(subnet_dst),
            ]
            if g is not None
        ]

    elif 11 <= rule_index <= 15:
        src_pair = _showcase_pair_idx_for_side(rule_index, "src", lookups)
        dst_pair = _showcase_pair_idx_for_side(rule_index, "dst", lookups)
        src_core, src_grp_core = _overlap_group_member_cell(lookups, src_pair)
        dst_core, dst_grp_core = _overlap_group_member_cell(lookups, dst_pair)

    elif 16 <= rule_index <= 20:
        patterns = ("all", "24_20", "20_16", "24_16", "24_only")
        pattern = patterns[rule_index - 16]
        max_subnet = max(0, _overlap_subnet_count_from_limit(limit) - 1)
        src_subnet = _showcase_subnet_idx_for_side(
            rule_index, "src", max_subnet=max_subnet
        )
        dst_subnet = _showcase_subnet_idx_for_side(
            rule_index, "dst", max_subnet=max_subnet
        )
        src_core = _subnet_overlap_bundle(lookups, src_subnet, pattern=pattern)
        dst_core = _subnet_overlap_bundle(lookups, dst_subnet, pattern=pattern)
        src_grp_core = [
            g
            for g in [lookups.subnet_group_by_subnet.get(src_subnet)]
            if g is not None
        ]
        dst_grp_core = [
            g
            for g in [lookups.subnet_group_by_subnet.get(dst_subnet)]
            if g is not None
        ]

    src_addrs = _pad_showcase_cell(
        src_core,
        addr_pool,
        src_n,
        rule_index=rule_index,
        slot=0,
        max_items=SHOWCASE_ADDR_PICK_MAX,
    )
    dst_addrs = _pad_showcase_cell(
        dst_core,
        addr_pool,
        dst_n,
        rule_index=rule_index,
        slot=1,
        max_items=SHOWCASE_ADDR_PICK_MAX,
    )
    src_grps = _pad_showcase_cell(
        src_grp_core,
        grp_pool,
        src_gn,
        rule_index=rule_index,
        slot=2,
        max_items=SHOWCASE_GROUP_PICK_MAX,
    )
    dst_grps = _pad_showcase_cell(
        dst_grp_core,
        grp_pool,
        dst_gn,
        rule_index=rule_index,
        slot=3,
        max_items=SHOWCASE_GROUP_PICK_MAX,
    )

    if not (src_addrs and dst_addrs and src_grps and dst_grps):
        return empty, empty, empty, empty
    return src_addrs, dst_addrs, src_grps, dst_grps


def _pick_regular_addresses(
    addr_rng: random.Random,
    *,
    address_pool: list[Any],
    prefix_pool: list[Any],
    overlap_pool: list[Any],
    count: int,
) -> list[Any]:
    """Pick addresses for non-showcase rules; bias overlap bucket + guarantee a prefix."""
    if count <= 0 or not address_pool:
        return []

    selected: list[Any] = []
    remaining = count

    if prefix_pool and remaining > 0:
        selected.append(addr_rng.choice(prefix_pool))
        remaining -= 1

    pool = address_pool
    if overlap_pool and addr_rng.random() < OVERLAP_BUCKET_PICK_PROBABILITY:
        pool = overlap_pool

    if remaining > 0:
        available = [obj for obj in pool if obj.pk not in {o.pk for o in selected}]
        if not available:
            available = [obj for obj in address_pool if obj.pk not in {o.pk for o in selected}]
        pick_n = min(remaining, len(available))
        if pick_n:
            selected.extend(addr_rng.sample(available, pick_n))

    return _dedupe_objects(selected)


def overlap_demo_rule_descriptions(
    *,
    overlap_leaf_limit: int | None = None,
) -> list[dict[str, str]]:
    """Documented overlap-showcase rules for manual IPA testing (rules 1–20)."""
    limit = overlap_leaf_limit or _overlap_bucket_leaf_count(DEFAULT_LEAF_COUNT)
    descriptions: list[dict[str, str]] = []
    subnet_patterns = ("all", "24_20", "20_16", "24_16", "24_only")
    max_subnet = max(0, _overlap_subnet_count_from_limit(limit) - 1)
    max_pair = max(0, _overlap_subnet_count_from_limit(limit) - 2)

    def _ipam_host_note(leaf_idx: int) -> str:
        return (
            f"{_bench_host_name(leaf_idx)} + {_bench_iface_name(leaf_idx)} "
            f"({_host_cidr(*_leaf_indices(leaf_idx))})"
        )

    def _side_doc(
        rule_index: int,
        side: str,
    ) -> tuple[str, str, str | None]:
        """Return (pattern, objects, optional ipam_host) for one cell."""
        if 1 <= rule_index <= 5:
            leaf_idx = _showcase_leaf_for_side_alias_dup(rule_index, side, limit)
            subnet_idx, _ = _leaf_indices(leaf_idx)
            return (
                "canonical_alias_dup_same_leaf",
                (
                    f"{_leaf_name(leaf_idx)} + {_alias_name(leaf_idx)} + "
                    f"{_dup_name(leaf_idx)} + {_subnet_name(subnet_idx)}; "
                    f"group {_group_name(subnet_idx)}"
                ),
                _ipam_host_note(leaf_idx),
            )

        if 6 <= rule_index <= 10:
            include_wider = rule_index in (7, 9, 10)
            leaf_idx = _showcase_host_leaf_for_side(rule_index, side, limit)
            subnet_idx, _ = _leaf_indices(leaf_idx)
            wide_idx = subnet_idx // SUBNETS_PER_WIDE
            super_idx = subnet_idx // SUBNETS_PER_SUPER
            if include_wider:
                return (
                    "host_wider_prefixes",
                    (
                        f"{_leaf_name(leaf_idx)} + {_subnet_name(subnet_idx)} + "
                        f"{_wide_name(wide_idx)} + {_super_name(super_idx)}; "
                        f"groups {_group_name(subnet_idx)}"
                    ),
                    _ipam_host_note(leaf_idx),
                )
            return (
                "host_subnet_containment",
                (
                    f"{_leaf_name(leaf_idx)} + {_subnet_name(subnet_idx)}; "
                    f"group {_group_name(subnet_idx)}"
                ),
                _ipam_host_note(leaf_idx),
            )

        if 11 <= rule_index <= 15:
            pair_idx = (rule_index - 11) % max(1, max_pair + 1)
            if side == "dst":
                pair_idx = (pair_idx + max(1, (max_pair + 1) // 2)) % max(
                    1, max_pair + 1
                )
            member_hosts = ", ".join(
                _bench_host_name(subnet_idx * HOSTS_PER_SUBNET)
                for subnet_idx in (pair_idx, pair_idx + 1)
            )
            return (
                "overlap_group_with_members",
                (
                    f"{_grp_ovlp_name(pair_idx)} + {_subnet_name(pair_idx)} + "
                    f"{_subnet_name(pair_idx + 1)} + host members"
                ),
                member_hosts,
            )

        subnet_idx = _showcase_subnet_idx_for_side(
            rule_index, side, max_subnet=max_subnet
        )
        wide_idx = subnet_idx // SUBNETS_PER_WIDE
        super_idx = subnet_idx // SUBNETS_PER_SUPER
        pattern = subnet_patterns[rule_index - 16]
        host_leaf = subnet_idx * HOSTS_PER_SUBNET
        if pattern == "all":
            objects = (
                f"{_leaf_name(host_leaf)} + {_subnet_name(subnet_idx)} + "
                f"{_wide_name(wide_idx)} + {_super_name(super_idx)}; "
                f"group {_group_name(subnet_idx)}"
            )
        elif pattern == "24_20":
            objects = (
                f"{_leaf_name(host_leaf)} + {_subnet_name(subnet_idx)} + "
                f"{_wide_name(wide_idx)}; group {_group_name(subnet_idx)}"
            )
        elif pattern == "20_16":
            objects = (
                f"{_leaf_name(host_leaf)} + {_wide_name(wide_idx)} + "
                f"{_super_name(super_idx)}; group {_group_name(subnet_idx)}"
            )
        elif pattern == "24_16":
            objects = (
                f"{_leaf_name(host_leaf)} + {_subnet_name(subnet_idx)} + "
                f"{_super_name(super_idx)}; group {_group_name(subnet_idx)}"
            )
        else:
            objects = (
                f"{_leaf_name(host_leaf)} + {_subnet_name(subnet_idx)}; "
                f"group {_group_name(subnet_idx)}"
            )
        return (
            f"subnets_with_host_{pattern}",
            objects,
            _ipam_host_note(host_leaf),
        )

    for rule_index in range(1, BENCH_OVERLAP_SHOWCASE_RULE_COUNT + 1):
        src_pattern, src_objects, src_ipam = _side_doc(rule_index, "src")
        dst_pattern, dst_objects, dst_ipam = _side_doc(rule_index, "dst")
        src_n, dst_n, src_gn, dst_gn = _showcase_cell_counts(rule_index)
        entry: dict[str, str] = {
            "index": str(rule_index),
            "name": f"{_BENCH_RULE_PREFIX}{rule_index:05d}",
            "source_pattern": src_pattern,
            "source_objects": src_objects,
            "destination_pattern": dst_pattern,
            "destination_objects": dst_objects,
            "counts": (
                f"src: {src_n} addr + {src_gn} grp; "
                f"dst: {dst_n} addr + {dst_gn} grp"
            ),
        }
        if src_ipam or dst_ipam:
            hosts = [h for h in (src_ipam, dst_ipam) if h]
            entry["ipam_host"] = "; ".join(dict.fromkeys(hosts))
        descriptions.append(entry)

    return descriptions


def _build_overlap_address_pool(
    lookups: _BenchAddressLookups,
    *,
    overlap_leaf_limit: int,
) -> list[Any]:
    """Addresses in the overlap bucket (hosts, alias/dup peers, /24–/16 prefixes)."""
    pool: list[Any] = []
    for leaf_idx in range(overlap_leaf_limit):
        leaf = lookups.leaf_by_idx.get(leaf_idx)
        if leaf is not None:
            pool.append(leaf)
        for mapping in (lookups.alias_by_leaf, lookups.dup_by_leaf):
            obj = mapping.get(leaf_idx)
            if obj is not None:
                pool.append(obj)

    overlap_subnet_count = (
        (overlap_leaf_limit + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET
        if overlap_leaf_limit
        else 0
    )
    seen_wide: set[int] = set()
    seen_super: set[int] = set()
    for subnet_idx in range(overlap_subnet_count):
        net = lookups.net_by_subnet.get(subnet_idx)
        if net is not None:
            pool.append(net)
        wide_idx = subnet_idx // SUBNETS_PER_WIDE
        super_idx = subnet_idx // SUBNETS_PER_SUPER
        if wide_idx not in seen_wide:
            seen_wide.add(wide_idx)
            wide = lookups.wide_by_idx.get(wide_idx)
            if wide is not None:
                pool.append(wide)
        if super_idx not in seen_super:
            seen_super.add(super_idx)
            supernet = lookups.super_by_idx.get(super_idx)
            if supernet is not None:
                pool.append(supernet)

    return _dedupe_objects(pool)


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
        schema_yaml=bench_rulebook_schema_yaml(),
        display_name="Bench Addresses",
    )


def _ensure_bench_zones(ZoneModel) -> list[Any]:
    """Create ``bench-zone-*`` rows for the bench rule generator."""
    zones = []
    for zone_idx in range(BENCH_ZONE_COUNT):
        zone, _ = ZoneModel.objects.get_or_create(name=_bench_zone_name(zone_idx))
        zones.append(zone)
    return zones


def _load_zone_pool(ZoneModel) -> list[Any]:
    """Prefer bench zones; fall back to starter ``zone_*`` or bundled defaults."""
    bench_zones = list(
        ZoneModel.objects.filter(name__startswith=_BENCH_ZONE_PREFIX).order_by("name")
    )
    if bench_zones:
        return bench_zones

    starter_zones = list(
        ZoneModel.objects.filter(name__startswith=_STARTER_ZONE_PREFIX).order_by("name")
    )
    if starter_zones:
        return starter_zones

    if ZoneModel.objects.exists():
        return list(ZoneModel.objects.order_by("name"))

    return _ensure_bench_zones(ZoneModel)


def _content_type_id_cache() -> dict[type, int]:
    cache: dict[type, int] = {}

    def ct_id(obj) -> int:
        cls = type(obj)
        if cls not in cache:
            cache[cls] = ContentType.objects.get_for_model(cls).pk
        return cache[cls]

    return ct_id


def _get_or_create_prefix(cidr: str) -> Prefix:
    """Return an IPAM prefix for *cidr*, tolerating duplicate rows (e.g. branching)."""
    existing = Prefix.objects.filter(prefix=cidr).order_by("pk").first()
    if existing is not None:
        return existing
    return Prefix.objects.create(prefix=cidr, status="active")


def _create_subnet_addresses(
    AddrModel,
    *,
    subnet_count: int,
) -> dict[int, Prefix]:
    """Create /24 prefixes and parent ``bench-net-*`` address rows."""
    prefix_by_subnet: dict[int, Prefix] = {}
    for subnet_idx in range(subnet_count):
        cidr = _subnet_prefix_cidr(subnet_idx)
        prefix = _get_or_create_prefix(cidr)
        prefix_by_subnet[subnet_idx] = prefix
        AddrModel.objects.get_or_create(
            name=_subnet_name(subnet_idx),
            defaults=_address_polymorphic_kwargs(prefix),
        )
    return prefix_by_subnet


def _create_wider_subnet_addresses(
    AddrModel,
    *,
    overlap_subnet_count: int,
) -> tuple[list[Any], list[Any]]:
    """Create /20 and /16 parent prefixes for the overlap bucket."""
    if overlap_subnet_count <= 0:
        return [], []

    wide_blocks = {
        subnet_idx // SUBNETS_PER_WIDE for subnet_idx in range(overlap_subnet_count)
    }
    super_blocks = {
        subnet_idx // SUBNETS_PER_SUPER for subnet_idx in range(overlap_subnet_count)
    }

    wide_addrs: list[Any] = []
    for wide_idx in sorted(wide_blocks):
        block_start = wide_idx * SUBNETS_PER_WIDE
        cidr = _wider_prefix_cidr(block_start, PREFIX_LEN_WIDE)
        prefix = _get_or_create_prefix(cidr)
        addr, _ = AddrModel.objects.get_or_create(
            name=_wide_name(wide_idx),
            defaults=_address_polymorphic_kwargs(prefix),
        )
        wide_addrs.append(addr)

    super_addrs: list[Any] = []
    for super_idx in sorted(super_blocks):
        block_start = super_idx * SUBNETS_PER_SUPER
        cidr = _wider_prefix_cidr(block_start, PREFIX_LEN_SUPER)
        prefix = _get_or_create_prefix(cidr)
        addr, _ = AddrModel.objects.get_or_create(
            name=_super_name(super_idx),
            defaults=_address_polymorphic_kwargs(prefix),
        )
        super_addrs.append(addr)

    return wide_addrs, super_addrs


def _create_leaf_addresses(
    AddrModel,
    *,
    leaf_count: int,
    prefix_by_subnet: dict[int, Prefix],
    overlap_leaf_limit: int,
) -> tuple[list[Any], list[Any], list[Any], dict[int, list[Any]]]:
    """Bulk-create host ``bench-ip-*`` rows, alias/dup peers, and subnet index."""
    leaves: list[Any] = []
    aliases: list[Any] = []
    dup_names: list[Any] = []
    leaves_by_subnet: dict[int, list[Any]] = defaultdict(list)
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
            alias_batch = []
            dup_batch = []
            for offset, ip in enumerate(created_ips):
                host_idx = batch_start + offset
                global_leaf = subnet_idx * HOSTS_PER_SUBNET + host_idx
                canonical = _leaf_name(global_leaf)
                network = _host_cidr(subnet_idx, host_idx)
                addr_batch.append(
                    AddrModel(
                        name=canonical,
                        **_address_polymorphic_kwargs(ip),
                    )
                )
                alias_stride = _alias_stride_for_leaf(global_leaf, overlap_leaf_limit)
                if global_leaf % alias_stride == 0:
                    alias_batch.append(
                        AddrModel(
                            name=_alias_name(global_leaf),
                            comments=_alias_comments(canonical, network),
                            **_address_polymorphic_kwargs(ip),
                        )
                    )
                if (
                    _leaf_in_overlap_bucket(global_leaf, overlap_leaf_limit)
                    and global_leaf % OVERLAP_DUP_NAME_STRIDE == 0
                ):
                    dup_batch.append(
                        AddrModel(
                            name=_dup_name(global_leaf),
                            comments=_alias_comments(canonical, network),
                            **_address_polymorphic_kwargs(ip),
                        )
                    )

            created_leaves = AddrModel.objects.bulk_create(
                addr_batch, batch_size=BATCH_SIZE
            )
            leaves.extend(created_leaves)
            leaves_by_subnet[subnet_idx].extend(created_leaves)

            if alias_batch:
                created_aliases = AddrModel.objects.bulk_create(
                    alias_batch, batch_size=BATCH_SIZE
                )
                aliases.extend(created_aliases)
            if dup_batch:
                created_dups = AddrModel.objects.bulk_create(
                    dup_batch, batch_size=BATCH_SIZE
                )
                dup_names.extend(created_dups)

    return leaves, aliases, dup_names, leaves_by_subnet


def _ensure_bench_virtualization_prerequisites():
    """Minimal Site + Cluster for ``bench-host-*`` VMs (idempotent)."""
    from dcim.models import Site
    from virtualization.models import Cluster, ClusterType

    site, _ = Site.objects.get_or_create(
        name=_BENCH_SITE_NAME,
        defaults={"slug": _BENCH_SITE_SLUG},
    )
    cluster_type, _ = ClusterType.objects.get_or_create(
        slug=_BENCH_CLUSTER_TYPE_SLUG,
        defaults={"name": "Bench cluster"},
    )
    cluster, _ = Cluster.objects.get_or_create(
        name=_BENCH_CLUSTER_NAME,
        defaults={"type": cluster_type},
    )
    return site, cluster


def _resolve_leaf_ip_address(addr_obj) -> IPAddress | None:
    """Return the linked ``IPAddress`` for a canonical ``bench-ip-*`` row."""
    if addr_obj is None:
        return None
    if getattr(addr_obj, "address_content_type_id", None) == _ip_content_type_id():
        ip_id = getattr(addr_obj, "address_object_id", None)
        if ip_id:
            return IPAddress.objects.filter(pk=ip_id).first()
    ip_obj = getattr(addr_obj, "ip_address", None)
    if isinstance(ip_obj, IPAddress):
        return ip_obj
    return None


def _assign_ip_to_bench_iface(ip_obj: IPAddress, iface) -> None:
    """Assign *ip_obj* to *iface* and set VM primary_ip4 when applicable."""
    from virtualization.models import VMInterface

    iface_ct = ContentType.objects.get_for_model(VMInterface)
    dirty = False
    if (
        ip_obj.assigned_object_type_id != iface_ct.pk
        or ip_obj.assigned_object_id != iface.pk
    ):
        ip_obj.assigned_object_type = iface_ct
        ip_obj.assigned_object_id = iface.pk
        dirty = True
    if dirty:
        ip_obj.save(update_fields=["assigned_object_type", "assigned_object_id"])

    vm = getattr(iface, "virtual_machine", None)
    if vm is not None and vm.primary_ip4_id != ip_obj.pk:
        vm.primary_ip4 = ip_obj
        vm.save(update_fields=["primary_ip4"])


def _create_showcase_ipam_hosts(
    *,
    leaf_indices: list[int],
    leaf_by_idx: dict[int, Any],
) -> dict[str, int]:
    """
    Create ``bench-host-*`` + ``bench-iface-*`` for overlap showcase leaf indices.

    Only canonical ``bench-ip-*`` rows are considered; alias/dup peers keep sharing
    the same ``IPAddress`` already linked on the COT row.
    """
    if not leaf_indices:
        return {"hosts": 0, "interfaces": 0, "ips_assigned": 0, "leaf_indices": []}

    from virtualization.models import VirtualMachine, VMInterface

    site, cluster = _ensure_bench_virtualization_prerequisites()

    hosts_created = 0
    ifaces_created = 0
    ips_assigned = 0
    resolved_indices: list[int] = []
    iface_ct = ContentType.objects.get_for_model(VMInterface)

    for leaf_idx in leaf_indices:
        addr_obj = leaf_by_idx.get(leaf_idx)
        ip_obj = _resolve_leaf_ip_address(addr_obj)
        if ip_obj is None:
            continue

        resolved_indices.append(leaf_idx)

        host_name = _bench_host_name(leaf_idx)
        iface_name = _bench_iface_name(leaf_idx)
        vm, vm_created = VirtualMachine.objects.get_or_create(
            name=host_name,
            defaults={
                "cluster": cluster,
                "site": site,
                "status": "active",
                "vcpus": 1,
                "memory": 1024,
            },
        )
        if vm_created:
            hosts_created += 1

        iface, iface_created = VMInterface.objects.get_or_create(
            virtual_machine=vm,
            name=iface_name,
        )
        if iface_created:
            ifaces_created += 1

        if (
            ip_obj.assigned_object_id != iface.pk
            or ip_obj.assigned_object_type_id != iface_ct.pk
        ):
            _assign_ip_to_bench_iface(ip_obj, iface)
            ips_assigned += 1

    return {
        "hosts": hosts_created,
        "interfaces": ifaces_created,
        "ips_assigned": ips_assigned,
        "leaf_indices": resolved_indices,
    }


def _bulk_set_group_members(
    GroupModel,
    *,
    groups: list[Any],
    members_by_subnet: dict[int, list[Any]],
    net_addrs_by_subnet: dict[int, Any],
) -> int:
    """Bulk attach ``nsm_address`` members to ``bench-grp-*`` rows."""
    if not groups:
        return 0

    group_field = GroupModel._meta.get_field("group")
    Through = group_field.remote_field.through
    rows = []
    member_links = 0

    for group in groups:
        subnet_idx = int(group.name.removeprefix(_BENCH_GRP_PREFIX))
        members = list(members_by_subnet.get(subnet_idx, []))
        net_addr = net_addrs_by_subnet.get(subnet_idx)
        if net_addr is not None:
            members.insert(0, net_addr)
        for member in members:
            rows.append(Through(source_id=group.pk, target_id=member.pk))
            member_links += 1

    Through.objects.bulk_create(rows, batch_size=BATCH_SIZE)
    return member_links


def _create_overlap_groups(
    GroupModel,
    *,
    overlap_subnet_count: int,
    leaves_by_subnet: dict[int, list[Any]],
    net_addrs_by_subnet: dict[int, Any],
) -> tuple[list[Any], int]:
    """Create ``bench-grp-ovlp-*`` rows spanning adjacent overlap subnets."""
    if overlap_subnet_count < 2:
        return [], 0

    GroupModel.objects.filter(name__startswith=_BENCH_GRP_OVLP_PREFIX).delete()
    pair_count = overlap_subnet_count - 1
    groups = GroupModel.objects.bulk_create(
        [GroupModel(name=_grp_ovlp_name(pair_idx)) for pair_idx in range(pair_count)],
        batch_size=BATCH_SIZE,
    )

    group_field = GroupModel._meta.get_field("group")
    Through = group_field.remote_field.through
    rows = []
    member_links = 0

    for group in groups:
        pair_idx = int(group.name.removeprefix(_BENCH_GRP_OVLP_PREFIX))
        members: list[Any] = []
        for subnet_idx in (pair_idx, pair_idx + 1):
            net_addr = net_addrs_by_subnet.get(subnet_idx)
            if net_addr is not None:
                members.append(net_addr)
            members.extend(
                leaves_by_subnet.get(subnet_idx, [])[:OVERLAP_LEAVES_PER_GROUP]
            )
        for member in members:
            rows.append(Through(source_id=group.pk, target_id=member.pk))
            member_links += 1

    if rows:
        Through.objects.bulk_create(rows, batch_size=BATCH_SIZE)
    return groups, member_links


def _create_address_groups(
    GroupModel,
    AddrModel,
    *,
    subnet_count: int,
    leaves_by_subnet: dict[int, list[Any]],
) -> tuple[list[Any], int]:
    """Create one ``bench-grp-*`` per subnet aggregating net + host addresses."""
    net_addrs_by_subnet = {
        subnet_idx: AddrModel.objects.filter(name=_subnet_name(subnet_idx)).first()
        for subnet_idx in range(subnet_count)
    }

    groups = GroupModel.objects.bulk_create(
        [GroupModel(name=_group_name(subnet_idx)) for subnet_idx in range(subnet_count)],
        batch_size=BATCH_SIZE,
    )
    member_links = _bulk_set_group_members(
        GroupModel,
        groups=groups,
        members_by_subnet=leaves_by_subnet,
        net_addrs_by_subnet=net_addrs_by_subnet,
    )
    return groups, member_links


def _bulk_seed_bench_rule_relations(
    rulebook_cot,
    *,
    rules: list[Any],
    src_zone_field: str,
    dst_zone_field: str,
    src_field: str,
    dst_field: str,
    zone_pool: list[Any],
    address_pool: list[Any],
    prefix_pool: list[Any],
    overlap_pool: list[Any],
    group_pool: list[Any],
    address_lookups: _BenchAddressLookups | None,
    services: list[Any],
    actions: dict[str, Any],
    addr_rng: random.Random,
    grp_rng: random.Random,
    zone_rng: random.Random,
    svc_rng: random.Random,
    act_rng: random.Random,
) -> int:
    """Bulk-create zone/address/service/action M2M rows for bench rules."""
    ct_id = _content_type_id_cache()
    SrcZoneThrough = get_cot_field_through_model(rulebook_cot, src_zone_field)
    DstZoneThrough = get_cot_field_through_model(rulebook_cot, dst_zone_field)
    SrcThrough = get_cot_field_through_model(rulebook_cot, src_field)
    DstThrough = get_cot_field_through_model(rulebook_cot, dst_field)
    ServicesThrough = get_cot_field_through_model(rulebook_cot, "services_applications")
    ActionsThrough = get_cot_field_through_model(rulebook_cot, "actions")
    fallback_action = next(iter(actions.values()), None)
    zone_ct_id = ct_id(zone_pool[0])

    src_zone_rows = []
    dst_zone_rows = []
    src_rows = []
    dst_rows = []
    service_rows = []
    action_rows = []
    object_items = 0

    for rule in rules:
        src_zone = zone_rng.choice(zone_pool)
        dst_zone = zone_rng.choice(zone_pool)
        src_zone_rows.append(
            SrcZoneThrough(
                source_id=rule.pk,
                content_type_id=zone_ct_id,
                object_id=src_zone.pk,
            )
        )
        dst_zone_rows.append(
            DstZoneThrough(
                source_id=rule.pk,
                content_type_id=zone_ct_id,
                object_id=dst_zone.pk,
            )
        )

        if (
            address_lookups is not None
            and 1 <= rule.index <= BENCH_OVERLAP_SHOWCASE_RULE_COUNT
        ):
            demo_src, demo_dst, demo_src_grps, demo_dst_grps = (
                _overlap_demo_cell_selection(rule.index, address_lookups)
            )
            src_objs = demo_src
            dst_objs = demo_dst
            src_grps = demo_src_grps
            dst_grps = demo_dst_grps
        else:
            src_n = _pick_counts(
                addr_rng,
                pool_size=len(address_pool),
                min_n=ADDR_PICK_MIN,
                max_n=ADDR_PICK_MAX,
            )
            dst_n = _pick_counts(
                addr_rng,
                pool_size=len(address_pool),
                min_n=ADDR_PICK_MIN,
                max_n=ADDR_PICK_MAX,
            )
            src_objs = _pick_regular_addresses(
                addr_rng,
                address_pool=address_pool,
                prefix_pool=prefix_pool,
                overlap_pool=overlap_pool,
                count=src_n,
            )
            dst_objs = _pick_regular_addresses(
                addr_rng,
                address_pool=address_pool,
                prefix_pool=prefix_pool,
                overlap_pool=overlap_pool,
                count=dst_n,
            )
            src_g = _pick_counts(
                grp_rng, pool_size=len(group_pool), min_n=GROUP_PICK_MIN, max_n=GROUP_PICK_MAX
            )
            dst_g = _pick_counts(
                grp_rng, pool_size=len(group_pool), min_n=GROUP_PICK_MIN, max_n=GROUP_PICK_MAX
            )
            src_grps = grp_rng.sample(group_pool, src_g) if src_g else []
            dst_grps = grp_rng.sample(group_pool, dst_g) if dst_g else []

        for obj in src_objs + src_grps:
            src_rows.append(
                SrcThrough(
                    source_id=rule.pk,
                    content_type_id=ct_id(obj),
                    object_id=obj.pk,
                )
            )
        for obj in dst_objs + dst_grps:
            dst_rows.append(
                DstThrough(
                    source_id=rule.pk,
                    content_type_id=ct_id(obj),
                    object_id=obj.pk,
                )
            )

        service = svc_rng.choice(services)
        service_rows.append(
            ServicesThrough(
                source_id=rule.pk,
                content_type_id=ct_id(service),
                object_id=service.pk,
            )
        )
        action_key = "permit" if act_rng.random() < 0.5 else "deny"
        action = actions.get(action_key) or fallback_action
        action_rows.append(ActionsThrough(source_id=rule.pk, target_id=action.pk))

        object_items += (
            2
            + len(src_objs)
            + len(src_grps)
            + len(dst_objs)
            + len(dst_grps)
            + 2
        )

    SrcZoneThrough.objects.bulk_create(src_zone_rows, batch_size=BATCH_SIZE)
    DstZoneThrough.objects.bulk_create(dst_zone_rows, batch_size=BATCH_SIZE)
    SrcThrough.objects.bulk_create(src_rows, batch_size=BATCH_SIZE)
    DstThrough.objects.bulk_create(dst_rows, batch_size=BATCH_SIZE)
    ServicesThrough.objects.bulk_create(service_rows, batch_size=BATCH_SIZE)
    ActionsThrough.objects.bulk_create(action_rows, batch_size=BATCH_SIZE)
    return object_items


def _create_bench_rules(
    rulebook_cot,
    *,
    zone_pool: list[Any],
    address_pool: list[Any],
    prefix_pool: list[Any],
    overlap_pool: list[Any],
    group_pool: list[Any],
    address_lookups: _BenchAddressLookups | None,
    rule_count: int,
    recreate_rules: bool,
) -> tuple[int, int]:
    """Create COT rule rows with zone + address + address-group refs."""
    RuleModel = rulebook_cot.get_model()
    if recreate_rules:
        RuleModel.objects.filter(name__startswith=_BENCH_RULE_PREFIX).delete()

    services = list(_load_lookup_map("nsm_service", "nsm_services").values())
    actions = _load_lookup_map("nsm_action")
    if not services:
        raise RuntimeError("No nsm_service objects found — run Setup seed/import first.")
    if not actions:
        raise RuntimeError("No nsm_action objects found — run Setup seed/import first.")
    if not zone_pool:
        raise RuntimeError("Zone pool is empty — create or import nsm_zone objects first.")
    if not address_pool:
        raise RuntimeError("Address pool is empty — create bench addresses first.")
    if not group_pool:
        raise RuntimeError("Address group pool is empty — create bench groups first.")

    src_zone_field, dst_zone_field = resolve_rulebook_zone_field_names(rulebook_cot)
    src_field, dst_field = resolve_rulebook_address_field_names(rulebook_cot)
    addr_rng = random.Random(RULE_RANDOM_SEED)
    grp_rng = random.Random(GROUP_RANDOM_SEED)
    zone_rng = random.Random(ZONE_RANDOM_SEED)
    svc_rng = random.Random(SERVICE_RANDOM_SEED)
    act_rng = random.Random(ACTION_RANDOM_SEED)

    rules = []
    for batch_start in range(0, rule_count, RULE_BATCH_SIZE):
        batch_end = min(batch_start + RULE_BATCH_SIZE, rule_count)
        rules.extend(
            RuleModel.objects.bulk_create(
                [
                    RuleModel(
                        index=i + 1,
                        status=True,
                        name=f"{_BENCH_RULE_PREFIX}{i + 1:05d}",
                    )
                    for i in range(batch_start, batch_end)
                ],
                batch_size=RULE_BATCH_SIZE,
            )
        )

    object_items = _bulk_seed_bench_rule_relations(
        rulebook_cot,
        rules=rules,
        src_zone_field=src_zone_field,
        dst_zone_field=dst_zone_field,
        src_field=src_field,
        dst_field=dst_field,
        zone_pool=zone_pool,
        address_pool=address_pool,
        prefix_pool=prefix_pool,
        overlap_pool=overlap_pool,
        group_pool=group_pool,
        address_lookups=address_lookups,
        services=services,
        actions=actions,
        addr_rng=addr_rng,
        grp_rng=grp_rng,
        zone_rng=zone_rng,
        svc_rng=svc_rng,
        act_rng=act_rng,
    )
    return rule_count, object_items


def _load_bench_address_pool(
    AddrModel,
) -> tuple[list[Any], list[Any], list[Any], dict[int, list[Any]]]:
    """Reload canonical leaves, alias/dup peers, and subnet grouping from the DB."""
    leaves = list(
        AddrModel.objects.filter(name__startswith=_BENCH_IP_PREFIX).order_by("name")
    )
    aliases = list(
        AddrModel.objects.filter(name__startswith=_BENCH_ALIAS_PREFIX).order_by("name")
    )
    dup_names = list(
        AddrModel.objects.filter(name__startswith=_BENCH_DUP_PREFIX).order_by("name")
    )
    leaves_by_subnet: dict[int, list[Any]] = defaultdict(list)
    for leaf in leaves:
        leaf_idx = int(leaf.name.removeprefix(_BENCH_IP_PREFIX))
        subnet_idx, _host_idx = _leaf_indices(leaf_idx)
        leaves_by_subnet[subnet_idx].append(leaf)
    return leaves, aliases, dup_names, leaves_by_subnet


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
    """Create bench addresses/groups and/or COT policy rules; return summary dict."""
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
    aliases: list[Any] = []
    dup_names: list[Any] = []
    groups: list[Any] = []
    overlap_groups: list[Any] = []
    wide_addrs: list[Any] = []
    super_addrs: list[Any] = []
    zones: list[Any] = []
    group_member_links = 0
    overlap_group_member_links = 0

    with transaction.atomic():
        AddrModel, _addr_cot = get_cot_model("nsm_address", "nsm_addresses")
        GroupModel, _group_cot = get_cot_model("nsm_address_group", "nsm_address_groups")
        ZoneModel, _zone_cot = get_cot_model("nsm_zone", "nsm_zones")
        zones = _load_zone_pool(ZoneModel)

        if not skip_addresses:
            subnet_count = (leaf_count + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET
            overlap_leaf_limit = _overlap_bucket_leaf_count(leaf_count)
            overlap_subnet_count = _overlap_bucket_subnet_count(leaf_count)
            prefix_by_subnet = _create_subnet_addresses(
                AddrModel,
                subnet_count=subnet_count,
            )
            wide_addrs, super_addrs = _create_wider_subnet_addresses(
                AddrModel,
                overlap_subnet_count=overlap_subnet_count,
            )
            leaves, aliases, dup_names, leaves_by_subnet = _create_leaf_addresses(
                AddrModel,
                leaf_count=leaf_count,
                prefix_by_subnet=prefix_by_subnet,
                overlap_leaf_limit=overlap_leaf_limit,
            )
            GroupModel.objects.filter(name__startswith=_BENCH_GRP_PREFIX).delete()
            groups, group_member_links = _create_address_groups(
                GroupModel,
                AddrModel,
                subnet_count=subnet_count,
                leaves_by_subnet=leaves_by_subnet,
            )
            net_addrs_by_subnet = {
                subnet_idx: AddrModel.objects.filter(name=_subnet_name(subnet_idx)).first()
                for subnet_idx in range(subnet_count)
            }
            overlap_groups, overlap_group_member_links = _create_overlap_groups(
                GroupModel,
                overlap_subnet_count=overlap_subnet_count,
                leaves_by_subnet=leaves_by_subnet,
                net_addrs_by_subnet=net_addrs_by_subnet,
            )
        else:
            leaves, aliases, dup_names, leaves_by_subnet = _load_bench_address_pool(
                AddrModel
            )
            if not leaves:
                raise RuntimeError(
                    "No bench-ip-* addresses found; run without --skip-addresses first."
                )
            leaf_count = len(leaves)
            subnet_count = (leaf_count + HOSTS_PER_SUBNET - 1) // HOSTS_PER_SUBNET
            overlap_leaf_limit = _overlap_bucket_leaf_count(leaf_count)
            overlap_subnet_count = _overlap_bucket_subnet_count(leaf_count)
            groups = list(
                _bench_subnet_group_queryset(GroupModel).order_by("name")
            )
            overlap_groups = list(
                GroupModel.objects.filter(name__startswith=_BENCH_GRP_OVLP_PREFIX).order_by(
                    "name"
                )
            )
            if not groups:
                _bench_subnet_group_queryset(GroupModel).delete()
                groups, group_member_links = _create_address_groups(
                    GroupModel,
                    AddrModel,
                    subnet_count=subnet_count,
                    leaves_by_subnet=leaves_by_subnet,
                )
            if not overlap_groups:
                net_addrs_by_subnet = {
                    subnet_idx: AddrModel.objects.filter(name=_subnet_name(subnet_idx)).first()
                    for subnet_idx in range(subnet_count)
                }
                overlap_groups, overlap_group_member_links = _create_overlap_groups(
                    GroupModel,
                    overlap_subnet_count=overlap_subnet_count,
                    leaves_by_subnet=leaves_by_subnet,
                    net_addrs_by_subnet=net_addrs_by_subnet,
                )
            wide_addrs = list(
                AddrModel.objects.filter(name__startswith=_BENCH_NET_WIDE_PREFIX).order_by(
                    "name"
                )
            )
            super_addrs = list(
                AddrModel.objects.filter(name__startswith=_BENCH_NET_SUPER_PREFIX).order_by(
                    "name"
                )
            )

        net_addrs = list(_bench_net_address_queryset(AddrModel).order_by("name"))
        prefix_pool = net_addrs + wide_addrs + super_addrs
        address_pool = leaves + aliases + dup_names + prefix_pool
        address_lookups = _build_bench_address_lookups(
            leaves,
            aliases,
            dup_names,
            net_addrs,
            wide_addrs,
            super_addrs,
            groups,
            overlap_groups,
            overlap_leaf_limit=overlap_leaf_limit,
        )
        overlap_pool = _build_overlap_address_pool(
            address_lookups,
            overlap_leaf_limit=overlap_leaf_limit,
        )
        group_pool = groups + overlap_groups

        showcase_ipam = _create_showcase_ipam_hosts(
            leaf_indices=_showcase_bench_leaf_indices(
                overlap_leaf_limit=overlap_leaf_limit
            ),
            leaf_by_idx=address_lookups.leaf_by_idx,
        )

        rules_created = 0
        object_items = 0
        if not skip_rules and rule_count > 0:
            rules_created, object_items = _create_bench_rules(
                rulebook_cot,
                zone_pool=zones,
                address_pool=address_pool,
                prefix_pool=prefix_pool,
                overlap_pool=overlap_pool,
                group_pool=group_pool,
                address_lookups=address_lookups,
                rule_count=rule_count,
                recreate_rules=recreate_rules,
            )

    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "rulebook": rulebook_cot.verbose_name or rulebook_cot.name,
        "rulebook_slug": rulebook_cot.slug,
        "rulebook_id": rulebook_cot.pk,
        "leaves": len(leaves),
        "aliases": len(aliases),
        "dup_names": len(dup_names),
        "wider_prefixes": len(wide_addrs),
        "super_prefixes": len(super_addrs),
        "overlap_leaves": overlap_leaf_limit,
        "overlap_subnets": overlap_subnet_count,
        "groups": len(groups),
        "overlap_groups": len(overlap_groups),
        "zones": len(zones),
        "group_member_links": group_member_links,
        "overlap_group_member_links": overlap_group_member_links,
        "showcase_hosts": showcase_ipam["hosts"],
        "showcase_interfaces": showcase_ipam["interfaces"],
        "showcase_ips_assigned": showcase_ipam["ips_assigned"],
        "showcase_leaf_indices": showcase_ipam["leaf_indices"],
        "rules": rules_created,
        "object_items": object_items,
        "overlap_demo_rules": overlap_demo_rule_descriptions(
            overlap_leaf_limit=overlap_leaf_limit,
        ),
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
    """Remove bench-* rules, groups, addresses, and linked IPAM rows."""
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

    GroupModel, _ = get_cot_model("nsm_address_group", "nsm_address_groups")
    groups_deleted, _ = _bench_subnet_group_queryset(GroupModel).delete()
    overlap_groups_deleted, _ = GroupModel.objects.filter(
        name__startswith=_BENCH_GRP_OVLP_PREFIX
    ).delete()
    groups_deleted += overlap_groups_deleted

    ZoneModel, _ = get_cot_model("nsm_zone", "nsm_zones")
    zones_deleted, _ = ZoneModel.objects.filter(
        name__startswith=_BENCH_ZONE_PREFIX
    ).delete()

    AddrModel, _ = get_cot_model("nsm_address", "nsm_addresses")
    ip_ct_id = _ip_content_type_id()
    prefix_ct_id = _prefix_content_type_id()
    host_qs = AddrModel.objects.filter(name__startswith=_BENCH_IP_PREFIX)
    alias_qs = AddrModel.objects.filter(name__startswith=_BENCH_ALIAS_PREFIX)
    dup_qs = AddrModel.objects.filter(name__startswith=_BENCH_DUP_PREFIX)
    ip_ids = [
        pk
        for pk in host_qs.filter(address_content_type_id=ip_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]
    alias_ip_ids = [
        pk
        for pk in alias_qs.filter(address_content_type_id=ip_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]
    dup_ip_ids = [
        pk
        for pk in dup_qs.filter(address_content_type_id=ip_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]
    net_qs = _bench_net_address_queryset(AddrModel)
    wide_qs = AddrModel.objects.filter(name__startswith=_BENCH_NET_WIDE_PREFIX)
    super_qs = AddrModel.objects.filter(name__startswith=_BENCH_NET_SUPER_PREFIX)
    prefix_ids = [
        pk
        for qs in (net_qs, wide_qs, super_qs)
        for pk in qs.filter(address_content_type_id=prefix_ct_id).values_list(
            "address_object_id", flat=True
        )
        if pk
    ]

    addresses_deleted, _ = AddrModel.objects.filter(
        name__startswith="bench-"
    ).delete()

    from virtualization.models import VirtualMachine

    vms_deleted, _ = VirtualMachine.objects.filter(
        name__startswith=_BENCH_HOST_PREFIX
    ).delete()

    all_ip_ids = list(dict.fromkeys(ip_ids + alias_ip_ids + dup_ip_ids))
    ip_addresses_deleted = 0
    if all_ip_ids:
        ip_addresses_deleted, _ = IPAddress.objects.filter(pk__in=all_ip_ids).delete()

    prefixes_deleted = 0
    if prefix_ids:
        prefixes_deleted, _ = Prefix.objects.filter(pk__in=prefix_ids).delete()

    return {
        "rules_deleted": rules_deleted,
        "groups_deleted": groups_deleted,
        "zones_deleted": zones_deleted,
        "addresses_deleted": addresses_deleted,
        "vms_deleted": vms_deleted,
        "ip_addresses_deleted": ip_addresses_deleted,
        "prefixes_deleted": prefixes_deleted,
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }
