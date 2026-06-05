#!/usr/bin/env python3
"""Export portable schema JSON from builtin_types (canonical, not from DB).

No Django required — imports ``builtin_types`` and ``custom_objects_schema`` directly.

Examples::

    # Host (no Django):
    python3 scripts/export_schema.py -o nsm-schema.json

    # Container (read-only plugin mount — write inside container first):
    docker exec netbox-dev python3 /opt/netbox-nsm/scripts/export_schema.py \\
        -o /tmp/nsm-schema.json
    docker cp netbox-dev:/tmp/nsm-schema.json netbox-nsm/nsm-schema.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def _load_schema_modules():
    """Load schema builder modules without importing netbox_nsm (needs Django)."""
    root = Path(__file__).resolve().parent.parent / "netbox_nsm"

    def _load(name: str, filename: str):
        path = root / filename
        spec = importlib.util.spec_from_file_location(f"netbox_nsm.{name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    builtin = _load("builtin_types", "builtin_types.py")
    schema_mod = _load("custom_objects_schema", "custom_objects_schema.py")
    return builtin.BUILTIN_CUSTOM_TYPES, schema_mod.build_schema_document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        help="Write JSON to this file (default: stdout)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Minified JSON",
    )
    args = parser.parse_args()

    builtin_types, build_schema_document = _load_schema_modules()
    document = build_schema_document(builtin_types)
    text = json.dumps(
        document,
        indent=None if args.compact else 2,
        ensure_ascii=False,
    )
    text += "\n"

    if args.output:
        out_path = Path(args.output)
        try:
            out_path.write_text(text, encoding="utf-8")
        except OSError as exc:
            if exc.errno == 30:  # EROFS
                print(
                    f"Cannot write {out_path}: read-only filesystem "
                    f"(netbox-nsm mount is :ro). Use /tmp in the container:\n"
                    f"  docker exec netbox-dev python3 /opt/netbox-nsm/scripts/export_schema.py "
                    f"-o /tmp/nsm-schema.json",
                    file=sys.stderr,
                )
            raise
        print(f"Wrote {out_path} ({len(document['types'])} types)", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
