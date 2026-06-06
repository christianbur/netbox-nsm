#!/usr/bin/env python3
"""Bench scale data — NOT registered in Setup wizard.

Creates nested ``nsm_addresses`` (1M hosts by default) and policy rules on an
existing rulebook (default pk=2, ``Demo - Addresses``).

Examples::

    # Full run (long; 1M rows + 13k rules)
    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

    # Rules only (addresses already present)
    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py --skip-addresses

    # Smaller smoke test
    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \\
        --leaf-count 1000 --rule-count 100

    # Remove bench-* data
    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py --purge
"""

from __future__ import annotations

import argparse
import sys

import django_bootstrap

django_bootstrap.setup()

from netbox_nsm.demos.addresses_million_scale import (  # noqa: E402
    DEFAULT_LEAF_COUNT,
    DEFAULT_RULEBOOK_ID,
    DEFAULT_RULE_COUNT,
    create_addresses_million_scale,
    purge_bench_data,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bench: nested nsm_addresses + rules (standalone, not Setup)."
    )
    parser.add_argument(
        "--rulebook-id",
        type=int,
        default=DEFAULT_RULEBOOK_ID,
        help=f"Target rulebook pk (default: {DEFAULT_RULEBOOK_ID})",
    )
    parser.add_argument(
        "--leaf-count",
        type=int,
        default=DEFAULT_LEAF_COUNT,
        help=f"Leaf address count (default: {DEFAULT_LEAF_COUNT:,})",
    )
    parser.add_argument(
        "--rule-count",
        type=int,
        default=DEFAULT_RULE_COUNT,
        help=f"Policy rules to create (default: {DEFAULT_RULE_COUNT:,})",
    )
    parser.add_argument(
        "--skip-addresses",
        action="store_true",
        help="Skip address/IPAM creation; use existing bench-* leaves",
    )
    parser.add_argument(
        "--skip-rules",
        action="store_true",
        help="Only create addresses, no rules",
    )
    parser.add_argument(
        "--keep-rules",
        action="store_true",
        help="Do not delete existing bench-* rules before creating",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Delete bench-* rules, addresses, and linked IPAM objects",
    )
    args = parser.parse_args(argv)

    if args.purge:
        summary = purge_bench_data(rulebook_id=args.rulebook_id)
        print(
            "Purged bench data: "
            f"{summary['rules_deleted']} rules, "
            f"{summary['addresses_deleted']} address rows, "
            f"{summary['prefixes_deleted']} prefixes, "
            f"{summary['ip_addresses_deleted']} IP addresses "
            f"({summary['elapsed_s']}s)"
        )
        return 0

    summary = create_addresses_million_scale(
        rulebook_id=args.rulebook_id,
        leaf_count=args.leaf_count,
        rule_count=args.rule_count,
        skip_addresses=args.skip_addresses,
        skip_rules=args.skip_rules,
        recreate_rules=not args.keep_rules,
    )
    print(
        f"{summary['rulebook']} (pk={summary['rulebook_id']}): "
        f"{summary['leaves']:,} leaves, "
        f"{summary['rules']:,} new rules, "
        f"{summary['object_items']:,} rule object items, "
        f"{summary['elapsed_s']}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
