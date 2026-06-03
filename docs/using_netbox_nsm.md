# Using netbox-nsm

This guide covers all plugin features in detail and is intended for operators who
want to document their security landscape in NetBox.

---

## Table of Contents

1. [Prerequisites & First Start](#prerequisites--first-start)
2. [Setup Wizard](#setup-wizard)
3. [Custom Object Types (COTs)](#custom-object-types-cots)
   - [Zones](#zones-nsm_zones)
   - [Addresses](#addresses-nsm_addresses)
   - [Labels](#labels-nsm_labels)
   - [Services](#services-nsm_services)
   - [Actions](#actions-nsm_action)
   - [Business Apps](#business-apps-nsm_business_apps)
   - [Network Apps](#network-apps-nsm_network_apps)
4. [NSM Object Links](#nsm-object-links)
5. [Security Panel](#security-panel)
   - [Direct Links](#direct-links)
   - [Inherited Links](#inherited-links)
   - [Assigning Links](#assigning-links)
6. [Type Configs](#type-configs)
7. [Security Rulebooks](#security-rulebooks)
   - [Creating a Rulebook](#creating-a-rulebook)
   - [Rulebook Fields (Columns)](#rulebook-fields-columns)
   - [Rule Editor](#rule-editor)
   - [AND-Groups](#and-groups)
   - [Rule Actions (enable, delete, reorder)](#rule-actions)
8. [Policy Views](#policy-views)
   - [Policy Table](#policy-table)
   - [Analysis Tab](#analysis-tab)
   - [Zone Matrix Tab](#zone-matrix-tab)
9. [Object Analyzer](#object-analyzer)
10. [REST API Reference](#rest-api-reference)
11. [Development Notes](#development-notes)

---

## Prerequisites & First Start

After installation and migration, open **Security → Configuration → Setup**.
The page checks whether all required COTs and TypeConfigs are present.

Run **Sync types** first — it creates all seven built-in COTs and their TypeConfig records
(idempotent: safe to run multiple times, existing objects are not overwritten).

---

## Setup Wizard

**Security → Configuration → Setup**

The Setup page has three sections:

| Section | What it does |
|---|---|
| **Built-in types** | Shows the status of each COT and TypeConfig. "Sync" creates missing ones. |
| **Demo rules** | Creates a small sample Rulebook to explore the rule editor. |
| **Enterprise DC demo** | Imports a full demo scenario (DCIM + IPAM + 11 rulebooks, 250+ rules). Only available when no IP addresses exist yet. |

> The Enterprise DC import is idempotent (`get_or_create`) — but because it creates IP
> addresses, it can only be triggered once (the button disappears after the first import).

---

## Custom Object Types (COTs)

COTs are managed by the `netbox-custom-objects` plugin. Each COT is essentially a named
object class with a custom field schema. NSM ships seven built-in COTs. You can also create
your own COTs and attach a TypeConfig to them.

Objects of each COT live under **Security → Security Objects → \<type\>**.

### Zones (`nsm_zones`)

Security zones — the logical groupings used in zone-based policies.

| Field | Description |
|---|---|
| `name` | Zone name, e.g. `prod`, `dmz`, `untrust` |
| `description` | Optional text |
| `color` | Hex colour used for pills and matrix cells |
| `comments` | Extended notes |

Zones are typically linked to Prefixes (e.g. `10.0.0.0/8 → prod`).

### Addresses (`nsm_addresses`)

Named address objects or address groups — equivalent to firewall address objects.

| Field | Description |
|---|---|
| `name` | Address object name |
| `value` | IP address or CIDR notation (optional) |
| `description` | Optional text |
| `color` | Display colour |
| `comments` | Extended notes |

### Labels (`nsm_labels`)

Arbitrary classification tags — environment (`prod`, `staging`), role (`web-tier`, `db-tier`),
compliance (`pci`, `gdpr`), or any other dimension.

| Field | Description |
|---|---|
| `name` | Label text |
| `description` | Optional text |
| `color` | Display colour |
| `comments` | Extended notes |

### Services (`nsm_services`)

Port/protocol definitions used in rule Service columns.

| Field | Description |
|---|---|
| `name` | Display name, e.g. `HTTPS`, `DNS-UDP` |
| `protocol` | `tcp`, `udp`, `icmp`, or custom string |
| `port` | Port number or range, e.g. `443`, `8080-8090` |
| `description` | Optional text |
| `color` | Display colour |
| `comments` | Extended notes |

### Actions (`nsm_action`)

Rule outcome objects: `permit`, `deny`, `drop`, `reject`, or custom values.

### Business Apps (`nsm_business_apps`)

Business applications with ownership metadata. Used in the **fixed** columns of a rule
to document which business application a rule serves.

| Field | Type | Description |
|---|---|---|
| `name` | Text | Application name (required) |
| `criticality` | Choice | `low` / `medium` / `high` / `critical` |
| `business_owner` | Object (ContactGroup) | Responsible business contact group |
| `technical_owner` | Object (ContactGroup) | Responsible technical contact group |
| `description` | Text | Free-text description |
| `color` | Text | Display colour (hex) |
| `comments` | Long text | Extended notes |

### Network Apps (`nsm_network_apps`)

App-ID style application identifiers — equivalent to Palo Alto App-IDs or Fortinet application
signatures. Pre-populated with common apps: `dns`, `http`, `ssl`, `ssh`, `rdp`, `smtp`,
`smb`, `onedrive`, `teams`, `zoom`.

| Field | Type | Description |
|---|---|---|
| `name` | Text | Application name, e.g. `ssl`, `zoom` |
| `app_category` | Choice | `collaboration` / `database` / `email` / `file-sharing` / `general-internet` / `infrastructure` / `media` / `networking` / `remote-access` / `saas` / `security` / `storage` / `voip-video` / `other` |
| `app_risk` | Choice | Risk level `1` (low) to `5` (high) |
| `default_ports` | Text | Comma-separated, e.g. `tcp/443,tcp/80` |
| `description` | Text | Description |
| `color` | Text | Display colour (hex) |
| `comments` | Long text | Extended notes |

---

## NSM Object Links

An **NSMObjectLink** connects any two NetBox objects: a "host" object (e.g. a Prefix,
IP Address, Device, VM) and a "security" object (Zone, Address, Label, Service, …).

Links are bidirectional — querying either end finds the link.

A single NetBox object can have **multiple links of the same type** (e.g. a Prefix belonging
to both `zone-a` and `zone-b`), and **links of different types** simultaneously (zone + address
+ two labels).

Links are managed directly on the object detail page (Security Panel) or via the REST API.

---

## Security Panel

The Security Panel is **automatically injected** into every NetBox object detail page
(Prefix, IP Address, Device, VM, Interface, and all custom object pages). No configuration
is needed — the panel appears as soon as the plugin is installed.

The panel shows:
- All directly assigned security objects, grouped by type (Zones, Addresses, Labels, …)
- An "Inherited" section for links coming from parent objects (see below)
- An **Enforced Rulebooks** section listing all Rulebooks that reference this object

### Direct Links

Each entry shows:
- A coloured badge (using the object's colour field)
- The object name as a link to the detail page
- A remove (×) button if you have write permissions

### Inherited Links

For **IP Addresses** and **sub-Prefixes**: links of the parent Prefix are shown as inherited,
marked with *"Inherited from containing prefix"*. Click **Load** to fetch inherited links.

For **Devices** and **Virtual Machines**: inherited links are fetched via the object's primary
IP address (primary IPv4 if set, else primary IPv6). This means the zone assignments of the
prefix containing the device's primary IP appear on the device panel automatically.

Inheritance is controlled per-type via the TypeConfig **inherit from parent** setting.

### Assigning Links

Click **+ Assign** in the Security Panel to open the assignment picker.

Select the target security object type, search for the object by name, and click **Assign**.
The new link appears immediately in the panel.

---

## Type Configs

**Security → Configuration → Type Configs**

A TypeConfig connects a NetBox ContentType (e.g. `Custom Objects › nsm_zones`) to NSM
behaviour settings.

| Field | Description |
|---|---|
| **Object Type** | The ContentType — must be set to a COT or native NetBox type |
| **Slug** | Internal identifier (auto-derived from ContentType) |
| **Label** | Human-readable name shown in pickers |
| **Matching Class** | Semantic role in rule columns: `zone`, `address`, `label`, `service`, `action`, `application`, `other` |
| **Display Template** | Jinja2-like template for rendering objects: `{name}`, `{name} ({protocol}/{port})` |
| **Allowed Placements** | Which rule columns this type can appear in: `source`, `destination`, `fixed` |
| **Panel linkable** | Show this type in the Assign picker of the Security Panel |
| **Inherit from parent** | Enable prefix/IP inheritance for this type |
| **Stop if own link** | Suppress inherited link if the child has its own direct link of this type |

All seven built-in COTs get their TypeConfigs created automatically by the Setup Wizard.

---

## Security Rulebooks

**Security → Security Policies**

A **Rulebook** models one firewall's rule base (or a logical segment of it). Each Rulebook
has a custom set of **fields** (columns) that define the column structure.

Because each Rulebook defines its own schema, you can document zone-based (Palo Alto,
Fortinet), address-based (iptables, ACLs) and label-based (NSX, Illumio) policies
side-by-side in the same NetBox instance.

### Creating a Rulebook

1. **Security → Security Policies → + Add**
2. Set a name (e.g. `FW-DC-01 Policy`) and optional description
3. Save

The Rulebook is now empty — it has no fields and no rules yet.

### Rulebook Fields (Columns)

Go to the **Fields** tab of the Rulebook detail page.

Each field defines one column in the rule editor:

| Field property | Description |
|---|---|
| **Name** | Internal name (also used for CSV import column headers) |
| **Label** | Display label in the rule table |
| **Area** | `source`, `destination`, or `fixed` — controls which object types appear in this column |
| **Allowed types** | Optional restriction to specific TypeConfigs (leave blank = all types for this area) |
| **Required** | Whether the column must be filled in every rule |
| **Weight** | Column order |

Typical field setups:

| Style | Fields |
|---|---|
| Zone-based | Source (zone), Destination (zone), Service (fixed), Action (fixed) |
| Address-based | Source (source), Destination (destination), Service (fixed), Action (fixed) |
| App-ID | Source (zone), Destination (zone), Application (fixed), Action (fixed) |

### Rule Editor

Open the **Policy** tab of any Rulebook.

The table shows one row per rule. Each cell in a rule row corresponds to one field (column).

**To add a new rule:** click **+ Add Rule** below the table.

**To edit a rule cell:**

1. Click anywhere in the cell to open the object picker for that column
2. The picker shows:
   - A **type selector** (if the column accepts multiple object types) — choose which type to add
   - A **search field** — type to filter, or leave empty to browse
   - A **browse list** showing up to 10 matching objects
   - A **Load more** button if more than 10 results are available
   - The **current selection** on the right side, with × buttons to remove items
3. Click an item in the browse list to add it to the rule
4. Click outside the picker or press Escape to close

**To edit rule metadata** (name, index, enabled, comment, log):
Click the pencil icon on the left side of the rule row to open the inline editor.

### AND-Groups

By default, multiple items in a single cell are treated as OR (any of them can match).

To create an AND-group (all items must match), click the **AND** button inside the picker.
This creates a sub-group; items within the group must all match simultaneously.

AND binds tighter than OR — `(A AND B) OR C` means "A and B together, or C alone".

### Rule Actions

| Action | How |
|---|---|
| Enable / Disable | Click the toggle icon in the rule row |
| Reorder | Edit the **Index** field in the rule row metadata |
| Delete | Check the row checkbox → **Delete selected** |
| Duplicate | Not yet implemented |

---

## Policy Views

### Policy Table

The **Policy** tab is the main editing surface. Rules are displayed as a table.

- Object pills are colour-coded using the object's own colour
- Pills are content-sized (not stretched to column width) with ellipsis for long names
- The policy table columns are dynamically sized to their content on first load

### Analysis Tab

The **Analysis** tab gives an overview of the Rulebook's composition:

- Total rule count, enabled/disabled breakdown
- Rule density per field (how many rules use each column)
- Object type distribution (which matching classes appear across all rules)

Useful for spotting incomplete rules (many empties in a column) or policy gaps.

### Zone Matrix Tab

The **Zone Matrix** tab renders the policy as a **source zone × destination zone** grid.

Each cell in the grid shows the services that are permitted or denied between those two zones.
This is the most effective way to understand a zone-based policy at a glance.

Works best for Rulebooks with Zone objects in Source and Destination fields (Palo Alto,
Fortinet, Cisco ASA, Check Point, …). For address-based Rulebooks, the matrix is less
meaningful (address objects rather than named zones).

---

## Object Analyzer

**Security → Analysis → Object Analyzer**

The Object Analyzer is a read-only exploration tool. Select any NetBox object (Prefix,
IP Address, Device, VM, custom object, …) and see:

- All direct and inherited NSM links grouped by type (Zones, Addresses, Labels, …)
- All policy rules across all Rulebooks where this object appears as source, destination,
  or in a fixed column

Useful for answering questions like:
- *"Which zone does 10.10.5.0/24 belong to?"*
- *"Which firewall rules reference this IP address?"*
- *"Is this server covered by a deny-all rule anywhere?"*

---

## REST API Reference

All NSM models are available under `/api/plugins/netbox-nsm/`.
The root endpoint (`GET /api/plugins/netbox-nsm/`) lists all available endpoints.

### Endpoints

| Endpoint | Description | Key filters |
|---|---|---|
| `type-configs/` | TypeConfig records | `slug`, `matching_class` |
| `object-links/` | NSMObjectLink records | `host_ct_id`, `host_obj_id`, `sec_obj_ct_id` |
| `security-areas/` | Rule field area definitions | — |
| `security-zone-policy-rulebooks/` | Rulebook records | `name` |
| `security-zone-policy-rules/` | Rule records | `rulebook_id`, `enabled` |
| `security-zone-policy-rulebook-assignments/` | Rulebook → object assignments | — |
| `object-groups/` | SecurityObjectGroup records | — |
| `rulebook-fields/` | Per-Rulebook column definitions | `rulebook_id` |
| `rulebook-field-types/` | Allowed types per field | — |
| `rule-object-items/` | Object items within a rule cell | `rule_id`, `field_id` |
| `rule-group-items/` | AND-group items within a rule cell | `rule_id`, `field_id` |

### Schema import

The COT schema can be applied (re-applied) via the `netbox-custom-objects` API:

```http
POST /api/plugins/custom-objects/schema/apply/
Content-Type: application/json

< nsm-schema.json
```

This is idempotent — existing COTs and fields are updated, not duplicated.

### Authentication

All API endpoints require a NetBox API token:

```bash
curl -H "Authorization: Token <your-token>" \
     https://your-netbox/api/plugins/netbox-nsm/type-configs/
```

---

## Development Notes

### Template changes require a restart

NetBox uses Django's `cached.Loader` which holds compiled templates in memory.
**Any change to a `.html` file requires a process restart to take effect:**

```bash
docker compose restart netbox
```

A plain `Ctrl+S` in the editor is not enough — the old template stays in RAM until restart.

### TypeConfig updates via Setup Wizard

If you change TypeConfig field values in `builtin_types.py` or `views/setup.py`, re-run the
Setup Wizard **Sync** to push the updates to the database. Existing records are updated
(not skipped) by the Sync operation.

### Locale / i18n

Translation strings for templates and Python are in:

```
netbox_nsm/locale/de/LC_MESSAGES/django.po
netbox_nsm/locale/en/LC_MESSAGES/django.po
```

After adding new `{% trans "..." %}` tags, compile the catalogues:

```bash
python netbox/manage.py compilemessages
```

Several strings added in the rule editor and Security Panel (e.g. `"Add Rule"`,
`"Inherited from containing prefix"`, `"No inherited links found."`) are marked for
translation but may not yet have German translations in `django.po`.
