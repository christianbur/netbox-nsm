#!/usr/bin/env python3
"""Dump or validate bundled portable schema files for netbox-custom-objects.

Canonical sources (edit these, then run Setup):

* ``netbox_nsm/schema/nsm_portable_schema.json``
* ``netbox_nsm/schema/nsm_choice_sets.json``

Examples::

    python3 scripts/export_schema.py
    python3 scripts/export_schema.py -o /tmp/nsm_portable_schema.json
    python3 scripts/export_schema.py --validate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "netbox_nsm" / "schema" / "nsm_portable_schema.json"
CHOICE_SETS_PATH = ROOT / "netbox_nsm" / "schema" / "nsm_choice_sets.json"


def _load_document() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _validate(document: dict) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != "1":
        errors.append("schema_version must be '1'")
    types = document.get("types")
    if not isinstance(types, list) or not types:
        errors.append("types must be a non-empty array")
        return errors

    slugs: set[str] = set()
    for type_def in types:
        slug = type_def.get("slug")
        if not slug:
            errors.append("type missing slug")
            continue
        if slug in slugs:
            errors.append(f"duplicate slug: {slug}")
        slugs.add(slug)
        if type_def.get("name") != slug:
            errors.append(f"{slug}: name must match slug")

        field_ids: set[int] = set()
        for field_def in type_def.get("fields", []):
            field_id = field_def.get("id")
            if field_id in field_ids:
                errors.append(f"{slug}: duplicate field id {field_id}")
            field_ids.add(field_id)

    choice_sets = json.loads(CHOICE_SETS_PATH.read_text(encoding="utf-8"))
    available = {row["name"] for row in choice_sets}
    for type_def in types:
        for field_def in type_def.get("fields", []):
            cs = field_def.get("choice_set")
            if cs and cs not in available:
                errors.append(f"missing choice set: {cs}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        help="Write schema JSON to this file (default: stdout)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Minified JSON",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate bundled schema + choice sets and exit",
    )
    args = parser.parse_args()

    document = _load_document()
    if args.validate:
        errors = _validate(document)
        if errors:
            for err in errors:
                print(f"ERROR: {err}", file=sys.stderr)
            return 1
        print(
            f"OK: {len(document['types'])} types in {SCHEMA_PATH.name}",
            file=sys.stderr,
        )
        return 0

    text = json.dumps(
        document,
        indent=None if args.compact else 2,
        ensure_ascii=False,
    )
    text += "\n"

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(text, encoding="utf-8")
        print(f"Wrote {out_path} ({len(document['types'])} types)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
