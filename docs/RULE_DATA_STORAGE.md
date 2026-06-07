# How rule data is stored

[← Documentation home](README.md) · [Database tables](DATABASE.md) · [Architecture](../ARCHITECTURE.md)

NSM does **not** persist policy as a wide spreadsheet with dynamic columns on the `Rule` row.
Instead, data is split into four layers:

1. **Schema** — which columns a rulebook has (`RulebookField`, `RulebookFieldType`)
2. **Rules** — one row per policy rule (`Rule`)
3. **Cell contents** — links from a rule + column to objects or groups (`RuleObjectItem`, `RuleGroupItem`)
4. **Referenced objects** — zones, addresses, services, etc. live in Custom Objects or NetBox core; NSM stores only generic foreign keys

Security **object instances** are never duplicated inside NSM rule tables. See [What is stored elsewhere](DATABASE.md#what-is-stored-elsewhere).

---

## Layer model

```mermaid
flowchart TB
    subgraph UI["What you see in the UI"]
        RB["Rulebook Rules table<br/>Columns: Index | Source › Zones | Destination › Addresses | …"]
    end

    subgraph Schema["Layer 1: column schema (per rulebook)"]
        RBF["RulebookField<br/>slug: source, destination, service, …"]
        RBFT["RulebookFieldType<br/>allowed object types per column"]
        TC["TypeConfig<br/>matching, display template, panel flags"]
    end

    subgraph Rules["Layer 2: rule rows"]
        R["Rule<br/>index, name, enabled, description, …"]
    end

    subgraph Cells["Layer 3: cell contents"]
        ROI["RuleObjectItem<br/>rule + field + content_type + object_id"]
        RGI["RuleGroupItem<br/>rule + field + ObjectGroup"]
    end

    subgraph External["Layer 4: actual objects (outside NSM rule tables)"]
        Z["Zone"]
        A["Address"]
        S["Service"]
        OG["ObjectGroup"]
    end

    RB --> R
    RB --> RBF
    RBF --> RBFT --> TC
    R --> ROI
    R --> RGI
    RBF --> ROI
    RBF --> RGI
    ROI -.->|Generic FK| Z
    ROI -.->|Generic FK| A
    ROI -.->|Generic FK| S
    RGI -.-> OG
```

---

## Entity relationships (simplified)

```mermaid
erDiagram
    Rulebook ||--o{ RulebookField : "defines columns"
    Rulebook ||--o{ Rule : "contains rules"
    RulebookField ||--o{ RulebookFieldType : "allowed types"
    RulebookFieldType }o--|| TypeConfig : "points to"
    TypeConfig }o--|| ContentType : "object type"

    Rule ||--o{ RuleObjectItem : "cell = object"
    Rule ||--o{ RuleGroupItem : "cell = group"
    RulebookField ||--o{ RuleObjectItem : "which column"
    RulebookField ||--o{ RuleGroupItem : "which column"

    RuleObjectItem }o--|| ContentType : "type"
    RuleObjectItem }o--o| "Any NetBox / custom object" : "object_id"

    Rulebook {
        int id PK
        string name
        string rulebook_type
    }

    RulebookField {
        int id PK
        int rulebook_id FK
        string slug
        string name
        string placement
        string field_kind
    }

    Rule {
        int id PK
        int rulebook_id FK
        int index
        string name
        bool enabled
        json virtual_group_config
    }

    RuleObjectItem {
        int id PK
        int rule_id FK
        int field_id FK
        int content_type_id FK
        bigint object_id
        bool exclude
    }
```

---

## Worked example: one UI row

**Policy table row:**

| Index | Name     | Source › Zones   | Destination › Addresses |
|------:|----------|------------------|-------------------------|
| 100   | Web→App  | DMZ, Internal    | 10.0.0.0/24             |

**How that maps to the database:**

```mermaid
flowchart LR
    subgraph rulebook["Rulebook: Security Rules RB"]
        F1["RulebookField<br/>slug=source"]
        F2["RulebookField<br/>slug=destination"]
    end

    subgraph rule["Rule #42"]
        R["index=100<br/>name=Web→App<br/>enabled=true"]
    end

    subgraph items["RuleObjectItems"]
        I1["field=source<br/>ct=Zone, object_id=7 → DMZ"]
        I2["field=source<br/>ct=Zone, object_id=12 → Internal"]
        I3["field=destination<br/>ct=Address, object_id=99 → 10.0.0.0/24"]
    end

    F1 --> I1
    F1 --> I2
    F2 --> I3
    R --> I1
    R --> I2
    R --> I3
```

**Important:** multiple pills in one UI cell = **multiple `RuleObjectItem` rows** (same
`rule_id` and `field_id`, different `object_id`).

Unique constraint on `RuleObjectItem`: `(rule, field, content_type, object_id)`.

---

## UI concept → PostgreSQL table

| UI concept | Table | What is stored |
|------------|-------|----------------|
| Rulebook | `netbox_nsm_rulebook` | Name, platform, matrix flag, comment template, … |
| Column “Source” | `netbox_nsm_rulebookfield` | slug, name, placement, sort_order, visibility, … |
| Sub-type “Zones” under Source | `netbox_nsm_rulebookfieldtype` → `netbox_nsm_typeconfig` | Which content type is allowed, max items, … |
| Rule row | `netbox_nsm_rule` | index, name, enabled, description — **not** zone/address text |
| Object pill in a cell | `netbox_nsm_ruleobjectitem` | FK to rule + field + generic object |
| Group pill in a cell | `netbox_nsm_rulegroupitem` | FK to rule + field + `ObjectGroup` |
| Zone / Address instance | Custom Objects / NetBox core | **Not** in NSM rule junction tables |

System columns (Index, Status, Name, Description) are also `RulebookField` rows with
`field_kind=system`; their values live on the `Rule` model, not in `RuleObjectItem`.

---

## Global rule list vs rulebook Rules tab

Both views read the **same** `Rule` and junction rows. Only the **presentation** differs.

```mermaid
flowchart TB
    subgraph same["Same PostgreSQL data"]
        DB[(netbox_nsm_rule<br/>netbox_nsm_ruleobjectitem<br/>…)]
    end

    subgraph list["/plugins/netbox-nsm/rules/"]
        L["RuleListView<br/>Fixed columns: Source, Destination, Service, Action, Info<br/>Legacy layout, all rulebooks mixed"]
    end

    subgraph tab["/plugins/netbox-nsm/rulebooks/&lt;pk&gt;/rules/"]
        T["RulebookRulesView<br/>Dynamic columns from RulebookField<br/>Per-rulebook layout"]
    end

    subgraph all["/plugins/netbox-nsm/rulebooks/0/rules/"]
        A["All Rules (read-only)<br/>Union of columns across policy rulebooks"]
    end

    DB --> L
    DB --> T
    DB --> A
```

| URL | Purpose |
|-----|---------|
| `/plugins/netbox-nsm/rules/` | NetBox object list of all `Rule` records; fixed column set in `RuleTable` |
| `/plugins/netbox-nsm/rulebooks/<pk>/rules/` | Rules grid for one rulebook; columns match that rulebook's fields |
| `/plugins/netbox-nsm/rulebooks/0/rules/` | Aggregated read-only view across all security rulebooks |

Prefer the rulebook Rules tab (or All Rules) for day-to-day policy work. The global `/rules/`
list is mainly a technical inventory / admin view.

---

## What “dynamic sub-fields” means

```mermaid
sequenceDiagram
    participant Admin as Configure rulebook
    participant Field as RulebookField
    participant Editor as Rule editor
    participant Item as RuleObjectItem
    participant Obj as NetBox object

    Admin->>Field: Add column "Application"
    Admin->>Field: Allow type "Labels"
    Editor->>Item: On save: rule + field(application) + label pk=5
    Item->>Obj: Generic FK → Label pk=5
```

| Dynamic at… | Mechanism |
|-------------|-----------|
| **Schema** | Each rulebook defines its own `RulebookField` rows and allowed `RulebookFieldType` entries |
| **Cell content** | Zero or more `RuleObjectItem` / `RuleGroupItem` rows per rule and field |
| **`Rule` row itself** | **Not** dynamic — no columns like `source_zones` or `dest_addresses` on the model |

Adding a new column to a rulebook does **not** require a database migration for rule content:
new assignments use existing junction tables with a new `field_id`.

---

## `virtual_group_config` (JSON on `Rule`)

`Rule.virtual_group_config` stores editor metadata for **virtual AND/OR groups** inside a cell
(how pills are grouped in the rule form). Object references still persist in
`RuleObjectItem` / `RuleGroupItem`; the JSON describes structure, not the referenced objects.

---

## Related documentation

- [DATABASE.md](DATABASE.md) — full table list and migration notes
- [ARCHITECTURE.md](../ARCHITECTURE.md) — model field reference for developers
- [Using netbox-nsm — Rules grid](using_netbox_nsm.md#rules-grid) — operator UI guide
