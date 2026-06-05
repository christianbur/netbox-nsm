#!/usr/bin/env python3
"""Export portable schema from DB via netbox-custom-objects export_cots.

Requires schema_id on fields — run set_schema_ids.py first if export skips fields.

    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/export_cots_db.py \\
        --slug nsm_action --slug nsm_addresses

    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/export_cots_db.py --all-nsm
"""
from __future__ import annotations

import argparse
import json
import sys

import django_bootstrap

django_bootstrap.setup()

from netbox_custom_objects.models import CustomObjectType
from netbox_custom_objects.schema.exporter import export_cots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slug",
        action="append",
        default=[],
        help="COT slug to export (repeatable)",
    )
    parser.add_argument(
        "--all-nsm",
        action="store_true",
        help="Export all slugs starting with nsm_",
    )
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    if args.all_nsm:
        qs = CustomObjectType.objects.filter(slug__startswith="nsm_").order_by("slug")
    elif args.slug:
        qs = CustomObjectType.objects.filter(slug__in=args.slug).order_by("slug")
    else:
        parser.error("Specify --slug or --all-nsm")
        return 2

    document = export_cots(qs)
    for t in document.get("types", []):
        n_fields = len(t.get("fields") or [])
        if n_fields == 0:
            print(
                f"WARN: {t.get('slug', '?')} has no exported fields "
                f"(schema_id missing?) — run set_schema_ids.py",
                file=sys.stderr,
            )

    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
