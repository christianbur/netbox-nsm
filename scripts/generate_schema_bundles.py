#!/usr/bin/env python3
"""Generate NSM portable-schema JSON bundles under netbox_nsm/bundles/builtin/."""

from __future__ import annotations

import importlib.util
import json
import re
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILTIN_DIR = ROOT / "netbox_nsm" / "bundles" / "builtin"
SCHEMA_BUNDLE_PATH = BUILTIN_DIR / "nsm_schema.json"
ZONE_MATRIX_BUNDLE_PATH = BUILTIN_DIR / "nsm_demo_zone_matrix.json"
ADDRESS_BUNDLE_PATH = BUILTIN_DIR / "nsm_demo_zone_address_adressgroup.json"

DEMO_MATRIX_GRID_SIZE = 30
DEMO_MATRIX_ACTION_SEED = 7
DEMO_ADDR_ZONE_COUNT = 20
DEMO_ADDR_HOST_COUNT = 500
DEMO_ADDR_GROUP_COUNT = 100
DEMO_ADDR_GROUP_MEMBER_COUNT = 5
DEMO_ADDR_RULE_COUNT = 500
DEMO_ADDR_SHOWCASE_RULE_COUNT = 20
DEMO_ADDR_SHOWCASE_ITEM_MIN = 1
DEMO_ADDR_SHOWCASE_ITEM_MAX = 20
DEMO_ADDR_SHOWCASE_COUNT_SEED = 17

_AREA_COLLAPSE = {"source": "srcdst", "destination": "srcdst"}
_IDENT_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_IDENT_COLLAPSE_RE = re.compile(r"_+")

TYPECONFIG_LIST_EXCLUDED_SLUGS = frozenset({"nsm_object_link"})

# Canonical metadata defaults — written into bundle JSON only (not runtime Python).
BUNDLE_ROLE_BY_SLUG = {
    "nsm_zone": "zone",
    "nsm_address": "address",
    "nsm_address_custom": "address",
    "nsm_address_group": "address_group",
    "nsm_label": "label",
    "nsm_service": "service",
    "nsm_service_group": "service_group",
    "nsm_action": "action",
    "nsm_app_business": "app_business",
    "nsm_app_network": "app_network",
    "nsm_object_link": "object_link",
}
BUNDLE_MENU_BY_ROLE = {
    "zone": "objects",
    "address": "objects",
    "address_group": "objects",
    "label": "objects",
    "service": "objects",
    "service_group": "objects",
    "action": "objects",
    "app_business": "objects",
    "app_network": "objects",
    "object_link": "links",
    "rulebook": "rulebooks",
}
BUNDLE_SORT_ORDER_BY_SLUG = {
    "nsm_zone": 10,
    "nsm_label": 11,
    "nsm_address": 12,
    "nsm_address_custom": 13,
    "nsm_address_group": 14,
    "nsm_service": 20,
    "nsm_service_group": 21,
    "nsm_app_network": 22,
    "nsm_action": 30,
    "nsm_app_business": 40,
    "nsm_object_link": 50,
}

SERVICE_DISPLAY_TEMPLATE = (
    "{{ name }} ({{ protocol }}/{% if port_end and port_end != port %}"
    "{{ port }}-{{ port_end }}{% elif port %}{{ port }}{% else %}—{% endif %})"
)

TYPECONFIG_SPECS = [
    ("nsm_zone", "Zones", "{{ name }}"),
    ("nsm_address", "Addresses", "{{ name }}"),
    ("nsm_address_custom", "Addresses Custom", "{{ name }}"),
    ("nsm_address_group", "Address Groups", "{{ name }}"),
    ("nsm_label", "Labels", "{{ label_type[0] | upper }}:{{ name }}"),
    ("nsm_service", "Services", SERVICE_DISPLAY_TEMPLATE),
    ("nsm_service_group", "Service Groups", "{{ name }}"),
    ("nsm_action", "Action", "{{ name | upper }}"),
    ("nsm_app_business", "Business Apps", "{{ name }}"),
    ("nsm_app_network", "Network Apps", "{{ name }}"),
]

