"""Pure naming/overlap helpers for IPA bench overlap tests (no data import)."""

from __future__ import annotations

import random

HOSTS_PER_SUBNET = 100
SUBNETS_PER_WIDE = 16
SUBNETS_PER_SUPER = 256

DEFAULT_LEAF_COUNT = 20 * 10 * 10 * HOSTS_PER_SUBNET

ALIAS_STRIDE = 8
OVERLAP_BUCKET_RATIO = 0.075
OVERLAP_ALIAS_STRIDE = 4
OVERLAP_DUP_NAME_STRIDE = 6
BENCH_OVERLAP_SHOWCASE_RULE_COUNT = 20
OVERLAP_DEMO_RULE_COUNT = BENCH_OVERLAP_SHOWCASE_RULE_COUNT

SHOWCASE_ADDR_PICK_MIN = 1
SHOWCASE_ADDR_PICK_MAX = 10
SHOWCASE_GROUP_PICK_MIN = 1
SHOWCASE_GROUP_PICK_MAX = 10
SHOWCASE_COUNT_SEED = 47
_SHOWCASE_ALIAS_DUP_STRIDE = 12

PREFIX_LEN_WIDE = 20
PREFIX_LEN_SUPER = 16

BENCH_DEMO_OCTET1 = 198
BENCH_DEMO_OCTET2_BASE = 18

_BENCH_NET_PREFIX = "bench-net-"
_BENCH_NET_WIDE_PREFIX = "bench-net-wide-"
_BENCH_NET_SUPER_PREFIX = "bench-net-super-"
_BENCH_IP_PREFIX = "bench-ip-"
_BENCH_ALIAS_PREFIX = "bench-alias-"
_BENCH_DUP_PREFIX = "bench-dup-"
_BENCH_GRP_PREFIX = "bench-grp-"
_BENCH_GRP_OVLP_PREFIX = "bench-grp-ovlp-"
_BENCH_RULE_PREFIX = "bench-rule-"
_BENCH_HOST_PREFIX = "bench-host-"
_BENCH_IFACE_PREFIX = "bench-iface-"


def _subnet_prefix_cidr(subnet_idx: int) -> str:
    third = subnet_idx // 256
    fourth = subnet_idx % 256
    return f"{BENCH_DEMO_OCTET1}.{BENCH_DEMO_OCTET2_BASE + third}.{fourth}.0/24"


def _wider_prefix_cidr(block_subnet_idx: int, prefix_len: int) -> str:
    third = block_subnet_idx // 256
    fourth = block_subnet_idx % 256
    return f"{BENCH_DEMO_OCTET1}.{BENCH_DEMO_OCTET2_BASE + third}.{fourth}.0/{prefix_len}"


def _overlap_bucket_leaf_count(leaf_count: int) -> int:
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
    return f"{BENCH_DEMO_OCTET1}.{BENCH_DEMO_OCTET2_BASE + third}.{fourth}.{host_octet}/32"


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
    return f"bench_canonical={canonical_name}; network={network}"


def _group_name(subnet_idx: int) -> str:
    return f"{_BENCH_GRP_PREFIX}{subnet_idx:05d}"


def _grp_ovlp_name(pair_idx: int) -> str:
    return f"{_BENCH_GRP_OVLP_PREFIX}{pair_idx:05d}"


def _showcase_cell_counts(rule_index: int) -> tuple[int, int, int, int]:
    rng = random.Random(SHOWCASE_COUNT_SEED + rule_index * 997)
    return (
        rng.randint(SHOWCASE_ADDR_PICK_MIN, SHOWCASE_ADDR_PICK_MAX),
        rng.randint(SHOWCASE_ADDR_PICK_MIN, SHOWCASE_ADDR_PICK_MAX),
        rng.randint(SHOWCASE_GROUP_PICK_MIN, SHOWCASE_GROUP_PICK_MAX),
        rng.randint(SHOWCASE_GROUP_PICK_MIN, SHOWCASE_GROUP_PICK_MAX),
    )


def _showcase_host_leaf(rule_index: int, *, overlap_leaf_limit: int) -> int:
    return ((rule_index - 6) * 100) % max(1, overlap_leaf_limit)


def _showcase_leaf_for_side_alias_dup(
    rule_index: int,
    side: str,
    overlap_leaf_limit: int,
) -> int:
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
