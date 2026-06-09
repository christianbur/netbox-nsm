#!/usr/bin/env python3
"""Bench scale data — NOT registered in Setup wizard.

Creates nested ``nsm_address`` hosts (200k by default) and COT policy rules on
``nsm_rb_bench_addresses`` (template 0002 — addresses only).

Ausführung (im Verzeichnis ``docker/netbox_dev``)::

    # Vollständiger Lauf (lange Laufzeit; 200k Adressen + 13k Regeln)
    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

    # Nur Regeln (Adressen bereits vorhanden)
    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py --skip-addresses

    # Smoke-Test
    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \\
        --leaf-count 1000 --rule-count 100

    # Bench-Daten entfernen
    docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py --purge

Voraussetzungen: NetBox + netbox-custom-objects + netbox-nsm; Setup → Import all types
und Create all TypeConfigs (oder Starter-Demo). Container ``netbox`` muss laufen;
``./netbox-nsm`` wird nach ``/opt/netbox-nsm`` gemountet.
"""

from __future__ import annotations

import argparse
import sys

import django_bootstrap

django_bootstrap.setup()

from netbox_nsm.demos.addresses_million_scale import (  # noqa: E402
    DEFAULT_LEAF_COUNT,
    DEFAULT_RULEBOOK_SLUG,
    DEFAULT_RULE_COUNT,
    create_addresses_million_scale,
    purge_bench_data,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bench: nested nsm_address hosts + COT rules (standalone, not Setup)."
    )
    parser.add_argument(
        "--rulebook-slug",
        default=DEFAULT_RULEBOOK_SLUG,
        help=f"Target COT rulebook slug (default: {DEFAULT_RULEBOOK_SLUG})",
    )
    parser.add_argument(
        "--rulebook-id",
        type=int,
        default=None,
        help="Legacy: resolve rulebook by CustomObjectType pk instead of slug",
    )
    parser.add_argument(
        "--leaf-count",
        type=int,
        default=DEFAULT_LEAF_COUNT,
        help=f"Leaf host address count (default: {DEFAULT_LEAF_COUNT:,})",
    )
    parser.add_argument(
        "--rule-count",
        type=int,
        default=DEFAULT_RULE_COUNT,
        help=f"COT policy rules to create (default: {DEFAULT_RULE_COUNT:,})",
    )
    parser.add_argument(
        "--skip-addresses",
        action="store_true",
        help="Skip address/IPAM creation; use existing bench-ip-* leaves",
    )
    parser.add_argument(
        "--skip-rules",
        action="store_true",
        help="Only create addresses, no rules",
    )
    parser.add_argument(
        "--keep-rules",
        action="store_true",
        help="Do not delete existing bench-rule-* rows before creating",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Delete bench-* rules, addresses, and linked IPAM objects",
    )
    args = parser.parse_args(argv)

    if args.purge:
        summary = purge_bench_data(
            rulebook_id=args.rulebook_id,
            rulebook_slug=args.rulebook_slug,
        )
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
        rulebook_slug=args.rulebook_slug,
        leaf_count=args.leaf_count,
        rule_count=args.rule_count,
        skip_addresses=args.skip_addresses,
        skip_rules=args.skip_rules,
        recreate_rules=not args.keep_rules,
    )
    print(
        f"{summary['rulebook']} ({summary['rulebook_slug']}, pk={summary['rulebook_id']}): "
        f"{summary['leaves']:,} leaves, "
        f"{summary['rules']:,} new rules, "
        f"{summary['object_items']:,} multiobject assignments, "
        f"{summary['elapsed_s']}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
