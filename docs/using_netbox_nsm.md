# Using netbox-nsm

Documentation plugin — no firewall configuration. Overview: [README](../README.md).

## Prerequisites

```python
PLUGINS = ["netbox_custom_objects", "netbox_nsm"]
```

```bash
./manage.py migrate netbox_custom_objects --no-input
./manage.py migrate netbox_nsm --no-input
```

## Setup wizard

**Security → Configuration → Setup**

| § | Content | Action |
|---|---------|--------|
| 2 | Schema bundles | **Apply** `nsm_schema` (required) — imports built-in `nsm_*` COTs and syncs bundle `metadata.types` / `metadata.rulebooks` into each type's `comments` (`nsm_config` YAML) |
| 3 | Demo | Optional **NSM Demo Zone Matrix** (Python job `nsm_demo_zone_matrix`; `nsm_rb_demo` is included in NSM Schema) |

There is no separate Object Config step in Setup: `nsm_config` is written during bundle apply (`sync_metadata()`). Adjust per-type settings later via **Security → Object Config** or the REST API.

Set `setup_allow_destructive_actions: True` in `PLUGINS_CONFIG` for demos.

## Permissions (0.4.5+)

| Area | Permission |
|------|------------|
| Setup (view) | `netbox_custom_objects.view_customobjecttype` |
| Import COT types | `netbox_custom_objects.add_customobjecttype` |
| Object Config (view) | `netbox_custom_objects.view_customobjecttype` |
| Object Config (add/edit/delete) | `netbox_custom_objects.change_customobjecttype` |
| Rulebook list / rules (per book) | `view` / `change` / `add` / `delete` on that rulebook's COT rule model |
| Create rulebook | `netbox_custom_objects.add_customobjecttype` |
| Security panel links | `add` / `change` / `delete` on `nsm_object_link` COT model |
| Panel row edits (address FK, group M2M) | `change` / `delete` on the affected COT instance model |

Legacy `netbox_nsm.*_typeconfig` and `view_rulebook` / `add_rulebook` permissions are no longer used.

## Built-in COTs

| Slug | Purpose |
|------|---------|
| `nsm_zone` | Security zones |
| `nsm_address` | Addresses |
| `nsm_address_group` | Address groups |
| `nsm_label` | Labels |
| `nsm_service` | Services (port/proto) |
| `nsm_service_group` | Service groups |
| `nsm_action` | Actions (permit, deny, …) |
| `nsm_app_business` | Business apps |
| `nsm_app_network` | Network apps |
| `nsm_object_link` | Security panel and rulebook links |

Per-type behaviour: `nsm_config` in COT `comments` or **Security → Object Config**.

## Security tab & links

On supported NetBox objects (prefix, IP, device, VM, interface, …), the **Security** tab lists linked objects:

1. **+ Assign** — link an NSM object (zone, service, …)
2. **Link type:** direct, inherit to IPAM children, inherit to group members
3. **Reverse view** — from an NSM object, all linked hosts and rulebook references

Linked objects render in a NetBox-style `object-list` table (sortable **Name**, paginator). They are grouped into **object-type tabs** (e.g. *COT Aktion*, *Prefix*) with count badges; within a tab, **value pills** (e.g. *Permit* / *Deny*) sub-filter by the object's value. Pagination is server-side, so tabs with 50k+ links load one page at a time. Tab, value, sort, and page selections are kept in the URL (`nsm_lt`, `nsm_lv`, `nsm_lo`, `nsm_lp`, `nsm_pp`).

Rule columns and the tab share the same **object config** entries — no separate zone model per product.

### Custom object types

1. Create a COT in **netbox-custom-objects**
2. **Security → Object Config → + Add** (matching class, display template, panel flags)
3. Use the object config in rulebook fields and the panel

## Rulebooks

**Security → Rulebooks**

- Fields and hierarchy per rulebook (source, destination, service, action, …)
- **Rules** tab: table, grouping, filter (`nsm_q`), matrix view
- **All Rules:** `/plugins/netbox-nsm/rulebooks/0/rules/` (read-only, all rulebooks)
- Rules are COT rows (`nsm_rb_*`), not `netbox_nsm_rule` ORM

Deployed COT rulebooks: `/plugins/netbox-nsm/rulebooks/cot/<slug>/rules/`

## IP Analysis

- **Applet:** loupe on analyzable objects in rule detail views (merge/diff address trees)
- **Legacy URL:** `/plugins/netbox-nsm/ip-analysis/` redirects to Object Analyzer
- **UI API:** `GET /plugins/netbox-nsm/api/ip-analysis/` (HTML fragments for the applet)
- **REST API:** `GET/POST /api/plugins/netbox-nsm/ip-analysis/` (JSON)

## Object Analyzer

**Security → Analysis → Object Analyzer** — xyflow graph from object to links and rulebooks.

## Object Report

**Security → Configuration → Object Report** — a daily background job audits the NSM
address layer (`nsm_address` / `nsm_address_group`): status vs. linked IPAM status, IPAM
duplicates, orphans, multi-group / empty / single-member / similar groups, deprecated
objects. The latest run is viewable; **Run now** enqueues a fresh run (requires an RQ
worker). Findings export as TOML (`?export=toml`). Sample lists are paginated client-side
(50 per page). Details: [object_report.md](object_report.md).

## REST API

| Endpoint | Purpose |
|----------|---------|
| `/api/plugins/netbox-nsm/nsm-configs/<slug>/` | Read/write `nsm_config` in COT comments |
| `/api/plugins/netbox-nsm/object-links/` | Security panel links (`nsm_object_link`) |
| `/api/plugins/netbox-nsm/ip-analysis/` | Address analysis (JSON) |

Rules and policy objects: **netbox-custom-objects** API. Rulebook assignments: `object-links` with `link_type=rulebook`.

Portable schema: `POST /api/plugins/custom-objects/schema/apply/` with `netbox_nsm/schema/nsm_portable_schema.json`.

## Demos

| Demo | Creates | Trigger |
|------|---------|---------|
| **Starter** | Zones, services, actions + rulebooks “Demo - Zone Matrix”, “Demo - Addresses” | Setup §3, synchronous |
| **Enterprise DC** | DCIM/IPAM scenario + rulebooks | Setup §3, empty IP DB only |
| **Addresses Million Scale** | Bench rulebook `nsm_rb_bench_addresses` | `scripts/create_addresses_million_scale.py`, RQ |

## Configuration

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "top_level_menu": True,
        "setup_menu": True,
        "setup_allow_destructive_actions": False,
        "assignments_menu": False,
        "menu_label": "Security",
        "panel_label": "Security",
        # Optional Jinja2 naming (see docs/address_name_templates.md)
        "address_name_templates": [
            {"template": "h-{ipam>ip}", "match": "host"},
            {"template": "n-{ipam>prefix>network}-{ipam>prefix>cidr}", "match": "prefix"},
        ],
    },
}
```

Restart NetBox after changes.

## Menu

```
Security
├── Configuration → Setup, Object Config, Object Report
├── Rulebooks
└── Analysis → Object Analyzer

Custom Objects → NSM (Zones, Addresses, …)
```

## See also

- [DATABASE.md](DATABASE.md) — tables
- [RULE_DATA_STORAGE.md](RULE_DATA_STORAGE.md) — storage layers
- [object_report.md](object_report.md) — daily object report
- [ARCHITECTURE.md](../ARCHITECTURE.md) — code
