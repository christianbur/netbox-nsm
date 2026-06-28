#!/usr/bin/env python3
"""Generate NSM portable-schema JSON bundle under netbox_nsm/bundles/builtin/nsm_schema/."""

from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_DIR = ROOT / "netbox_nsm" / "bundles" / "builtin" / "nsm_schema"
BUNDLE_PATH = BUNDLE_DIR / "bundle.json"
TEMPLATES_PATH = ROOT / "netbox_nsm" / "rulebooks" / "templates.py"

_AREA_COLLAPSE = {"source": "srcdst", "destination": "srcdst"}
_IDENT_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_IDENT_COLLAPSE_RE = re.compile(r"_+")

TYPECONFIG_LIST_EXCLUDED_SLUGS = frozenset({"security-object-link"})
TYPECONFIG_SORT_ORDER_BY_SLUG = {
    "security-zone": 10,
    "security-label": 11,
    "security-address": 12,
    "security-address-group": 13,
    "security-service": 20,
    "security-service-group": 21,
    "security-app-network": 22,
    "security-action": 30,
    "security-app-business": 40,
}

TYPECONFIG_SPECS = [
    ("security-zone", "Zones", "{{ name }}"),
    ("security-address", "Addresses", "{{ name }}"),
    ("security-address-group", "Address Groups", "{{ name }}"),
    ("security-label", "Labels", "{{ label_type[0] | upper }}:{{ name }}"),
    ("security-service", "Services", "{{ name }} ({{ protocol }}/{{ port }})"),
    ("security-service-group", "Service Groups", "{{ name }}"),
    ("security-action", "Action", "{{ name | upper }}"),
    ("security-app-business", "Business Apps", "{{ name }}"),
    ("security-app-network", "Network Apps", "{{ name }}"),
]

DEMO_RULEBOOK_SLUG = "security-rb-demo1"
CORE_BUNDLE_EXTRA_TYPE_SLUGS = frozenset({DEMO_RULEBOOK_SLUG})
RULEBOOK_TEMPLATE_GROUP = "NSM Rulebook Templates"
RULEBOOK_GROUP = "NSM Rulebooks"

DEMO_RULEBOOK_SCHEMA_YAML = """schema_version: "1"
types:
  - name: nsm_rb_{{name}}
    slug: nsm_rb_{{name}}
    verbose_name: "{{display_name}}"
    verbose_name_plural: "{{display_name}}"
    description: "{{description}}"
    group_name: NSM Rulebooks
    fields:
      - id: 1
        name: index
        type: integer
        label: Index
        required: true
        weight: 1
        primary: true
      - id: 2
        name: status
        type: boolean
        label: Status
        required: false
        weight: 2
      - id: 3
        name: name
        type: text
        label: Name
        required: true
        weight: 3
      - id: 4
        name: source
        type: multiobject
        label: Source
        required: true
        weight: 11
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
      - id: 5
        name: destination
        type: multiobject
        label: Destination
        required: true
        weight: 21
        is_polymorphic: true
        related_object_types:
          - custom-objects/nsm_zone
      - id: 9
        name: actions
        type: multiobject
        label: Actions
        required: true
        weight: 50
        related_object_type: custom-objects/nsm_action
      - id: 11
        name: description
        type: longtext
        label: Description
        required: false
        weight: 100
    removed_fields: []
"""


def slugify_identifier(value) -> str:
    s = str(value or "").strip().lower()
    s = _IDENT_CLEAN_RE.sub("_", s)
    s = _IDENT_COLLAPSE_RE.sub("_", s).strip("_")
    return s or "x"


def type_slug(base_name: str) -> str:
    ident = slugify_identifier(base_name).replace("_", "-")
    return f"security-{ident}"


