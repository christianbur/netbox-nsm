# netbox-nsm — Architecture Reference

This document describes the internal structure of the plugin for developers who want to
understand, extend or contribute to `netbox-nsm`.

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Dependency: netbox-custom-objects](#dependency-netbox-custom-objects)
3. [Data Model](#data-model)
   - [NSMObjectLink](#nsmobjectlink)
   - [TypeConfig](#typeconfig)
   - [SecurityPolicyRulebook](#securitypolicyrulebook)
   - [RulebookField / RulebookFieldType](#rulebookfield--rulebookfieldtype)
   - [SecurityPolicyRule](#securitypolicyrule)
   - [SecurityPolicyAssignment](#securitypolicyassignment)
4. [Built-in Types (builtin_types.py)](#built-in-types)
5. [Views](#views)
6. [Template Extensions (Security Panel)](#template-extensions-security-panel)
7. [API](#api)
8. [Navigation](#navigation)
9. [Signals](#signals)
10. [Demo Data](#demo-data)
11. [Testing](#testing)

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
│   ├── navigation.py         Plugin menu definition
│   ├── template_content.py   PluginTemplateExtension registrations
│   └── urls.py               URL patterns
├── docs/
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
- `netbox-nsm` only stores links (`NSMObjectLink`) and configuration (`TypeConfig`).
- The five built-in types are defined in `builtin_types.py` and can be imported/synced via
  the Setup Wizard or `POST /api/plugins/custom-objects/schema/apply/`.

This separation keeps the security data model flexible — you can extend or replace any type
without changing the NSM plugin itself.

---

## Data Model

### NSMObjectLink

```
NSMObjectLink
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
fwd = NSMObjectLink.objects.filter(object_a_type=ct, object_a_id=obj.pk)
rev = NSMObjectLink.objects.filter(object_b_type=ct, object_b_id=obj.pk)
```

---

### TypeConfig

```
TypeConfig
├── content_type       (OneToOneField → ContentType)
├── matching_class     (CharField, choices: MatchingClassChoices)
├── display_template   (CharField, default: "{name}")
├── allowed_placements (JSONField, list of placement slugs)
├── inherit_links      (BooleanField)
└── inherit_stop_on_own (BooleanField)
```

**Purpose:** Per-ContentType configuration for NSM behaviour.

`matching_class` values: `address`, `zone`, `label`, `trust`, `service`, `action`, `user`,
`application`, `group`, `other`.

`display_template` is evaluated in `display_utils.render_object_display()` by substituting
`{field_name}` placeholders with the object's attributes. Falls back to `str(obj)`.

`inherit_links` / `inherit_stop_on_own` control the Security Panel's inheritance logic in
`NsmSecurityLinksExtension` (see Template Extensions).

---

### SecurityPolicyRulebook

```
SecurityPolicyRulebook (PrimaryModel, ContactsMixin)
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
├── rulebook    (FK → SecurityPolicyRulebook, related_name="fields")
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

### SecurityPolicyRule

```
SecurityPolicyRule (PrimaryModel, ContactsMixin)
├── rulebook           (FK → SecurityPolicyRulebook, related_name="rules")
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
SecurityPolicyRuleObjectItem
├── rule        (FK → SecurityPolicyRule)
├── field       (FK → RulebookField)
├── object_type (FK → ContentType)
├── object_id   (PositiveBigIntegerField)
└── object      (GenericForeignKey)

SecurityPolicyRuleGroupItem
├── rule   (FK → SecurityPolicyRule)
├── field  (FK → RulebookField)
└── group  (FK → SecurityObjectGroup)
```

This separation allows mixing direct object references and group references within the same
rule field.

`virtual_group_config` is a JSON structure controlling AND-group rendering in the policy table
(multiple objects shown as a single "AND bubble" instead of separate rows).

---

### SecurityPolicyAssignment

```
SecurityPolicyAssignment (NetBoxModel)
├── rulebook              (FK → SecurityPolicyRulebook)
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
| `views/type_config.py` | List / Add / Edit / Delete | `type-config/` |
| `views/object_builder.py` | `ObjectBuilderView` (tabbed) | `object-builder/<tab>/` |
| `views/security_policy.py` | Rulebook CRUD + Policy / Analysis / ZoneMatrix / IPAnalysis tabs | `security-policy/` |
| `views/nsm_object_link.py` | CRUD for NSMObjectLink | `object-link/` |
| `views/object_analyzer.py` | `ObjectAnalyzerView` | `object-analyzer/` |
| `views/security_area.py` | SecurityArea CRUD | `security-area/` |
| `views/security_object_group.py` | SecurityObjectGroup CRUD | `security-object-group/` |
| `views/custom_objects_demo.py` | Demo helpers | `demo/` |
| `views/custom_objects_sync.py` | Sync helper (manual trigger) | `sync/` |
| `views/inherited_links_api.py` | Internal JSON API for inherited links | `api/inherited-links/` |
| `views/object_rules_api.py` | Internal JSON API for rule lookup | `api/object-rules/` |
| `views/rulebook_field.py` | RulebookField CRUD | `rulebook-field/` |

The `SetupView` POST handler dispatches on the `action` form field:

| action value | Effect |
|---|---|
| `import_type_<slug>` | Import single COT |
| `import_all_types` | Import all five COTs |
| `create_typeconfig_<slug>` | Create TypeConfig for one COT |
| `create_all_typeconfigs` | Create all TypeConfigs |
| `create_demo_matrix` | Create "Demo – Zone Matrix" Rulebook |
| `create_demo_addresses` | Create "Demo – Addresses" Rulebook |
| `create_demo_enterprise` | Run Enterprise DC import (blocked if IPs exist) |

---

## Template Extensions (Security Panel)

Registered in `template_content.py` as `template_extensions = [...]`:

| Class | Models | What it renders |
|---|---|---|
| `NsmSecurityLinksExtension` | `None` (all models) | Security panel (right column): NSMObjectLinks grouped by type, with inheritance resolution |
| `DeviceRulebookEnforcerExtension` | `dcim.device`, `dcim.virtualdevicecontext`, `virtualization.virtualmachine` | "Assigned Rulebooks" panel |
| `SecurityZoneContextInfo` | `netbox_nsm.securityzone` | Legacy zone detail extension |
| `AddressContextInfo` | `netbox_nsm.address` | Legacy address detail extension |
| `InterfaceInfo` | `dcim.interface` | Legacy interface extension |

### Inheritance Resolution in NsmSecurityLinksExtension

For a child object (IP Address, IP Range, sub-Prefix), the extension:

1. Queries direct `NSMObjectLink` records for the object.
2. For each `TypeConfig` with `inherit_links=True`, walks up the prefix hierarchy
   (via `ipam.Prefix.get_parents()` or equivalent) and collects NSMObjectLinks of the
   parent Prefix.
3. If `inherit_stop_on_own=True` on a TypeConfig and the child already has a direct link
   of that type, the inherited links for that type are suppressed.
4. Renders all links grouped by `content_type`, with an "inherited" badge on non-direct links.

---

## API

REST API modules under `netbox_nsm/api/`:

```
api/
├── serializers_/
│   ├── nsm_object_link.py     NSMObjectLinkSerializer (with UniqueTogetherValidator)
│   ├── type_config.py
│   ├── security_policy.py
│   └── ...
├── views.py                   ModelViewSet subclasses
└── urls.py                    Router registration
```

The `NSMObjectLinkSerializer` uses a `ContentTypeField` (writable, accepts
`"app_label.model"` strings) and a custom `UniqueTogetherValidator` to enforce the
`unique_together` constraint at API level.

---

## Navigation

`navigation.py` uses a `DynamicPluginMenu` wrapper around NetBox's `PluginMenu` to defer
group construction until request time. This is necessary because some menu items reference
database objects (e.g. hardcoded Rulebook pk=4 for the IP Analysis demo link).

Menu structure (when `top_level_menu=True`):

```
Security
├── Configuration
│   ├── Setup
│   ├── Object Builder
│   └── Type Config
├── Security Policies
└── Analysis
    ├── IP Analysis        (hardcoded demo link to rulebook 4)
    └── Demo – Object Analyzer
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
- NSMObjectLink CRUD via REST API (88 tests)
- TypeConfig CRUD
- SecurityPolicyRulebook / Rule / Assignment CRUD
- UniqueTogetherValidator on NSMObjectLink
- Inheritance resolution in the Security Panel

All 88 tests pass on NetBox 4.6.1.
