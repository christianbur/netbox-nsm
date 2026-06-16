# How rule data is stored

[← Documentation home](README.md) · [Database tables](DATABASE.md) · [Architecture](../ARCHITECTURE.md)

NSM does **not** persist policy as wide `netbox_nsm_rule` rows with dynamic SQL columns.
Since the COT migration, **rulebooks and rules are Custom Object Types** managed by
`netbox-custom-objects`. Configuration lives in COT `comments` (`nsm_config`); links and
assignments use the `nsm_object_link` COT.

Data is split into four layers:

1. **Schema** — COT field definitions on each deployed rulebook (`nsm_rb_*`)
2. **Rules** — one COT row per policy rule
3. **Cell contents** — `multiobject` COT fields on each rule row (references to zones, addresses, …)
4. **Referenced objects** — zones, addresses, services, etc. are separate COT or NetBox core rows

Security **object instances** are never duplicated inside rule rows — cells store references only.
See [What is stored elsewhere](DATABASE.md#what-is-stored-elsewhere).

---

## Layer model

```mermaid
flowchart TB
    subgraph UI["What you see in the UI"]
        RB["Rulebook Rules grid<br/>Columns: Index | Source › Zones | Destination › Addresses | …"]
    end

    subgraph Schema["Layer 1: column schema (per rulebook COT)"]
        COT["COT nsm_rb_*<br/>field: source, destination, service, …"]
        FLD["Field metadata<br/>type=multiobject, related_object_types, group_name"]
        TC["Object Config (nsm_config)<br/>sort order, display template, panel flags"]
    end

    subgraph Rules["Layer 2: rule rows"]
        R["COT rule row<br/>index, status, name, description, …"]
    end

    subgraph Cells["Layer 3: cell contents"]
        MO["multiobject field values<br/>on the rule COT row"]
    end

    subgraph External["Layer 4: referenced objects"]
        Z["nsm_zone"]
        A["nsm_address"]
        S["nsm_service"]
        G["nsm_address_group"]
    end

    RB --> R
    COT --> FLD
    FLD -.-> TC
    R --> MO
    COT --> MO
    MO -.->|object reference| Z
    MO -.->|object reference| A
    MO -.->|object reference| S
    MO -.->|object reference| G
```

---

## Entity relationships (simplified)

```mermaid
erDiagram
    "COT nsm_rb_*" ||--o{ "COT rule row" : "contains"
    "COT nsm_rb_*" ||--|{ "COT field def" : "defines columns"
    "nsm_object_link" }o--|| "NetBox host" : "netbox_object"
    "nsm_object_link" }o--o| "Policy object" : "policy_object (optional)"

    "COT rule row" {
        int index PK
        bool status
        string name
        json multiobject_source
        json multiobject_destination
    }

    "COT nsm_rb_*" {
        string slug
        text comments_nsm_config_rulebook
    }

    "nsm_object_link" {
        string link_type
        string rulebook_slug
        int netbox_object_id
    }
```

Native `Rulebook`, `Rule`, `RulebookField`, `RuleObjectItem`, and `RuleGroupItem` tables were
**removed**. Do not query `netbox_nsm_rule*` for current installs.

---

## Worked example: one UI row

**Policy table row:**

| Index | Name     | Source › Zones   | Destination › Addresses |
|------:|----------|------------------|-------------------------|
| 100   | Web→App  | DMZ, Internal    | bench-net-prod          |

**How that maps to storage:**

```mermaid
flowchart LR
    subgraph cot["COT rulebook nsm_rb_demo_addresses"]
        F1["field source<br/>multiobject → zones, labels, addresses, groups"]
        F2["field destination<br/>multiobject → zones, labels, addresses, groups"]
    end

    subgraph rule["Rule COT row index=100"]
        R["name=Web→App<br/>status=true"]
        S1["source → [DMZ pk, Internal pk]"]
        S2["destination → [bench-net-prod pk]"]
    end

    F1 --> S1
    F2 --> S2
    R --> S1
    R --> S2
```

**Important:** multiple pills in one UI cell = **multiple object references** in the same
`multiobject` field on that rule row (stored by `netbox-custom-objects`, not in NSM junction tables).

---

## UI concept → storage

| UI concept | Where it lives | What is stored |
|------------|----------------|----------------|
| Rulebook (deployed) | COT `nsm_rb_<name>` + `comments.nsm_config.rulebook` | COT schema + hierarchy/matrix flags in comments |
| Column “Source” | COT field `source` (or `source_zones`, …) | `multiobject` definition, `group_name`, `related_object_types` |
| Sub-type “Zones” under Source | Polymorphic `related_object_types` + `nsm_config` | UI splits one field by content type |
| Rule row | COT table for `nsm_rb_*` | `index`, `status`, `name`, system + policy fields |
| Object pill in a cell | `multiobject` value on rule row | Reference to zone / address / … instance |
| Group pill | `multiobject` or nested `group` M2M | Address group COT or member references |
| Zone / Address instance | `netbox-custom-objects` | **Not** duplicated in NSM native tables |
| Rulebook on device | COT `nsm_object_link` (`link_type=rulebook`) | `rulebook_slug` + generic FK to Device/VM/VDC |

System columns (Index, Status, Name, Description) are ordinary COT fields on the rulebook type
(see `_FIELD_CATALOG` in `rulebooks/templates.py`).

---

## Rulebook templates and schema apply

Built-in layouts (zone matrix, address-based, …) are Python documents in `rulebooks/templates.py`.
Setup or `POST /api/plugins/custom-objects/schema/apply/` deploys them as `nsm_rb_*` COTs.

Adding a column to a rulebook means **extending the COT schema** (new field on `nsm_rb_*`), not
a Django migration on NSM rule junction tables.

---

## Global rule list vs rulebook Rules tab

Both views read the **same** COT rule rows. Only presentation differs.

```mermaid
flowchart TB
    subgraph same["Same COT data"]
        DB[(netbox-custom-objects<br/>nsm_rb_* rows)]
    end

    subgraph tab["/plugins/netbox-nsm/rulebooks/cot/&lt;slug&gt;/rules/"]
        T["COT rules tab<br/>Columns from COT field schema"]
    end

    subgraph all["/plugins/netbox-nsm/rulebooks/0/rules/"]
        A["All Rules (read-only)<br/>Union across security rulebooks"]
    end

    DB --> T
    DB --> A
```

| URL | Purpose |
|-----|---------|
| `/plugins/netbox-nsm/rulebooks/cot/<slug>/rules/` | Rules grid for one deployed COT rulebook; optional vertical **Grouped rows** tabs (`nsm_config.rulebook.row_group_by_col_id`, active tab `?row_group_tab=…`) |
| `/plugins/netbox-nsm/rulebooks/0/rules/` | Aggregated read-only view across rulebooks |

The legacy global `/plugins/netbox-nsm/rules/` native list was removed with the COT migration.

---

## What “dynamic sub-fields” means

```mermaid
sequenceDiagram
    participant Admin as Extend rulebook COT
    participant Field as COT field (multiobject)
    participant Editor as Rule editor
    participant Row as COT rule row
    participant Obj as Zone / Address COT

    Admin->>Field: Add field "application" → labels
    Editor->>Row: Save rule with application → [label pk=5]
    Row->>Obj: Reference via multiobject storage
```

| Dynamic at… | Mechanism |
|-------------|-----------|
| **Schema** | Each `nsm_rb_*` COT defines its own fields (`rulebooks/templates.py` or schema apply) |
| **Cell content** | Zero or more references per `multiobject` field on each rule row |
| **Rule row shape** | Defined by COT fields — not a fixed `netbox_nsm_rule` model |

---

## Virtual AND/OR groups in cells

The rule editor can group pills into virtual AND/OR bubbles (`allow_virtual_groups` in
`nsm_config`). Structure is stored in editor metadata on the rule row (JSON where the COT
schema provides it); object references remain in the underlying `multiobject` field values.

---

## Related documentation

- [DATABASE.md](DATABASE.md) — permission anchors, removed legacy tables, migrations
- [ARCHITECTURE.md](../ARCHITECTURE.md) — developer model reference
- [Using netbox-nsm](using_netbox_nsm.md) — operator guide (rulebooks, panel)
