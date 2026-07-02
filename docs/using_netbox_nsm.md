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

## Bundles

**Security → Configuration → Bundles**

| Step | Content | Action |
|------|---------|--------|
| 1 | NSM Schema (`nsm_schema`) | **Apply** (required) — imports built-in `nsm_*` COTs and syncs bundle `metadata.types` / `metadata.rulebooks` into each type's `comments` (`nsm_config` YAML) |
| 2 | Demo bundles | Optional **RB Demo Zone Matrix**, **RB Demo Zone/Address** (Preview → Apply) |

`nsm_config` is written during bundle apply (`sync_metadata()`). Adjust per-type settings later via **Security → Type Metadata** or the REST API.

Set `setup_allow_destructive_actions: True` in `PLUGINS_CONFIG` to enable the destructive-changes checkbox on Preview/Apply and demo bundle actions.

## Permissions (0.4.5+)

| Area | Permission |
|------|------------|
| Bundles (view) | `netbox_custom_objects.view_customobjecttype` |
| Bundles (apply) | `netbox_custom_objects.add_customobjecttype` **and** `netbox_custom_objects.change_customobjecttype` |
| Type Metadata (view) | `netbox_custom_objects.view_customobjecttype` |
| Type Metadata (add/edit/delete) | `netbox_custom_objects.change_customobjecttype` |
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

Per-type behaviour: `nsm_config` in COT `comments` or **Security → Type Metadata**.

## Security tab & links

On supported NetBox objects (prefix, IP, device, VM, interface, …), the **Security** tab lists linked objects:

1. **+ Assign** — link an NSM object (zone, service, …)
2. **Reverse view** — from an NSM object, all linked hosts and rulebook references

Linked objects render in a NetBox-style `object-list` table (sortable **Name**, paginator). They are grouped into **object-type tabs** (e.g. *COT Aktion*, *Prefix*) with count badges; within a tab, **value pills** (e.g. *Permit* / *Deny*) sub-filter by the object's value. Pagination is server-side, so tabs with 50k+ links load one page at a time. Tab, value, sort, and page selections are kept in the URL (`nsm_lt`, `nsm_lv`, `nsm_lo`, `nsm_lp`, `nsm_pp`).

Rule columns and the tab share the same **type metadata** entries — no separate zone model per product.

### Custom object types

1. Create a COT in **netbox-custom-objects**
2. **Security → Type Metadata → + Add** (matching class, display template, panel flags)
3. Use the type metadata in rulebook fields and the panel

## Rulebooks

**Security → Rulebooks**

- Fields and hierarchy per rulebook (source, destination, service, action, …)
- **Rules** tab: table, grouping, filter (`nsm_q`), matrix view
- **All Rules:** `/plugins/netbox-nsm/rulebooks/0/rules/` (read-only, all rulebooks)
- Rules are COT rows (`nsm_rb_*`), not `netbox_nsm_rule` ORM

Deployed COT rulebooks: `/plugins/netbox-nsm/rulebooks/cot/<slug>/rules/`

## IP Analyzer

- **Applet:** loupe on analyzable objects in rule detail views (merge/diff address trees)
- **Legacy URL:** `/plugins/netbox-nsm/ip-analyzer/` redirects to Object Analyzer
- **UI API:** `GET /plugins/netbox-nsm/api/ip-analyzer/` (HTML fragments for the applet)
- **REST API:** `GET/POST /api/plugins/netbox-nsm/ip-analyzer/` (JSON)

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
| `/api/plugins/netbox-nsm/nsm-configs/<slug>/` | Read/write Type Metadata (`nsm_config` in COT comments) |
| `/api/plugins/netbox-nsm/object-links/` | Security panel links (`nsm_object_link`) |
| `/api/plugins/netbox-nsm/ip-analyzer/` | Address analysis (JSON) |

Rules and policy objects: **netbox-custom-objects** API. Rulebook assignments: `object-links` with `link_type=rulebook`.

Portable schema: `POST /api/plugins/custom-objects/schema/apply/` with `netbox_nsm/schema/nsm_portable_schema.json`.

## Demos

| Demo | Creates | Trigger |
|------|---------|---------|
| **NSM Schema** | Built-in `nsm_*` COT types, choice sets, seed objects, type metadata | Bundles → `nsm_schema` (Apply) |
| **RB Demo Zone Matrix** | 30×30 zone matrix, 900 rules | Bundles → `nsm_demo_zone_matrix` (Preview → Apply) |
| **RB Demo Zone/Address** | Zones, addresses, groups, 500 rules | Bundles → `nsm_demo_zone_address_adressgroup` (Preview → Apply) |

## Configuration

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "top_level_menu": True,
        "setup_menu": True,
        "setup_allow_destructive_actions": False,
        "menu_label": "Security",
        "panel_label": "Security",
        "bundle_paths": [],
        "builtin_bundles": True,
    },
}
```

| Key | Purpose |
|-----|---------|
| `top_level_menu` | Show the top-level **Security** (or `menu_label`) sidebar menu |
| `setup_menu` | Show **Configuration → Bundles** and allow `/bundles/` URLs |
| `setup_allow_destructive_actions` | Enable destructive-changes checkbox on bundle Preview/Apply and demo actions |
| `menu_label` | Top-level menu title (default: Security) |
| `panel_label` | Security tab title on NetBox objects (default: same as menu or Security) |
| `bundle_paths` | Extra directories for custom JSON bundles; same slug **overrides** a built-in bundle |
| `builtin_bundles` | Include bundles shipped with the plugin under `bundles/builtin/` (default: True) |
| `address_name_templates` | Optional Jinja2 naming rules for `nsm_address` (see [address_name_templates.md](address_name_templates.md)) |
| `address_group_name_templates` | Optional Jinja2 naming rules for `nsm_address_group` (same doc) |

Custom bundle layout per directory: flat `my_bundle.json` (slug = filename) or `my_bundle/bundle.json`.

Built-in bundles load automatically when `builtin_bundles` is True — you do **not** need to add `bundles/builtin` to `bundle_paths`. Use `bundle_paths` for additional directories only, e.g.:

```python
"bundle_paths": ["/opt/netbox/custom-bundles"],
```

Restart NetBox after changes.

## Menu

```
Security
├── Configuration → Bundles, Type Metadata, Object Report
├── Rulebooks
└── Analysis → Object Analyzer

Custom Objects → NSM (Zones, Addresses, …)
```

## See also

- [DATABASE.md](DATABASE.md) — tables
- [RULE_DATA_STORAGE.md](RULE_DATA_STORAGE.md) — storage layers
- [object_report.md](object_report.md) — daily object report
- [ARCHITECTURE.md](../ARCHITECTURE.md) — code
