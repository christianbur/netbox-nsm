# netbox-nsm — Network Security Management Plugin for NetBox

> **⚠️ Work in Progress — do not use in production.**

A [NetBox](https://github.com/netbox-community/netbox) plugin for managing network security objects, security policies, and object groups.

This plugin was inspired by [netbox-security](https://github.com/andy-shady-org/netbox-security) by andy-shady-org. After working with it, I decided to write a new plugin from scratch that better fits my workflow and requirements.

The goal is a **modular, vendor-agnostic plugin** that can be used with any kind of firewall or policy system — including traditional firewalls, Cisco TrustSec, and label-based micro-segmentation platforms such as Illumio. Instead of hard-coding object types, the plugin lets you define your own types and fields to match whatever your environment requires.

---

## Architecture Overview

The plugin is built around four pillars:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Security Objects   — custom types, objects, groups          │
│  2. Security Policy    — rulebooks and rules                    │
│  3. Security Panel     — structured property system (NSM)       │
│  4. Security Tab       — read-only tabs on IPAM/DCIM objects    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Security Objects

### 1a. SecurityObjectType — Custom Object Types

`SecurityObjectType` defines the **schema** for a class of security objects. Think of it as a table definition: it specifies which fields instances of this type have, how they are displayed, and which area they belong to.

**Fields:**

| Field | Description |
|---|---|
| `name` | Unique identifier |
| `area` | One of `srcdst`, `services`, `action`, `info` (see below) |
| `icon` | MDI icon name from [pictogrammers.com](https://pictogrammers.com/library/mdi/) |
| `field_definitions` | JSON list of typed field definitions |
| `display_template` | Format string controlling how instances appear in the UI, e.g. `{name} ({port}/{protocol})` |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

**Areas:**

| Area | Key | Purpose |
|---|---|---|
| Source/Destination | `srcdst` | Objects used as traffic sources or destinations (addresses, prefixes, …) |
| Services | `services` | Port/protocol definitions and similar |
| Action | `action` | Actions applied to matching traffic (permit, deny, log, policer, …) |
| Info | `info` | Informational objects attached to rules (dates, comments, …) |

**Field definition types** (entries in `field_definitions`):

| Type | Description |
|---|---|
| `text` | Single-line text |
| `number` | Numeric value |
| `boolean` | True/False checkbox |
| `url` | Clickable URL |
| `date` | Date picker |
| `markdown` | Multi-line Markdown |
| `object_ref` | FK reference to any NetBox model |
| `multi_object_ref` | M2M reference to any NetBox model |

Each field definition is an object with at minimum `name` and `type`, plus optional `label`, `required`, `model` (for `object_ref`/`multi_object_ref`), and `help_text`.

**Built-in type catalog:**
A set of ready-made types can be installed with one click at
`/plugins/netbox-nsm/object/custom/types/install-builtins/`:

- *Action area:* Action, Filter, Log, Policer
- *Info area:* Comment, InstalledOn, InstallDate, Syslog

Once installed, a type is a regular database record and can be freely edited or deleted.

---

### 1b. SecurityObject — Custom Object Instances

`SecurityObject` is an **instance** of a `SecurityObjectType` — the actual data record.

**Fields:**

| Field | Description |
|---|---|
| `custom_type` | FK → `SecurityObjectType` |
| `name` | Name (unique per type) |
| `field_data` | JSON dict of dynamic field values, keyed by field name |
| `table_data` | JSON list of `{key, value}` rows for arbitrary extra metadata |
| `comments` | Markdown with template substitution (`{name}`, field data keys) |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

The form is generated dynamically from `custom_type.field_definitions`. For `object_ref` fields, a live search autocomplete fetches objects from the referenced NetBox model.

Objects support full CRUD, bulk-edit, bulk-delete, and CSV bulk-import.

---

### 1c. SecurityObjectAssignment — Generic Assignments

`SecurityObjectAssignment` links a `SecurityObject` to **any NetBox object** (Device, VM, Interface, IP Address, Prefix, …) via a generic foreign key.

**Fields:**

| Field | Description |
|---|---|
| `custom_object` | FK → `SecurityObject` |
| `assigned_object_type` | ContentType of the target object |
| `assigned_object_id` | PK of the target object |
| `comment` | Optional comment per assignment |

The assignments appear on both the `SecurityObject` detail page (Assignments tab) and the target object's detail page (NSM Security panel in the right column).

---

### 1d. SecurityObjectGroup — Object Groups

`SecurityObjectGroup` aggregates `SecurityObject` instances and/or other groups of the **same area** into a named group.

**Fields:**

| Field | Description |
|---|---|
| `name` | Unique group name |
| `area` | Same four areas as `SecurityObjectType` |
| `members` | M2M → `SecurityObject` (area-filtered in UI) |
| `sub_groups` | M2M (self, asymmetric) → child `SecurityObjectGroup` |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

Groups can be nested to arbitrary depth. The detail view shows both direct members and all parent groups that contain this group.

Groups are directly referenced in security rules (`source_groups`, `destination_groups`, `service_groups`, `action_groups`).

---

### Object / Group UI Structure

The plugin presents objects through a tabbed area view:

```
/plugins/netbox-nsm/object/            ← top-level tab switcher
    /object/<tab>/                      ← custom objects by area tab
    /object/groups/                     ← group area overview
    /object/groups/<area>/              ← groups filtered by area
```

---

## 2. Security Policy

### 2a. SecurityPolicyRulebook — Policy Container

`SecurityPolicyRulebook` is a **named policy** that holds an ordered list of rules.

**Fields:**

| Field | Description |
|---|---|
| `name` | Unique name |
| `rulebook_type` | Currently only `policy` ("Security Rules") |
| `rule_comment_template` | Markdown template pre-filled when adding new rules; supports `{rule_name}`, `{index}`, `{rulebook}` |
| `description`, `tags`, `custom_fields`, `contacts` | Standard NetBox fields |

The rulebook detail view contains:
- a rule table with inline status indicators
- a **Visualization** tab rendering the rules as a formatted policy table
- an **Assignments** tab listing all device/VM/VDC assignments
- a **Bulk Assign** action to assign the rulebook to multiple devices at once

---

### 2b. SecurityPolicyRule — Individual Rules

`SecurityPolicyRule` is a single rule inside a rulebook.

**Fields:**

| Field | Description |
|---|---|
| `rulebook` | FK → `SecurityPolicyRulebook` |
| `index` | Ordering index (lower = evaluated first) |
| `enabled` | Active/disabled toggle |
| `name` | Rule name |
| `source_groups` | M2M → `SecurityObjectGroup` (area `srcdst`) |
| `destination_groups` | M2M → `SecurityObjectGroup` (area `srcdst`) |
| `custom_service_objects` | M2M → `SecurityObject` (area `services`) |
| `service_groups` | M2M → `SecurityObjectGroup` (area `services`) |
| `custom_action_objects` | M2M → `SecurityObject` (area `action`) |
| `action_groups` | M2M → `SecurityObjectGroup` (area `action`) |
| `source_users` | M2M → NetBox User |
| `destination_users` | M2M → NetBox User |
| `log_enabled` | Log flag |
| `policy_action` | Choice field (permit / deny / reject / …) |
| `comments` | Markdown |
| `tags`, `custom_fields`, `contacts` | Standard NetBox fields |

Rules are edited via an inline edit form on the rulebook detail page, or via the dedicated rule edit page.

---

### 2c. SecurityPolicyAssignment — Rulebook → Device Assignments

`SecurityPolicyAssignment` assigns a `SecurityPolicyRulebook` to a **Device**, **Virtual Machine**, or **Virtual Device Context**.

**Fields:**

| Field | Description |
|---|---|
| `rulebook` | FK → `SecurityPolicyRulebook` |
| `assigned_object_type` | ContentType (Device / VM / VDC) |
| `assigned_object_id` | PK of the target |
| `description`, `tags` | Standard NetBox fields |

Assigned rulebooks appear on the device/VM/VDC detail page in the Security tab.

---

### Additional Policy Views

| URL | Description |
|---|---|
| `/plugins/netbox-nsm/rules/search/` | Global rule search across all rulebooks |
| `/plugins/netbox-nsm/device-security/device/<pk>/matching-rules/` | All rules that match a specific device by its NSM labels |
| `/plugins/netbox-nsm/device-security/vm/<pk>/matching-rules/` | Same for virtual machines |

---

## 3. Security Panel (NSM Object Builder)

The Security Panel provides a **second, strongly-typed property system** for scenarios where you need validated fields with JSON schemas, rather than the free-form JSON of Custom Objects.

### 3a. SecurityPropertyType — Property Schema

Defines a structured schema for one category of property data.

**Fields:**

| Field | Description |
|---|---|
| `name` | Slug-style identifier (lowercase, underscores) |
| `verbose_name` / `verbose_name_plural` | Human-readable display name |
| `slug` | URL-safe unique identifier |
| `group_name` | Optional grouping label |
| `schema_document` | Optional JSON Schema for validation |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

### 3b. SecurityPropertyField — Field Definition per Type

Each `SecurityPropertyType` has one or more `SecurityPropertyField` records defining its individual data fields.

**Fields:**

| Field | Description |
|---|---|
| `security_property_type` | FK → `SecurityPropertyType` |
| `name` | Field identifier (slug-style) |
| `label` | Human-readable field label |
| `field_type` | Field type (mirrors NetBox `CustomFieldTypeChoices`) |
| `required` | Whether the field is mandatory |
| `weight` | Display order |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

### 3c. SecurityProperty — Property Instances

Instances of a `SecurityPropertyType` attached to a NetBox object.

**Fields:**

| Field | Description |
|---|---|
| `property_type` | FK → `SecurityPropertyType` |
| `assigned_object` | Generic FK to any NetBox object |
| `data` | JSON dict of field values |
| `description`, `tags`, `custom_fields` | Standard NetBox fields |

---

## 4. Security Tab (Template Extensions)

The plugin injects a **Security** tab or panel into several standard NetBox detail pages without adding models of its own:

| NetBox model | What is shown |
|---|---|
| Device | Security tab: assigned rulebooks + NSM labels + matching rules link |
| Virtual Machine | Same as Device |
| Virtual Device Context | Assigned rulebooks |
| IP Address | Security tab: all Object Group chains referencing this address, including inherited prefix matches |
| Prefix | Security tab: direct and inherited Object Group references |
| IP Range | Security tab: Object Group references |
| *All other objects* | NSM Security panel (right column): Custom Object Assignments grouped by type, plus Custom Object back-references |

---

## YAML Bundle Export / Import

The plugin can export and import the entire Custom Type + Object + Group configuration as a single YAML file:

- **Export:** `/plugins/netbox-nsm/object/bundle/export/`
- **Import:** `/plugins/netbox-nsm/object/bundle/import/`

This is useful for bootstrapping new environments or sharing configurations between instances.

---

## REST API

All models are fully accessible via NetBox's REST API:

| Endpoint | Model |
|---|---|
| `/api/plugins/netbox-nsm/custom-types/` | `SecurityObjectType` |
| `/api/plugins/netbox-nsm/custom-objects/` | `SecurityObject` |
| `/api/plugins/netbox-nsm/custom-object-assignments/` | `SecurityObjectAssignment` |
| `/api/plugins/netbox-nsm/object-groups/` | `SecurityObjectGroup` |
| `/api/plugins/netbox-nsm/security-policy/` | `SecurityPolicyRulebook` |
| `/api/plugins/netbox-nsm/security-rule/` | `SecurityPolicyRule` |
| `/api/plugins/netbox-nsm/security-zone-policy-rulebook-assignments/` | `SecurityPolicyAssignment` |
| `/api/plugins/netbox-nsm/property-types/` | `SecurityPropertyType` |
| `/api/plugins/netbox-nsm/property-fields/` | `SecurityPropertyField` |
| `/api/plugins/netbox-nsm/properties/` | `SecurityProperty` |

All endpoints support filtering, searching, and pagination.

---

## Compatibility

| NetBox Version | Plugin Version |
|---|---|
| 4.5.x | 0.0.1 |
| 4.6.x | 0.0.1 |

---

## Installation

```bash
pip install netbox-nsm
```

Enable the plugin in your NetBox `configuration.py`:

```python
PLUGINS = ["netbox_nsm"]
```

Run database migrations:

```bash
cd /opt/netbox
source venv/bin/activate
python netbox/manage.py migrate netbox_nsm
python netbox/manage.py reindex netbox_nsm
```

Restart NetBox (gunicorn / uwsgi).

---

## Configuration

Add plugin settings in `configuration.py` (all optional):

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        # Show plugin menu as top-level entry (default: True)
        "top_level_menu": True,

        # Show assignments sub-menu item (default: False)
        "assignments_menu": False,
    }
}
```

---

## Quick Start

1. **Install built-in types** — go to *Security → Objects → Install Defaults* and select the types you need (Action, Filter, Log, Comment, …).
2. **Create custom objects** — navigate to the matching area tab (Source/Destination, Services, Action) and add objects.
3. **Create object groups** *(optional)* — group related objects under *Security → Objects → Groups*.
4. **Create a Security Policy** — under *Security → Security Policy*.
5. **Add rules** — open the policy and add rules, selecting object groups for each column (source, destination, services, action).
6. **Assign the policy to a device** — open a Device and use the *Assign Rulebook* action, or use the bulk-assign view on the policy detail page.

---

## Screenshots

### Navigation & Object Management
![Navigation](docs/img/01-navigation.png)
![Custom Object Types](docs/img/02-object-types.png)
![Object Type Detail](docs/img/03-object-type-detail.png)
![Object List](docs/img/04-object-list.png)
![Object Detail](docs/img/05-object-detail.png)

### Object Groups
![Object Groups](docs/img/06-object-groups.png)
![Object Group Detail](docs/img/07-object-group-detail.png)

### Built-in Types & YAML Bundle
![Built-in Type Installer](docs/img/08-builtin-types.png)
![YAML Bundle Export/Import](docs/img/09-yaml-bundle.png)

### Security Policies
![Security Policy — Address-based Rules](docs/img/10-security-policy-address.png)
![Security Rule Detail](docs/img/11-security-rule-detail.png)
![Security Policy — Label-based Rules (Illumio-style)](docs/img/12-security-policy-labels.png)

### Object Assignments & Device Integration
![Custom Object Assignments](docs/img/13-custom-object-assignments.png)
![Device Security Panel](docs/img/14-device-security-panel.png)

### Security on IPAM Objects
![Prefix Security Tab](docs/img/15-prefix-security-tab.png)
![IP Address Security Tab (inherited via subnet)](docs/img/16-ipaddress-security-tab.png)

---

## License

See [LICENSE](LICENSE).
