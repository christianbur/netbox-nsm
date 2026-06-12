# netbox-nsm — Architecture Reference

[Documentation home](docs/README.md) · [Using netbox-nsm](docs/using_netbox_nsm.md)

This document describes the internal structure of the plugin for developers who want to
understand, extend or contribute to `netbox-nsm`.

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Dependency: netbox-custom-objects](#dependency-netbox-custom-objects)
3. [Data Model](#data-model)
   - [Database tables (PostgreSQL)](#database-tables-postgresql)
   - [COT storage (rules, links, policy objects)](#cot-storage-rules-links-policy-objects)
   - [TypeConfig](#typeconfig)
   - [CotRulebookAssignment](#cotrulebookassignment)
4. [Built-in Types (builtin_types.py)](#built-in-types)
5. [Views](#views)
6. [Template Extensions (Security Panel)](#template-extensions-security-panel)
7. [API](#api)
8. [Navigation](#navigation)
9. [Signals](#signals)
10. [Demo Data](#demo-data)
11. [Testing](#testing)

---

## Front-end dependencies

Rules and Matrix use **server-rendered HTML** (Django templates + plugin JS/CSS). The only
external UI library is **@xyflow/react** for Object Analyzer:

| Library | Views | Notes |
|---|---|---|
| **@xyflow/react 12** | `object_analyzer` | Import map + esm.sh in `object_analyzer.html` |

---

## Repository Layout

```
netbox-nsm/
├── netbox_nsm/
│   ├── api/                  REST API (serializers, views, urls)
│   ├── analyzer/             Object Analyzer helper logic
│   ├── choices/              ActionChoices and other enum values
│   ├── constants/            RULESET_ASSIGNMENT_MODELS etc.
│   ├── demos/
│   │   └── enterprise_dc/    Enterprise DC import script
│   ├── fields/               Custom Django form/model fields
│   ├── filtersets/           Django-filter FilterSets for all models
│   ├── forms/                ModelForms for all models
│   ├── graphql/              GraphQL types (auto-generated via NetBox helpers)
│   ├── locale/               Translations (en / de)
│   ├── migrations/           Database migrations
│   ├── mixins/               Shared view/model mixins
│   ├── models/               All Django models (see Data Model section)
│   ├── serializers/          Standalone serializers (not under api/)
│   ├── signals/              post_save / post_delete signal handlers
│   ├── static/               CSS and JS assets
│   ├── tables/               django-tables2 Table classes
│   ├── templates/            HTML templates
│   ├── templatetags/         Custom Jinja2 / Django template tags
│   ├── tests/                Integration and unit tests
│   ├── validators/           Custom DRF / Django validators
│   ├── views/                Class-based views
│   ├── apps.py               AppConfig (registers locale path)
│   ├── builtin_types.py      Built-in COT definitions + default objects
│   ├── custom_objects_schema.py  Schema builder for netbox-custom-objects
│   ├── display_utils.py      Object display template rendering helpers
│   ├── group_m2m.py          Shared ``group`` M2M membership helpers (Security Panel + Analyzer)
│   ├── ipam_inheritance.py   Prefix ancestor lookup + inherited nsm_addresses for IPAM objects
│   ├── navigation.py         Plugin menu definition
│   ├── template_content.py   PluginTemplateExtension registrations
│   └── urls.py               URL patterns
├── docs/
│   ├── DATABASE.md           PostgreSQL table reference
│   ├── using_netbox_nsm.md   Operator guide
│   └── img/                  Screenshots for documentation
├── nsm-schema.json           Portable COT schema (apply via API)
├── pyproject.toml
├── README.md
└── ARCHITECTURE.md           ← this file
```

---

## Dependency: netbox-custom-objects

`netbox-nsm` stores its security object data (Zones, Addresses, Labels, Services, Actions)
as **Custom Object Type instances** via the `netbox-custom-objects` plugin.

This means:
- The schemas (field definitions) for these types live in `netbox-custom-objects`.
- `netbox-nsm` only stores links (`ObjectLink`) and configuration (`TypeConfig`).
- The five built-in types are defined in `builtin_types.py` and can be imported/synced via
  the Setup Wizard or `POST /api/plugins/custom-objects/schema/apply/`.

This separation keeps the security data model flexible — you can extend or replace any type
without changing the NSM plugin itself.

---

## Naming

Model and module names do **not** use an `NSM` prefix (the app label `netbox_nsm` is enough).
Legacy rename scripts were removed with the pre-COT archive; use git history if needed.

### Glossary (one language per layer)

| Layer | Convention | Examples |
|-------|------------|----------|
| UI / URL | **Rules** | Tab label „Rules“, route `cot_rulebook_rules`, COT rule rows |
| Domain | **Security rules** (rulebook type) | `RulebookTypeChoices.SECURITY_RULES` |
| Grid stack (Python) | `rulebook_rules_grid_*` | `rulebook_rules_grid_service.py`, `RulebookRulesGridApiView` |
| Grouping (legacy grid) | `rulebook_rules_grouping.py` | `build_rulebook_rules_group_options()` |
| Row-group tabs (COT) | `rules_row_grouping.py` | `build_row_group_tab_summaries()`, `prepare_row_grouping_tab_columns()` |
| Tab context | `rules_tab.py` | `build_cot_rulebook_rules_tab_context()` |
| Grid API paths | `/api/rulebooks/<pk>/rules-grid/` | validate: `…/rules-grid/validate/` |
| Cache keys | `nsm:rulebook_rules_grid:…` | — |
| Grid DOM/CSS (JS) | `nsm-rules-*` | Rules table chrome, profile key `rules` |
| Grouped table data key | `rules_layout` | Column/row scaffold for rules grid |

`all_rules_grid_*` and `matrix_grid_*` names are unchanged (virtual / matrix views).

## Data Model

### Native models (SOLL)

Four Django models owned by `netbox_nsm` form the active domain layer:

| Model | UI title | Purpose |
|-------|----------|---------|
| `CotRulebookAssignment` | Rulebook Assignment | Assign a COT rulebook to Device / VM / VDC |
| `NsmUiSettings` | NSM UI Settings | Singleton menu/panel labels and Setup menu flags |
| `Section` | NSM Section | Logical grouping of Custom Object Types (source, destination, …) |
| `TypeConfig` | Type Config | Per-ContentType NSM behaviour (panel, matching class, display) |

Policy object **instances**, rulebook **rules**, and Security Panel **links** are stored as
Custom Object Types (`netbox-custom-objects`), not as native NSM tables. The canonical link
COT is `nsm_object_link` (native `ObjectLink` was removed in migration `0004`).

Legacy `ObjectGroup`, `ObjectGroupMember`, `PropertyType`, `PropertyField`, and `Property`
tables were removed in migration `0005_remove_legacy_object_and_property_models`. Group
membership and policy objects use COT `group` M2M fields and Custom Object Types instead.

See `netbox_nsm/models/__init__.py` for the authoritative inline summary.

### Database tables (PostgreSQL)

All NSM-owned rows use the Django app label `netbox_nsm` (tables `netbox_nsm_*`).
Security object **instances**, rulebook **rules**, and panel **links** are stored by
`netbox-custom-objects` (COT), not in native NSM tables — NSM stores configuration,
hierarchy metadata, and generic assignments.

| UI / concept | Storage |
|--------------|---------|
| Rulebook hierarchy / matrix / grouped rows | COT `comments` (`nsm_config.rulebook`) |
| Rulebook assignment to host | `netbox_nsm_cotrulebookassignment` |
| Type behaviour | `netbox_nsm_typeconfig` |
| Rule rows / cell objects | COT tables per `nsm_rb_*` slug |
| Panel links | COT `nsm_object_link` |
| Group membership | COT `group` M2M on Custom Objects |

Full table list, removed legacy tables, migrations, and SQL examples: **[docs/DATABASE.md](docs/DATABASE.md)**.

---

### COT storage (rules, links, policy objects)

Policy **instances**, **rule rows**, and Security Panel **links** are Custom Object Type rows
managed by `netbox-custom-objects`. NSM does not define Django models for them.

| COT slug | Purpose |
|----------|---------|
| `nsm_zone`, `nsm_address`, `nsm_label`, `nsm_service`, `nsm_action`, … | Built-in policy object types (`builtin_types.py`) |
| `nsm_object_link` | Bidirectional Security Panel link between two NetBox objects |
| `nsm_rb_<name>` | Deployed rulebook — one COT per rulebook; each **rule** is a COT row |

**Rulebook schema** (columns, allowed object types per cell) is defined as COT **fields** on the
`nsm_rb_*` type — see `rulebooks/templates.py` (`_FIELD_CATALOG`, `build_rulebook_document()`).
Applying a template calls `POST /api/plugins/custom-objects/schema/apply/`.

**Rule cell contents** are `multiobject` (polymorphic) COT fields on each rule row, e.g.
`source`, `destination`, `service` — not junction tables in `netbox_nsm_*`.

**Object links** (`nsm_object_link` COT rows) store `object_a`, `object_b`, `propagation`
(`LinkPropagationChoices`: `direct`, `inherit_ipam`, `inherit_group`), and optional comment.
The REST API exposes them as `object-links/` (serializer maps COT rows). Native `ObjectLink`
was removed in migration `0004`.

**Group membership** uses COT `group` M2M fields on custom objects, not native
`ObjectGroup` tables (removed in `0005`).

See [RULE_DATA_STORAGE.md](docs/RULE_DATA_STORAGE.md) for the layer model and
[DATABASE.md](docs/DATABASE.md) for table inventory.

---

### TypeConfig

```
TypeConfig (NetBoxModel)
├── name                   (CharField)
├── content_type           (FK → ContentType)
├── matching_class         (CharField — MatchingClassChoices)
├── display_template       (CharField, default: "{name}")
├── allow_virtual_groups   (BooleanField)
├── inherit_links          (BooleanField)
├── inherit_stop_on_own    (BooleanField)
└── panel_linkable_types   (JSONField — allowed host types for + Assign; [] = all)
```

**Purpose:** Per-ContentType configuration for NSM panels, rulebook columns, and display.
Unique together: `(content_type, matching_class)`.

`matching_class` values include `address`, `zone`, `label`, `service`, `action`, `info`,
`user`, `application`, `group`, `other`.

`display_template` is evaluated in `display_utils.render_object_display()`.

`panel_linkable_types` replaces the legacy `panel_linkable` boolean: empty list means all host
types may assign this NSM type from the Security Panel; `[0]` disables linking.

`inherit_links` / `inherit_stop_on_own` drive IPAM inheritance in `ipam_inheritance.py` and the
Security Panel extension. See `docs/DATABASE.md`.

---

### Rulebook metadata (`nsm_config.rulebook`)

Deployed COT rulebooks (`nsm_rb_*`) store NSM-specific UI metadata in the
`CustomObjectType.comments` field as a YAML `nsm_config` list entry:

```yaml
nsm_config:
  - rulebook:
      parent_slug: nsm_rb_global
      matrix_tab_enabled: true
      row_group_by_col_id: destination_zones::ct_2
```

Parsed and written by `netbox_nsm/objects/rulebook_config.py`. Defaults:
`parent_slug=""`, `matrix_tab_enabled=true`, `row_group_by_col_id=""`.

---

### CotRulebookAssignment

```
CotRulebookAssignment (NetBoxModel)
├── assigned_object_type  (FK → ContentType, limited to RULESET_ASSIGNMENT_MODELS)
├── assigned_object_id    (PositiveBigIntegerField)
├── assigned_object       (GenericForeignKey)
├── cot_slug              (SlugField — nsm_rb_* rulebook)
└── description           (CharField, optional)
```

`RULESET_ASSIGNMENT_MODELS` limits assignments to `dcim.Device`,
`dcim.VirtualDeviceContext`, `virtualization.VirtualMachine`.

Unique: `(assigned_object_type, assigned_object_id, cot_slug)`.

---

## Built-in Types

`builtin_types.py` defines the five NSM Custom Object Types as Python data structures:

| Slug | Purpose | Default objects |
|---|---|---|
| `nsm_zones` | Security zones | — |
| `nsm_addresses` | Address objects (subnet-based) | — |
| `nsm_labels` | Arbitrary labels / tags | — |
| `nsm_services` | Port/protocol service definitions | 33 built-in services (HTTP, HTTPS, SSH, DNS-UDP, …) |
| `nsm_action` | Policy actions | Permit (#28a745), Deny (#dc3545), Drop (#6c757d) |

These are synced to the database via `custom_objects_schema.py` which builds the
`netbox-custom-objects` API payload and calls
`POST /api/plugins/custom-objects/schema/apply/`.

---

## Views

| Module | View(s) | URL prefix |
|---|---|---|
| `views/setup/view.py` | `SetupView` | `setup/` |
| `views/type_config.py` | TypeConfig CRUD | `type-config/` |
| `rulebooks/views/list.py` | Rulebook list (COT registry) | `rulebooks/` |
| `rulebooks/views/cot.py` | COT rulebook detail, rules tab, matrix | `rulebooks/cot/<slug>/` |
| `rulebooks/views/cot_rule.py` | Add / edit / delete COT rules | `rulebooks/cot/<slug>/rules/…` |
| `rulebooks/views/virtual_all.py` | All Rules (read-only aggregate) | `rulebooks/0/rules/` |
| `rulebooks/views/assignment.py` | CotRulebookAssignment CRUD | `rulebook-assignment/` |
| `views/object_link.py` | CRUD for COT `nsm_object_link` | `object-link/` |
| `views/ip_analysis.py` | `IPAnalysisView` | `ip-analysis/` |
| `views/object_analyzer.py` | `ObjectAnalyzerView` | `object-analyzer/` |
| `views/setup/demo.py` | Demo rulebooks (imports COTs/TypeConfigs if needed) | Setup POST |
| `views/custom_objects_sync.py` | Sync helper (manual trigger) | `setup/sync/custom-objects/` |
| `views/inherited_links_api.py` | Internal JSON API for inherited links | `api/inherited-links/` |
| `security/views/object_rules_api.py` | Internal JSON API for rule lookup | `api/object-rules/` |

The `SetupView` POST handler dispatches on the `action` form field:

| action value | Effect |
|---|---|
| `import_type_<slug>` | Import single COT |
| `import_all_types` | Import all built-in COTs |
| `create_typeconfig_<slug>` | Create TypeConfig for one COT |
| `create_all_typeconfigs` | Create all TypeConfigs |
| `create_demo_starter` | Zone Matrix + Addresses rulebooks (imports COTs/TypeConfigs if needed) |
| `create_demo_enterprise` | Run Enterprise DC import (blocked if IPs exist) |
| `create_demo_scale` | `Demo - Scale Test` — 300 zones, 12 000 rules |
| `create_demo_addresses_scale` | `Demo - Addresses` — 6 000 address-based rules |

**Not in Setup:** `scripts/create_addresses_million_scale.py` — bench load (200k nested
`nsm_addresses`, 13k rules). See [docs/bench_addresses_million_scale.md](docs/bench_addresses_million_scale.md).

All demo actions call `_ensure_demo_prerequisites()` (imports missing COTs **and** TypeConfigs).

---

## Template Extensions (Security Panel)

Registered in `template_content.py` as `template_extensions = [...]`:

| Class | Models | What it renders |
|---|---|---|
| `NsmSecurityLinksExtension` | `None` (all models) | Security panel (right column): ObjectLinks, group M2M membership, nsm_addresses FK refs, rule references, rulebook assignments (devices/VMs), inheritance |

### Security Panel Link Sources

`NsmSecurityLinksExtension.right_page()` builds link groups from several sources:

1. **COT `nsm_object_link`** rows (forward and reverse) — explicit NSM assignments with edit/delete actions.
2. **nsm_addresses FK** — Custom Object rows pointing at this IPAM object via `prefix_id`, `ip_address_id`, or `range_id`.
3. **group M2M** — via `group_m2m.iter_group_m2m_relations()` (parent groups as *Member of*, contained objects as *Member*).
4. **Inherited links** — resolved at page load for IPAddress, IPRange, and Prefix (via `iter_inherited_nsm_links`).

Header actions: **Object Analyzer** (all objects), **IP Analysis** loupe overlay (address-matching TypeConfig only), **Assign** (ObjectLink picker).

#### Macro vs micro zones (operational convention)

NSM stores every zone as the same `nsm_zones` Custom Object type. **Macro** and **micro** zone
are not separate models or TypeConfigs — operators express them by assigning **multiple direct
zone ObjectLinks** to one host (typically a Prefix or Interface). A macro zone (e.g. `prod`)
documents DC/trust segmentation; a micro zone (e.g. `app-x`) documents application-level
segmentation inside that macro context. The Security Panel lists each link as its own row under
**Zones**; the zone object's reverse panel aggregates every linked Prefix, Device, Interface,
and VM. Inheritance from parent Prefixes (see below) applies to macro assignments at subnet
level; micro zones are usually direct on Interfaces or specific prefixes.

#### Extensible object types (TypeConfig)

Rule columns and Security Panel assignments both flow through **TypeConfig** → ContentType.
Built-in COTs ship with TypeConfigs from Setup; additional types are added by creating a
Custom Object Type (`netbox-custom-objects`) and a matching TypeConfig, then extending the
rulebook COT schema (`multiobject` fields / `related_object_types`). No NSM code changes
required for a new security object class when using polymorphic columns.

### Inheritance Resolution

Inherited links are computed at page load (same `iter_inherited_nsm_links` logic as the API). The panel merges them into
the type groups with a `(from <prefix>)` suffix. The JSON endpoint `inherited-links/` remains for API consumers; the client no longer fetches
`GET /plugins/netbox-nsm/api/inherited-links/?ct_id=&obj_id=` on demand.

For a child IPAM object (IP Address, IP Range, sub-Prefix), `ipam_inheritance.ancestor_prefixes_for_ipam()` finds
containing Prefixes (most-specific first). IP Ranges require a Prefix that contains **both** start and end address.
The API then collects `nsm_object_link` rows and inherited `nsm_addresses` FK rows from those ancestors, respecting per-TypeConfig
`inherit_links` and `inherit_stop_on_own` settings.

---

## API

REST API modules under `netbox_nsm/api/`:

```
api/
├── ip_analysis.py           IpAnalysisRestApiView (address resolution, JSON)
├── serializers_/
│   ├── type_config.py       TypeConfigSerializer
│   ├── cot_rulebook_assignment.py
│   ├── object_link.py       ObjectLinkSerializer (COT nsm_object_link rows)
│   └── section.py
├── serializers.py           Re-exports from serializers_/
├── views.py                 ModelViewSet subclasses + API root
└── urls.py                  Router + ip-analysis/ path
```

| Endpoint | Auth | Purpose |
|---|---|---|
| `type-configs/` | Token | TypeConfig CRUD |
| `object-links/` | Token | Security Panel links (COT `nsm_object_link`) |
| `rulebook-assignments/` | Token | CotRulebookAssignment CRUD |
| `ip-analysis/` | Token | IP tree merge/diff for IPAM + analyzable address objects |

There are **no** REST endpoints for COT rulebook rules or policy object instances — use
`netbox-custom-objects` for those. IP Analysis REST accepts generic `content_type` + `id`
references only; it does not add COT-specific routes.

The UI plugin API at `/plugins/netbox-nsm/api/ip-analysis/` shares
`analysis/ip_analysis_service.py` but returns HTML for the Security Panel applet.

The `ObjectLinkSerializer` uses a `ContentTypeField` (writable, accepts
`"app_label.model"` strings) and validates uniqueness at the COT row level.

---

## Navigation

`navigation.py` uses a `DynamicPluginMenu` wrapper around NetBox's `PluginMenu` to defer
group construction until request time.

Menu structure (when `top_level_menu=True`):

```
NSM
├── Configuration
│   ├── Setup
│   └── Type Config
├── Rulebooks
└── Analysis
    └── Object Analyzer    → `/plugins/netbox-nsm/object-analyzer/`

IP Analysis: Security Panel loupe overlay or `/plugins/netbox-nsm/ip-analysis/` (not in menu).
```

---

## Signals

`signals/` contains `post_save` / `post_delete` handlers that keep derived data consistent,
e.g. invalidating cached display templates when a TypeConfig changes.

---

## Demo Data

`demos/enterprise_dc/import.py` is a self-contained Python script executed via
`exec()` in `_run_enterprise_demo()`. It uses `get_or_create` throughout and prints a
progress summary to stdout (captured by the view).

Pre-conditions checked at the top of the script:
- All five NSM COT types exist in the database
- TypeConfigs exist for all five types

If either check fails, the script exits with a descriptive error message.

---

## Testing

Integration and unit tests live under `netbox_nsm/tests/` (~400 cases). Run them via NetBox’s Django test runner — not pytest.

See **[docs/TESTING.md](docs/TESTING.md)** for dev-container commands, CI parity, and Black.