def iter_builtin_types(builtin_types):
    for typedef in builtin_types:
        base_slug = slugify_identifier(typedef.get("name", ""))
        raw_areas = typedef.get("areas") or (
            [typedef.get("area")] if typedef.get("area") else []
        )
        areas = []
        for area in raw_areas:
            collapsed = _AREA_COLLAPSE.get(slugify_identifier(area), slugify_identifier(area))
            if collapsed and collapsed not in areas:
                areas.append(collapsed)
        yield typedef, base_slug, type_slug(base_slug), areas


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _config_dict_from_spec(slug: str, display_template: str, areas: list[str]) -> dict:
    return {
        "sort_order": TYPECONFIG_SORT_ORDER_BY_SLUG.get(slug, 0),
        "display_template": display_template,
        "areas": list(areas),
        "links": {
            "linkable": True,
            "inherit_links": False,
            "inherit_stop_on_own": False,
            "allow_virtual_groups": False,
        },
    }


def _default_objects_entries(builtin_types) -> list[dict]:
    entries: list[dict] = []
    for typedef, _base, slug, _areas in iter_builtin_types(builtin_types):
        records = []
        for entry in typedef.get("default_objects") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            record = {"name": name}
            for key, value in (entry.get("field_data") or {}).items():
                record[key] = value
            records.append(record)
        if records:
            entries.append({"type": slug, "records": records})
    return entries


def _build_metadata_types(builtin_types) -> dict:
    areas_by_slug = {
        slug: areas for _td, _base, slug, areas in iter_builtin_types(builtin_types)
    }
    result: dict = {}
    for slug, _label, display_template in TYPECONFIG_SPECS:
        if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
            continue
        cfg = _config_dict_from_spec(
            slug, display_template, areas_by_slug.get(slug, [])
        )
        result[slug] = {"links": cfg["links"]}
    return result


def _build_rule_view_types(builtin_types) -> dict:
    areas_by_slug = {
        slug: areas for _td, _base, slug, areas in iter_builtin_types(builtin_types)
    }
    types: dict = {}
    for slug, _label, display_template in TYPECONFIG_SPECS:
        if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
            continue
        cfg = _config_dict_from_spec(
            slug, display_template, areas_by_slug.get(slug, [])
        )
        rule_view = {
            "sort_order": cfg["sort_order"],
            "display_template": cfg["display_template"],
        }
        if cfg.get("areas"):
            rule_view["areas"] = list(cfg["areas"])
        types[slug] = {"rule_view": rule_view}
    return types


def build_nsm_schema_bundle(builtin_types) -> dict:
    existing = _read_json(BUNDLE_PATH)
    return {
        **existing,
        "types": _merge_core_types(list(existing.get("types") or [])),
        "objects": _merge_core_objects(list(existing.get("objects") or []), builtin_types),
        "metadata": {
            "types": _build_metadata_types(builtin_types),
            "rulebooks": {
                DEMO_RULEBOOK_SLUG: {
                    "rulebook": {
                        "parent_slug": "",
                        "matrix_tab_enabled": True,
                        "row_group_by_col_id": "",
                    },
                    "types": _build_rule_view_types(builtin_types),
                }
            },
        },
    }


def _demo_rulebook_type_def() -> dict:
    return {
        "name": DEMO_RULEBOOK_SLUG,
        "slug": DEMO_RULEBOOK_SLUG,
        "verbose_name": "NSM Demo Zone Matrix",
        "verbose_name_plural": "NSM Demo Zone Matrix",
        "description": "Zone matrix rulebook (250×250 zones). Fill with the NSM Demo Zone Matrix setup job.",
        "group_name": RULEBOOK_GROUP,
        "fields": [
            {
                "id": 1,
                "name": "index",
                "type": "integer",
                "label": "Index",
                "required": True,
                "weight": 1,
                "primary": True,
            },
            {
                "id": 2,
                "name": "status",
                "type": "boolean",
                "label": "Status",
                "required": False,
                "weight": 2,
            },
            {
                "id": 3,
                "name": "name",
                "type": "text",
                "label": "Name",
                "required": True,
                "weight": 3,
            },
            {
                "id": 4,
                "name": "source",
                "type": "multiobject",
                "label": "Source",
                "required": True,
                "weight": 11,
                "is_polymorphic": True,
                "related_object_types": [
                    "custom-objects/security-zone",
                    "custom-objects/security-label",
                    "custom-objects/security-address",
                    "custom-objects/security-address-group",
                ],
            },
            {
                "id": 5,
                "name": "destination",
                "type": "multiobject",
                "label": "Destination",
                "required": True,
                "weight": 21,
                "is_polymorphic": True,
                "related_object_types": [
                    "custom-objects/security-zone",
                    "custom-objects/security-label",
                    "custom-objects/security-address",
                    "custom-objects/security-address-group",
                ],
            },
            {
                "id": 8,
                "name": "services_applications",
                "type": "multiobject",
                "label": "Services & Applications",
                "required": True,
                "weight": 40,
                "is_polymorphic": True,
                "related_object_types": [
                    "custom-objects/security-service",
                    "custom-objects/security-service-group",
                    "custom-objects/security-app-network",
                ],
            },
            {
                "id": 9,
                "name": "actions",
                "type": "multiobject",
                "label": "Actions",
                "required": True,
                "weight": 50,
                "related_object_type": "custom-objects/security-action",
            },
            {
                "id": 10,
                "name": "infos",
                "type": "multiobject",
                "label": "Infos",
                "required": False,
                "weight": 60,
                "related_object_type": "custom-objects/security-app-business",
            },
            {
                "id": 11,
                "name": "description",
                "type": "longtext",
                "label": "Description",
                "required": False,
                "weight": 100,
            },
        ],
        "removed_fields": [],
    }


