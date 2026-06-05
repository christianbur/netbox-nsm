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
11. [Database Tables](#database-tables)
12. [Development Notes](#development-notes)

---

## Prerequisites & First Start

### Database migrations

`netbox-custom-objects` must be migrated **before** NSM. Without these tables, the Setup
page cannot query Custom Object Types (`relation "netbox_custom_objects_customobjecttype"
does not exist`).

After `netbox_nsm` is in `PLUGINS`, use the usual NetBox workflow (same as
[netbox-branching](https://github.com/netboxlabs/netbox-branching)):

```bash
cd netbox/netbox
./manage.py migrate --no-input
```

Or per plugin:

```bash
./manage.py migrate netbox_custom_objects --no-input
./manage.py migrate netbox_nsm --no-input
```

Homelab **netbox-dev:** siehe **[DOCKER.md](DOCKER.md)** (Migrationen, `down -v`, Setup, Fehler).

### Setup page

After installation and migration, open **Security → Configuration → Setup**.
The page checks whether all required COTs and TypeConfigs are present.

Use **Import** / **Import all missing types** on Setup to create built-in COTs and TypeConfigs
(idempotent for missing entries).

---

## Setup Wizard

**Security → Configuration → Setup**

### Plugin settings

| Setting | Default | Effect |
|---|---|---|
| `setup_menu` | `True` | Show **Setup** under Security → Configuration; allow `/setup/` URLs |
| `setup_allow_destructive_actions` | `True` | Show sync/demo buttons on Setup; set `False` in production |

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_menu": True,
        "setup_allow_destructive_actions": True,
    },
}
```

### Production vs. development actions

With `setup_allow_destructive_actions: False`, Setup only shows safe operations:

- per-type **Import** and **Import all missing types**
- **Create** / **Create all missing TypeConfigs**

The following are **hidden** and POST requests are rejected (production-safe):

| Action | Risk |
|---|---|
| **Sync built-in types** | Reapplies schemas, prunes stale COTs, reseeds defaults |
| **Create demo rulebooks** | Starter (Zone Matrix + Addresses) imports COTs/TypeConfigs if missing; Enterprise DC import |

Disable them in production in `configuration.py`:

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_allow_destructive_actions": False,
    },
}
```

Restart NetBox after changing plugin config.

### Setup sections (when destructive actions are enabled)

| Section | What it does |
|---|---|
| **Built-in types** | Status of each COT and TypeConfig; import missing types; optional full sync |
| **Demo rules** | Sample rulebooks for the rule editor |
| **Enterprise DC demo** | Full demo (DCIM + IPAM + 11 rulebooks). Button hidden once IP addresses exist |

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

An **ObjectLink** connects any two NetBox objects: a "host" object (e.g. a Prefix,
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
- **Group membership** for Custom Objects with a `group` M2M field (see below)
- An "Inherited" section for links coming from parent objects (see below)
- Quick links to **Object Analyzer** and **IP Analysis** (address objects only)
- An **Enforced Rulebooks** section listing all Rulebooks that reference this object

### Direct Links

Each entry shows:
- A coloured badge (using the object's colour field)
- The object name as a link to the detail page
- A remove (×) button if you have write permissions

### Group Membership (Address / Service objects)

Custom objects that define a `group` M2M field (notably `nsm_addresses` and
`nsm_services`) show group relationships in the Security Panel **without** requiring an
explicit ObjectLink:

| Comment | Meaning |
|---|---|
| **Member of** | Parent group(s) that contain this object (reverse M2M) |
| **Member** | Object(s) contained in this group when viewing a group object (forward M2M) |

Example: on address group `group-1`, the panel lists `g-all` as *Member of* and all
contained addresses/sub-groups as *Member*. The same edges appear in the Object Analyzer.

### Inherited Links

For **IP Addresses**, **IP Ranges**, and **sub-Prefixes**: links of containing Prefixes
are shown as inherited, marked with *"Inherited from containing prefix"*. Click **Load**
to fetch inherited links. For IP Ranges, a containing Prefix must cover **both** the
start and end address.

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
| **Panel slugs** | Panel sections (`source`, `destination`, `services`, `action`, `info`) — rule column placement is configured per RulebookField |
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
| `object-links/` | ObjectLink records | `host_ct_id`, `host_obj_id`, `sec_obj_ct_id` |
| `rulebooks/` | Rulebook records | `name` |
| `rules/` | Rule records | `rulebook_id`, `enabled` |
| `rulebook-assignments/` | Rulebook → object assignments | — |
| `object-groups/` | ObjectGroup records | — |
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

## Database Tables

NSM stores plugin data in PostgreSQL under the `netbox_nsm_*` tables (Django app `netbox_nsm`).
Rulebook **fields** map to `netbox_nsm_rulebookfield`; **types within a field** map to
`netbox_nsm_rulebookfieldtype` and `netbox_nsm_typeconfig`; rule rows and cell assignments
use `netbox_nsm_rule`, `netbox_nsm_ruleobjectitem`, and `netbox_nsm_rulegroupitem`.

Actual security objects (zones, addresses, labels, etc.) are **not** in these tables — they
live in `netbox-custom-objects` (and core NetBox when referenced).

See **[DATABASE.md](DATABASE.md)** for the full table list, hierarchy, and SQL examples.

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

### netbox_branching

Browser-side `fetch()` calls to the **NetBox REST API** must include the `X-NetBox-Branch`
header (schema ID from cookie `active_branch`) when a branch is active. NSM loads
`static/netbox_nsm/js/nsm_branch_api.js` on Security Panel, Object Analyzer, and related
pages to set this header automatically.

The **Rule Editor** object picker uses a server-side NSM endpoint instead of the REST API:
`GET /plugins/netbox-nsm/api/picker-browse/?ct=<content_type_id>&q=…` — branch context
comes from the Django request (cookie / `?_branch=`), so no branch header is needed in
`rule_form.js`.

The **Rules** (AG Grid) and **Matrix** tabs do not call the REST API from JavaScript —
row data is embedded at page render time (branch cookie selects the DB schema on the
server). Internal links (rule detail, matrix cell filters, Add Rule) get
`?_branch=<schema_id>` via `netbox_nsm.branch_urls.with_branch_query()`.

NSM registers junction tables (`RuleObjectItem`, `RuleGroupItem`, …) with netbox_branching at
plugin startup and routes writes explicitly via `netbox_nsm.branch_db` when a branch is active.
Without this, saving a rule in a branch fails with an FK error (parent `Rule` in branch schema,
child rows in `main`).

After upgrading NSM on an installation that already has branches, run **Branch → Migrate**
on each active branch once so the branch schema gets the junction tables if they were
missing.

### Locale / i18n

Translation strings for templates and Python are in:

```
netbox_nsm/locale/de/LC_MESSAGES/django.po
netbox_nsm/locale/en/LC_MESSAGES/django.po
```

After adding new `{% trans "..." %}` tags or editing `django.po`, compile catalogues
(in **netbox-dev** after `docker compose build`, or via host `msgfmt` if installed):

```bash
# netbox-dev (empfohlen)
./scripts/netbox-compilemessages.sh

# oder im Container
docker compose exec -T netbox python /opt/netbox/netbox/manage.py compilemessages
```

Several strings in the rule editor and Security Panel (e.g. `"Member of"`, `"Member"`,
`"Inherited from containing prefix"`) are listed in `django.po` with German translations.
