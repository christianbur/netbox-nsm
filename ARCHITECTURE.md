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
   - [ObjectLink](#objectlink)
   - [TypeConfig](#typeconfig)
   - [Rulebook](#rulebook)
   - [RulebookField / RulebookFieldType](#rulebookfield--rulebookfieldtype)
   - [Rule](#rule)
   - [RulebookAssignment](#rulebookassignment)
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

Interactive UI uses two MIT-licensed libraries (no commercial AG Grid Enterprise):

| Library | Views | Notes |
|---|---|---|
| **AG Grid Community 33.2.4** | `rulebook_rules`, `rulebook_matrix`, All Rules grid | Vendored under `plugin_assets/vendor/ag-grid-community/` |
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
See `scripts/drop_nsm_prefix.py` when migrating legacy names.

### Glossary (one language per layer)

| Layer | Convention | Examples |
|-------|------------|----------|
| UI / URL | **Rules** | Tab label „Rules“, route `rulebook_rules`, REST `/rules/` unchanged |
| Domain | **Security rules** (rulebook type) | `RulebookTypeChoices.SECURITY_RULES` |
| Grid stack (Python) | `rulebook_rules_grid_*` | `rulebook_rules_grid_service.py`, `RulebookRulesGridApiView` |
| Grouping | `rulebook_rules_grouping.py` | `build_rulebook_rules_group_options()` |
| Tab context | `rulebook_rules_tab.py` | `build_rulebook_rules_tab_context()` |
| Grid API paths | `/api/rulebooks/<pk>/rules-grid/` | validate: `…/rules-grid/validate/` |
| Cache keys | `nsm:rulebook_rules_grid:…` | — |
| Grid DOM/CSS (JS) | `nsm-rules-*` | `nsm-rules-ag-grid`, profile key `rules` |
| Grouped table data key | `rules_layout` | Column/row scaffold for rules grid |

`all_rules_grid_*` and `matrix_grid_*` names are unchanged (virtual / matrix views).

## Data Model

### Database tables (PostgreSQL)

All NSM-owned rows use the Django app label `netbox_nsm` (tables `netbox_nsm_*`).
Security object **instances** (zones, addresses, etc.) are stored by `netbox-custom-objects`,
not in NSM tables — NSM only stores links, configuration, rulebooks, and generic references.

| UI / concept | Tables |
|--------------|--------|
| Rulebook | `netbox_nsm_rulebook` |
| Field (column) | `netbox_nsm_rulebookfield` |
| Type in field | `netbox_nsm_rulebookfieldtype` + `netbox_nsm_typeconfig` |
| Rule | `netbox_nsm_rule` |
| Rule cell objects / groups | `netbox_nsm_ruleobjectitem`, `netbox_nsm_rulegroupitem` |
| Panel links | `netbox_nsm_objectlink` |
| Object groups | `netbox_nsm_objectgroup`, `netbox_nsm_objectgroupmember` |

Full table list, M2M tables, and SQL examples: **[docs/DATABASE.md](docs/DATABASE.md)**.

---

### ObjectLink (formerly ObjectLink)

```
ObjectLink
├── object_a_type  (ForeignKey → ContentType)
├── object_a_id    (PositiveBigIntegerField)
├── object_a       (GenericForeignKey)
├── object_b_type  (ForeignKey → ContentType)
├── object_b_id    (PositiveBigIntegerField)
├── object_b       (GenericForeignKey)
└── comment        (TextField, optional)
```

**Purpose:** Bidirectional link between any two NetBox objects.

**Unique constraint:** `(object_a_type, object_a_id, object_b_type, object_b_id)` — one link
per pair per direction.

**Indexes:** separate DB indexes on `(object_a_type, object_a_id)` and
`(object_b_type, object_b_id)` for fast lookup in both directions.

The Security Panel queries both directions in a single page render:

```python
fwd = ObjectLink.objects.filter(object_a_type=ct, object_a_id=obj.pk)
rev = ObjectLink.objects.filter(object_b_type=ct, object_b_id=obj.pk)
```

---

### TypeConfig

```
TypeConfig
├── name                 (CharField)
├── content_type         (FK → ContentType)
├── matching_class       (CharField, choices: MatchingClassChoices)
├── display_template     (CharField, default: "{name}")
├── panel_slugs          (JSONField, panel section slugs)
├── order_id             (PositiveIntegerField)
├── allow_virtual_groups (BooleanField)
├── inherit_links        (BooleanField)
├── inherit_stop_on_own  (BooleanField)
└── panel_linkable       (BooleanField — Security Panel assign picker master switch)
```

**Purpose:** Per-ContentType configuration for NSM behaviour. Unique together:
`(content_type, matching_class)`.

`matching_class` values: `address`, `zone`, `label`, `trust`, `service`, `action`, `info`, `user`,
`application`, `group`, `other`.

`display_template` is evaluated in `display_utils.render_object_display()` by substituting
`{field_name}` placeholders with the object's attributes. Falls back to `str(obj)`.

`panel_linkable` controls whether objects of this type can be linked from the NSM Security Panel
(**+ Assign**). Implemented in `forms/object_link.py` and `views/object_link.py`.

`inherit_links` / `inherit_stop_on_own` control the Security Panel's inheritance logic in
`NsmSecurityLinksExtension` (see Template Extensions). See `docs/DATABASE.md`.

---

### Rulebook

```
Rulebook (PrimaryModel, ContactsMixin)
├── name                   (CharField, unique)
├── rulebook_type          (CharField, currently only "policy")
└── rule_comment_template  (TextField, Markdown, supports {rule_name}/{index}/{rulebook})
```

Has a `@property matching_classes` that auto-derives the set of matching class strings from
all linked `RulebookFieldType` entries — used by the Analysis view.

---

### RulebookField / RulebookFieldType

```
RulebookField
├── rulebook    (FK → Rulebook, related_name="fields")
├── slug        (SlugField, unique within rulebook)
├── name        (CharField)
├── sort_order  (PositiveIntegerField)
└── placement   (CharField: source / destination / fixed)

RulebookFieldType
├── field       (FK → RulebookField, related_name="type_configs")
├── type_config (FK → TypeConfig)
├── sort_order  (PositiveIntegerField)
└── max_items   (PositiveIntegerField, nullable)
```

**Purpose:** Defines the columns of a Rulebook's rule editor. Each field can accept objects
of multiple TypeConfig types (e.g. a "Source" field might accept both Zones and Addresses).

---

### Rule

```
Rule (PrimaryModel, ContactsMixin)
├── rulebook           (FK → Rulebook, related_name="rules")
├── index              (PositiveIntegerField, ordering)
├── enabled            (BooleanField)
├── name               (CharField)
├── policy_action      (CharField, ActionChoices)
├── log_enabled        (BooleanField)
├── virtual_group_config (JSONField)
├── source_users       (M2M → User)
└── destination_users  (M2M → User)
```

Rule items (the actual object references per field) are stored in two separate models:

```
RuleObjectItem
├── rule        (FK → Rule)
├── field       (FK → RulebookField)
├── object_type (FK → ContentType)
├── object_id   (PositiveBigIntegerField)
└── object      (GenericForeignKey)

RuleGroupItem
├── rule   (FK → Rule)
├── field  (FK → RulebookField)
└── group  (FK → ObjectGroup)
```

This separation allows mixing direct object references and group references within the same
rule field.

`virtual_group_config` is a JSON structure controlling AND-group rendering in the policy table
(multiple objects shown as a single "AND bubble" instead of separate rows).

---

### RulebookAssignment

```
RulebookAssignment (NetBoxModel)
├── rulebook              (FK → Rulebook)
├── assigned_object_type  (FK → ContentType, limited to RULESET_ASSIGNMENT_MODELS)
├── assigned_object_id    (PositiveBigIntegerField)
└── assigned_object       (GenericForeignKey)
```

`RULESET_ASSIGNMENT_MODELS` (defined in `constants/`) limits assignments to:
`dcim.Device`, `dcim.VirtualDeviceContext`, `virtualization.VirtualMachine`.

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
| `views/setup.py` | `SetupView` | `setup/` |
| `views/nsm_type_config.py` | List / Add / Edit / Delete | `type-config/` |
| `views/nsm_policy.py` | Rulebook CRUD + Policy / Analysis / ZoneMatrix / IPAnalysis tabs | `rulebooks/` |
| `views/object_link.py` | CRUD for ObjectLink | `object-link/` |
| `views/object_analyzer.py` | `ObjectAnalyzerView` | `object-analyzer/` |
| `views/nsm_object_group.py` | ObjectGroup CRUD | `object-groups/` |
| `panel_sections.py` | Static panel slugs (source, destination, …) | — |
| `views/setup/demo.py` | Demo rulebooks (Matrix imports COTs/TypeConfigs if needed) | Setup POST |
| `views/custom_objects_sync.py` | Sync helper (manual trigger) | `setup/sync/custom-objects/` |
| `views/inherited_links_api.py` | Internal JSON API for inherited links | `api/inherited-links/` |
| `views/object_rules_api.py` | Internal JSON API for rule lookup | `api/object-rules/` |
| `views/rulebook_field.py` | RulebookField CRUD | `rulebook-field/` |

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

All demo actions call `_ensure_demo_prerequisites()` (imports missing COTs **and** TypeConfigs).

---

## Template Extensions (Security Panel)

Registered in `template_content.py` as `template_extensions = [...]`:

| Class | Models | What it renders |
|---|---|---|
| `NsmSecurityLinksExtension` | `None` (all models) | Security panel (right column): ObjectLinks, group M2M membership, nsm_addresses FK refs, rule references, rulebook assignments (devices/VMs), inheritance |

### Security Panel Link Sources

`NsmSecurityLinksExtension.right_page()` builds link groups from several sources:

1. **ObjectLink** records (forward and reverse) — explicit NSM assignments with edit/delete actions.
2. **nsm_addresses FK** — Custom Object rows pointing at this IPAM object via `prefix_id`, `ip_address_id`, or `range_id`.
3. **group M2M** — via `group_m2m.iter_group_m2m_relations()` (parent groups as *Member of*, contained objects as *Member*).
4. **Inherited links** — resolved at page load for IPAddress, IPRange, and Prefix (via `iter_inherited_nsm_links`).

Header actions: **Object Analyzer** (all objects), **IP Analysis** (address-matching TypeConfig only), **Assign** (ObjectLink picker).

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
Custom Object Type (`netbox-custom-objects`) and a matching TypeConfig, then wiring
**RulebookFieldType** rows on the Rulebook **Fields** card. No NSM code changes required for
a new security object class.

### Inheritance Resolution

Inherited links are computed at page load (same `iter_inherited_nsm_links` logic as the API). The panel merges them into
the type groups with a `(from <prefix>)` suffix. The JSON endpoint `inherited-links/` remains for API consumers; the client no longer fetches
`GET /plugins/netbox-nsm/api/inherited-links/?ct_id=&obj_id=` on demand.

For a child IPAM object (IP Address, IP Range, sub-Prefix), `ipam_inheritance.ancestor_prefixes_for_ipam()` finds
containing Prefixes (most-specific first). IP Ranges require a Prefix that contains **both** start and end address.
The API then collects ObjectLinks and inherited `nsm_addresses` FK rows from those ancestors, respecting per-TypeConfig
`inherit_links` and `inherit_stop_on_own` settings.

---

## API

REST API modules under `netbox_nsm/api/`:

```
api/
├── serializers_/
│   ├── object_link.py     ObjectLinkSerializer (with UniqueTogetherValidator)
│   ├── nsm_type_config.py
│   ├── nsm_policy.py
│   └── ...
├── views.py                   ModelViewSet subclasses
└── urls.py                    Router registration
```

The `ObjectLinkSerializer` uses a `ContentTypeField` (writable, accepts
`"app_label.model"` strings) and a custom `UniqueTogetherValidator` to enforce the
`unique_together` constraint at API level.

---

## Navigation

`navigation.py` uses a `DynamicPluginMenu` wrapper around NetBox's `PluginMenu` to defer
group construction until request time. This is necessary because some menu items reference
database objects (e.g. the default IP Analysis rulebook resolved at menu render time).

Menu structure (when `top_level_menu=True`):

```
Security
├── Configuration
│   ├── Setup
│   └── Type Config
├── Rulebooks
└── Analysis
    ├── IP Analysis        (first matching rulebook; config: `ip_analysis_rulebook_id` / `_name`)
    └── Object Analyzer
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

Integration tests live in `netbox_nsm/tests/integration_test.py`.

Run via:

```bash
docker exec netbox-dev python /app/netbox/netbox/manage.py test \
  netbox_nsm --verbosity=2
```

The test suite covers:
- ObjectLink CRUD via REST API (88 tests)
- TypeConfig CRUD
- Rulebook / Rule / Assignment CRUD
- UniqueTogetherValidator on ObjectLink
- Inheritance resolution in the Security Panel

All 88 tests pass on NetBox 4.6.1.