def _demo_core_object_entries() -> list[dict]:
    return [
        {
            "type": "security-service-group",
            "records": [
                {
                    "name": "G-DNS",
                    "status": "active",
                    "group": ["security-service/DNS-UDP", "security-service/DNS-TCP"],
                }
            ],
        },
        {
            "type": DEMO_RULEBOOK_SLUG,
            "records": [
                {
                    "index": 1,
                    "status": True,
                    "name": "trust-to-untrust-https",
                    "source": ["security-zone/trust"],
                    "destination": ["security-zone/untrust"],
                    "services_applications": ["security-service/HTTPS"],
                    "actions": ["security-action/Permit"],
                    "description": "HTTPS trust → untrust, permit",
                },
                {
                    "index": 2,
                    "status": True,
                    "name": "trust-to-untrust-http",
                    "source": ["security-zone/trust"],
                    "destination": ["security-zone/untrust"],
                    "services_applications": ["security-service/HTTP"],
                    "actions": ["security-action/Permit"],
                    "description": "HTTP trust → untrust, permit",
                },
                {
                    "index": 3,
                    "status": True,
                    "name": "untrust-to-trust-https-deny",
                    "source": ["security-zone/untrust"],
                    "destination": ["security-zone/trust"],
                    "services_applications": ["security-service/HTTPS"],
                    "actions": ["security-action/Deny"],
                    "description": "HTTPS untrust → trust, deny",
                },
                {
                    "index": 4,
                    "status": True,
                    "name": "untrust-to-trust-dns-deny",
                    "source": ["security-zone/untrust"],
                    "destination": ["security-zone/trust"],
                    "services_applications": ["security-service-group/G-DNS"],
                    "actions": ["security-action/Deny"],
                    "description": "DNS untrust → trust, deny",
                },
            ],
        },
    ]


def _merge_core_types(existing_types: list[dict]) -> list[dict]:
    by_slug = {t.get("slug"): t for t in existing_types if isinstance(t, dict)}
    by_slug[DEMO_RULEBOOK_SLUG] = _demo_rulebook_type_def()
    return list(by_slug.values())


def _merge_core_objects(existing_objects: list[dict], builtin_types) -> list[dict]:
    by_type = {
        entry.get("type"): entry
        for entry in (existing_objects or [])
        if isinstance(entry, dict) and entry.get("type")
    }
    generated = _default_objects_entries(builtin_types)
    for entry in generated:
        by_type.setdefault(entry["type"], entry)
    for entry in _demo_core_object_entries():
        by_type[entry["type"]] = entry
    return list(by_type.values())


def main() -> None:
    builtin_mod = _load_module(
        "builtin_types", ROOT / "netbox_nsm" / "objects" / "builtin_types.py"
    )
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_nsm_schema_bundle(builtin_mod.BUILTIN_CUSTOM_TYPES)
    payload.setdefault("bundle_kind", "schema")
    _write_json(BUNDLE_PATH, payload)
    print(f"Wrote {BUNDLE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