SCHEMA_DEMO_RULEBOOK_SLUG = "nsm_rb_demo_rulebook"
DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG = "nsm_rb_demo_zone_addresses"
DEMO_ZONE_MATRIX_RULEBOOK_SLUG = "nsm_rb_demo_zone_matrix"


def slugify_identifier(value) -> str:
    s = str(value or "").strip().lower()
    s = _IDENT_CLEAN_RE.sub("_", s)
    s = _IDENT_COLLAPSE_RE.sub("_", s).strip("_")
    return s or "x"


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
        yield typedef, base_slug, f"nsm_{base_slug.replace('-', '_')}", areas


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path):
    if not path.is_file():
        legacy = BUILTIN_DIR / path.stem / "bundle.json"
        if legacy.is_file():
            path = legacy
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _config_dict_from_spec(slug: str, display_template: str, areas: list[str]) -> dict:
    return {
        "sort_order": BUNDLE_SORT_ORDER_BY_SLUG.get(slug, 0),
        "display_template": display_template,
        "areas": list(areas),
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


def _build_link_table_metadata(builtin_types) -> dict:
    """``link_table`` flags from builtin typedefs (e.g. ``nsm_object_link``)."""
    result: dict = {}
    for typedef, _base, slug, _areas in iter_builtin_types(builtin_types):
        if typedef.get("link_table"):
            result[slug] = {"link_table": True}
    return result


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
        role = BUNDLE_ROLE_BY_SLUG.get(slug)
        entry: dict = {}
        if role:
            entry["role"] = role
            menu = BUNDLE_MENU_BY_ROLE.get(role)
            if menu:
                entry["menu"] = menu
        rule_view = {
            "sort_order": cfg["sort_order"],
            "display_template": cfg["display_template"],
        }
        if cfg.get("areas"):
            rule_view["areas"] = list(cfg["areas"])
        entry["rule_view"] = rule_view
        result[slug] = entry
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
    return _compact_rulebook_types_map(types, areas_by_slug)


def _default_rule_view_for_slug(
    slug: str,
    display_template: str,
    areas: list[str],
) -> dict:
    rule_view = {
        "sort_order": BUNDLE_SORT_ORDER_BY_SLUG.get(slug, 0),
        "display_template": display_template,
    }
    if areas:
        rule_view["areas"] = list(areas)
    return rule_view


def _compact_rulebook_types_map(types_map: dict, areas_by_slug: dict) -> dict:
    """Keep only rulebook type entries whose rule_view differs from bundled defaults."""
    display_by_slug = {
        slug: display_template for slug, _label, display_template in TYPECONFIG_SPECS
    }
    result: dict = {}
    for slug, block in (types_map or {}).items():
        if not isinstance(block, dict):
            continue
        areas = areas_by_slug.get(slug, [])
        default = _default_rule_view_for_slug(
            slug,
            display_by_slug.get(slug, "{{ name }}"),
            areas,
        )
        rule_view = block.get("rule_view") or {}
        if rule_view == default:
            continue
        diff = {}
        for key in ("sort_order", "display_template", "areas"):
            if rule_view.get(key) != default.get(key):
                diff[key] = rule_view[key]
        if diff:
            result[slug] = {"rule_view": diff}
    return result


def _rulebook_metadata_block(
    *,
    rulebook_cfg: dict,
    rule_view_types: dict,
) -> dict:
    block = {
        "rulebook": rulebook_cfg,
        "role": "rulebook",
        "menu": "rulebooks",
        "rule_view": {
            "sort_order": 0,
            "display_template": "{{ name }}",
        },
    }
    if rule_view_types:
        block["types"] = rule_view_types
    return block


def _load_templates_module():
    return _load_module(
        "rulebook_templates",
        ROOT / "netbox_nsm" / "rulebooks" / "templates.py",
    )


def _schema_demo_rulebook_type_def(templates_mod) -> dict:
    type_def = templates_mod.parse_rulebook_schema_yaml(
        templates_mod.schema_demo_rulebook_schema_yaml()
    )
    type_def["name"] = SCHEMA_DEMO_RULEBOOK_SLUG
    type_def["slug"] = SCHEMA_DEMO_RULEBOOK_SLUG
    return type_def


def _zone_matrix_rulebook_type_def(templates_mod) -> dict:
    type_def = templates_mod.parse_rulebook_schema_yaml(
        templates_mod.demo_rulebook_schema_yaml()
    )
    type_def["name"] = DEMO_ZONE_MATRIX_RULEBOOK_SLUG
    type_def["slug"] = DEMO_ZONE_MATRIX_RULEBOOK_SLUG
    return type_def


def _demo_matrix_zone_name(zone_idx: int, *, zone_count: int) -> str:
    width = max(2, len(str(zone_count)))
    return f"zone_{zone_idx + 1:0{width}d}"


def _zone_matrix_demo_object_entries() -> list[dict]:
    import random

    grid = DEMO_MATRIX_GRID_SIZE
    zone_count = grid
    rule_count = grid * grid
    act_rng = random.Random(DEMO_MATRIX_ACTION_SEED)
    zone_records = [
        {"name": _demo_matrix_zone_name(i, zone_count=zone_count), "status": "active"}
        for i in range(zone_count)
    ]
    rule_records = []
    for rule_idx in range(rule_count):
        src_i = rule_idx // grid
        dst_i = rule_idx % grid
        src_name = _demo_matrix_zone_name(src_i, zone_count=zone_count)
        dst_name = _demo_matrix_zone_name(dst_i, zone_count=zone_count)
        action = "Permit" if act_rng.random() < 0.5 else "Deny"
        rule_records.append(
            {
                "index": rule_idx + 1,
                "status": True,
                "name": f"demo-rule-{src_name}-to-{dst_name}",
                "source": [f"nsm_zone/{src_name}"],
                "destination": [f"nsm_zone/{dst_name}"],
                "actions": [f"nsm_action/{action}"],
            }
        )
    return [
        {"type": "nsm_zone", "records": zone_records},
        {"type": DEMO_ZONE_MATRIX_RULEBOOK_SLUG, "records": rule_records},
    ]


def _demo_addr_name(prefix: str, index: int, *, total: int) -> str:
    width = max(2, len(str(total)))
    return f"{prefix}-{index + 1:0{width}d}"


def _demo_addr_side_refs(
    rule_index: int,
    side: str,
    *,
    hosts: list[str],
    group_records: list[dict],
    count: int,
) -> list[str]:
    """Build *count* polymorphic address refs (mix of hosts and groups)."""
    import random

    pick_rng = random.Random(
        DEMO_ADDR_SHOWCASE_COUNT_SEED + rule_index * 31 + (7 if side == "src" else 13)
    )
    refs: list[str] = []
    for offset in range(count):
        if rule_index == 1 and side == "dst" and offset == 0:
            refs.append("nsm_address_custom/ANY")
            continue
        if pick_rng.random() < 0.55:
            host_idx = (rule_index * 17 + offset * 3 + (0 if side == "src" else 11)) % len(
                hosts
            )
            refs.append(f"nsm_address/{hosts[host_idx]}")
        elif pick_rng.random() < 0.85:
            group_idx = (rule_index * 5 + offset * 2 + (0 if side == "src" else 7)) % len(
                group_records
            )
            refs.append(f"nsm_address_group/{group_records[group_idx]['name']}")
        else:
            refs.append("nsm_address_custom/ANY")
    return refs


def _zone_address_demo_object_entries() -> list[dict]:
    import random

    zones = [
        _demo_addr_name("demo-addr-zone", i, total=DEMO_ADDR_ZONE_COUNT)
        for i in range(DEMO_ADDR_ZONE_COUNT)
    ]
    hosts = [
        _demo_addr_name("demo-addr-host", i, total=DEMO_ADDR_HOST_COUNT)
        for i in range(DEMO_ADDR_HOST_COUNT)
    ]
    group_records = []
    for group_idx in range(DEMO_ADDR_GROUP_COUNT):
        group_name = _demo_addr_name("demo-addr-group", group_idx, total=DEMO_ADDR_GROUP_COUNT)
        members = [
            f"nsm_address/{hosts[(group_idx * DEMO_ADDR_GROUP_MEMBER_COUNT + offset) % DEMO_ADDR_HOST_COUNT]}"
            for offset in range(DEMO_ADDR_GROUP_MEMBER_COUNT)
        ]
        group_records.append(
            {
                "name": group_name,
                "status": "active",
                "group": members,
            }
        )
    services = ["nsm_service/HTTPS", "nsm_service/HTTP", "nsm_service/DNS-UDP"]
    rng = random.Random(42)
    rule_records = []
    for rule_idx in range(DEMO_ADDR_RULE_COUNT):
        rule_index = rule_idx + 1
        src_zone = zones[rule_idx % DEMO_ADDR_ZONE_COUNT]
        dst_zone = zones[(rule_idx + 3) % DEMO_ADDR_ZONE_COUNT]
        action = "Permit" if rng.random() < 0.5 else "Deny"
        if rule_index <= DEMO_ADDR_SHOWCASE_RULE_COUNT:
            count_rng = random.Random(DEMO_ADDR_SHOWCASE_COUNT_SEED + rule_index * 997)
            src_count = count_rng.randint(
                DEMO_ADDR_SHOWCASE_ITEM_MIN, DEMO_ADDR_SHOWCASE_ITEM_MAX
            )
            dst_count = count_rng.randint(
                DEMO_ADDR_SHOWCASE_ITEM_MIN, DEMO_ADDR_SHOWCASE_ITEM_MAX
            )
            source_addresses = _demo_addr_side_refs(
                rule_index,
                "src",
                hosts=hosts,
                group_records=group_records,
                count=src_count,
            )
            destination_addresses = _demo_addr_side_refs(
                rule_index,
                "dst",
                hosts=hosts,
                group_records=group_records,
                count=dst_count,
            )
        else:
            src_host = hosts[rule_idx % DEMO_ADDR_HOST_COUNT]
            dst_host = hosts[(rule_idx + 7) % DEMO_ADDR_HOST_COUNT]
            src_group = group_records[rule_idx % DEMO_ADDR_GROUP_COUNT]["name"]
            dst_group = group_records[(rule_idx + 2) % DEMO_ADDR_GROUP_COUNT]["name"]
            source_addresses = [
                f"nsm_address/{src_host}",
                f"nsm_address_group/{src_group}",
            ]
            destination_addresses = [
                f"nsm_address/{dst_host}",
                f"nsm_address_group/{dst_group}",
            ]
        rule_records.append(
            {
                "index": rule_index,
                "status": True,
                "name": f"demo-addr-rule-{rule_index:03d}",
                "source_zones": [f"nsm_zone/{src_zone}"],
                "destination_zones": [f"nsm_zone/{dst_zone}"],
                "source_addresses": source_addresses,
                "destination_addresses": destination_addresses,
                "services_applications": [rng.choice(services)],
                "actions": [f"nsm_action/{action}"],
            }
        )
    return [
        {"type": "nsm_zone", "records": [{"name": z, "status": "active"} for z in zones]},
        {"type": "nsm_address", "records": [{"name": h, "status": "active"} for h in hosts]},
        {"type": "nsm_address_group", "records": group_records},
        {"type": DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG, "records": rule_records},
    ]


def _schema_demo_rulebook_object_entries() -> list[dict]:
    def _rule(
        *,
        index: int,
        name: str,
        source_zone: str,
        destination_zone: str,
        service: str,
        action: str,
    ) -> dict:
        return {
            "index": index,
            "status": True,
            "name": name,
            "source_zones": [f"nsm_zone/{source_zone}"],
            "destination_zones": [f"nsm_zone/{destination_zone}"],
            "source_addresses": [],
            "destination_addresses": [],
            "services_applications": [f"nsm_service/{service}"],
            "actions": [f"nsm_action/{action}"],
        }

    return [
        {
            "type": SCHEMA_DEMO_RULEBOOK_SLUG,
            "records": [
                _rule(
                    index=1,
                    name="trust-to-untrust-https",
                    source_zone="trust",
                    destination_zone="untrust",
                    service="HTTPS",
                    action="Permit",
                ),
                _rule(
                    index=2,
                    name="trust-to-untrust-http",
                    source_zone="trust",
                    destination_zone="untrust",
                    service="HTTP",
                    action="Permit",
                ),
                _rule(
                    index=3,
                    name="untrust-to-trust-https-deny",
                    source_zone="untrust",
                    destination_zone="trust",
                    service="HTTPS",
                    action="Deny",
                ),
                _rule(
                    index=4,
                    name="untrust-to-trust-dns-deny",
                    source_zone="untrust",
                    destination_zone="trust",
                    service="DNS-UDP",
                    action="Deny",
                ),
            ],
        }
    ]


def _schema_demo_object_entries() -> list[dict]:
    return [
        {
            "type": "nsm_service_group",
            "records": [
                {
                    "name": "G-DNS",
                    "status": "active",
                    "group": ["nsm_service/DNS-UDP", "nsm_service/DNS-TCP"],
                }
            ],
        }
    ]


def build_nsm_schema_bundle(builtin_types, templates_mod) -> dict:
    existing = _read_json(SCHEMA_BUNDLE_PATH)
    rule_view_types = _build_rule_view_types(builtin_types)
    types = [
        t
        for t in (existing.get("types") or [])
        if isinstance(t, dict)
        and t.get("slug") not in {DEMO_ZONE_MATRIX_RULEBOOK_SLUG, DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG}
    ]
    by_slug = {t.get("slug"): t for t in types if t.get("slug")}
    by_slug[SCHEMA_DEMO_RULEBOOK_SLUG] = _schema_demo_rulebook_type_def(templates_mod)
    types = list(by_slug.values())

    objects = [
        entry
        for entry in (existing.get("objects") or [])
        if isinstance(entry, dict)
        and entry.get("type")
        not in {DEMO_ZONE_MATRIX_RULEBOOK_SLUG, DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG}
    ]
    by_type = {entry.get("type"): entry for entry in objects if entry.get("type")}
    for entry in _default_objects_entries(builtin_types):
        by_type.setdefault(entry["type"], entry)
    for entry in _schema_demo_object_entries():
        by_type[entry["type"]] = entry
    by_type[SCHEMA_DEMO_RULEBOOK_SLUG] = _schema_demo_rulebook_object_entries()[0]
    objects = list(by_type.values())

    return {
        **existing,
        "description": (
            "Required NSM base import: Security Object custom types, choice sets, "
            "default seed objects, and type metadata (links settings, rulebook views). "
            f"Defines {SCHEMA_DEMO_RULEBOOK_SLUG} and sample policy objects."
        ),
        "types": types,
        "objects": objects,
        "metadata": {
            "types": {
                **_build_metadata_types(builtin_types),
                **_build_link_table_metadata(builtin_types),
            },
            "rulebooks": {
                SCHEMA_DEMO_RULEBOOK_SLUG: _rulebook_metadata_block(
                    rulebook_cfg={"parent_slug": ""},
                    rule_view_types=rule_view_types,
                ),
            },
        },
    }




def _zone_addresses_rulebook_type_def(templates_mod) -> dict:
    type_def = templates_mod.parse_rulebook_schema_yaml(
        templates_mod.bench_rulebook_schema_yaml()
    )
    type_def["name"] = DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG
    type_def["slug"] = DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG
    return type_def


def build_zone_address_bundle_payload(builtin_types, templates_mod) -> dict:
    existing = _read_json(ADDRESS_BUNDLE_PATH)
    rule_view_types = _build_rule_view_types(builtin_types)
    return {
        **existing,
        "schema_type": "nsm",
        "schema_version": "1",
        "bundle_kind": "schema",
        "title": existing.get("title") or "RB Demo Zone/Address",
        "description": (
            "Zone, address, and address-group demo on "
            f"{DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG}: "
            f"{DEMO_ADDR_ZONE_COUNT} zones, {DEMO_ADDR_HOST_COUNT} addresses, "
            f"{DEMO_ADDR_GROUP_COUNT} groups, and {DEMO_ADDR_RULE_COUNT} rules "
            f"(rules 1–{DEMO_ADDR_SHOWCASE_RULE_COUNT}: 1–{DEMO_ADDR_SHOWCASE_ITEM_MAX} "
            "addresses/groups per side, rule 1 destination includes nsm_address_custom/ANY; "
            "assigns random IPAM hosts/prefixes to demo addresses on apply). "
            "Requires nsm_schema (ANY seed object)."
        ),
        "requires": ["nsm_schema"],
        "needs_confirm": True,
        "confirm_label": "I confirm that IP addresses and prefixes may be created in IPAM.",
        "types": [_zone_addresses_rulebook_type_def(templates_mod)],
        "objects": _zone_address_demo_object_entries(),
        "metadata": {
            "rulebooks": {
                DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG: _rulebook_metadata_block(
                    rulebook_cfg={"parent_slug": ""},
                    rule_view_types=rule_view_types,
                ),
            }
        },
    }


def build_zone_matrix_bundle_payload(builtin_types, templates_mod) -> dict:
    existing = _read_json(ZONE_MATRIX_BUNDLE_PATH)
    rule_view_types = _build_rule_view_types(builtin_types)
    rule_count = DEMO_MATRIX_GRID_SIZE * DEMO_MATRIX_GRID_SIZE
    return {
        **existing,
        "schema_type": "nsm",
        "schema_version": "1",
        "bundle_kind": "schema",
        "title": existing.get("title") or "RB Demo Zone Matrix",
        "description": (
            f"Zone matrix demo on {DEMO_ZONE_MATRIX_RULEBOOK_SLUG}: "
            f"{DEMO_MATRIX_GRID_SIZE}×{DEMO_MATRIX_GRID_SIZE} zones with "
            f"{rule_count:,} rules (random permit/deny). Apply NSM Schema first."
        ),
        "requires": ["nsm_schema"],
        "types": [_zone_matrix_rulebook_type_def(templates_mod)],
        "objects": _zone_matrix_demo_object_entries(),
        "metadata": {
            "rulebooks": {
                DEMO_ZONE_MATRIX_RULEBOOK_SLUG: _rulebook_metadata_block(
                    rulebook_cfg={
                        "parent_slug": "",
                        "matrix_tab_enabled": True,
                        "row_group_by_col_id": "source::nsm_zone",
                    },
                    rule_view_types=rule_view_types,
                ),
            }
        },
    }


def main() -> None:
    builtin_mod = _load_module(
        "builtin_types", ROOT / "netbox_nsm" / "objects" / "builtin_types.py"
    )
    templates_mod = _load_templates_module()
    schema_payload = build_nsm_schema_bundle(
        builtin_mod.BUILTIN_CUSTOM_TYPES, templates_mod
    )
    schema_payload.setdefault("bundle_kind", "schema")
    _write_json(SCHEMA_BUNDLE_PATH, schema_payload)

    zone_payload = build_zone_matrix_bundle_payload(
        builtin_mod.BUILTIN_CUSTOM_TYPES, templates_mod
    )
    _write_json(ZONE_MATRIX_BUNDLE_PATH, zone_payload)

    address_payload = build_zone_address_bundle_payload(
        builtin_mod.BUILTIN_CUSTOM_TYPES, templates_mod
    )
    _write_json(ADDRESS_BUNDLE_PATH, address_payload)

    print(f"Wrote {SCHEMA_BUNDLE_PATH.relative_to(ROOT)}")
    print(f"Wrote {ZONE_MATRIX_BUNDLE_PATH.relative_to(ROOT)}")
    print(f"Wrote {ADDRESS_BUNDLE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
