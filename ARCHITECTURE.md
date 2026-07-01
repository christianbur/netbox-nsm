# netbox-nsm — Architecture

For developers. Operations: [docs/using_netbox_nsm.md](docs/using_netbox_nsm.md)

## Dependency

Policy data (zones, rules, links) is stored as **Custom Object Types** via [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects).

- Type behaviour: **`metadata`** in JSON bundles → synced to COT **`comments`** (`nsm_config` YAML)
- Instances: COT rows (`nsm_zone`, `nsm_rb_*`, `nsm_object_link`, …)
- Built-in schemas: JSON bundles under `netbox_nsm/bundles/builtin/<slug>/bundle.json`; apply via Setup or `bundles/dispatch.py`

## Data model (0.5.x setup rebuild)

| Layer | Where | Examples |
|-------|-------|----------|
| UI labels | `PLUGINS_CONFIG` | `menu_label`, `panel_label` |
| Global type metadata | Bundle `metadata.types` → policy COT `comments` | `links` |
| Rulebook type metadata | Bundle `metadata.rulebooks` → rulebook COT `comments` | `rulebook` flags + per-type `rule_view` |
| Instances | COT rows | zones, rules, links |

`nsm_object_link`: panel links (`link_type=policy`) and rulebook assignments (`link_type=rulebook`).

Details: [docs/DATABASE.md](docs/DATABASE.md), [docs/RULE_DATA_STORAGE.md](docs/RULE_DATA_STORAGE.md)

## Four modules

| Module | Path | Role |
|--------|------|------|
| **Import** | `bundles/` | COT schemas, choice sets, seeds; `discovery.py` for Setup health |
| **Views** | `rulebooks/views/` | Table + matrix display; `views/registry.py` drives tabs |
| **Proxy** | `rulebooks/proxy/` | Rule-row add/edit/delete/clone URLs on COT rulebooks |
| **Analyzers** | `analyzers/` | Object Analyzer, IP Analyzer, Object Report; `registry.py` |

Semantic roles (address, address_group, …) are resolved in `objects/cot_roles.py` from deployed field schema (`related_object_types`) and optional COT metadata — not from hardcoded slugs or field names.

## Layout

```
netbox_nsm/
├── bundles/              # dispatch, discovery, setup_context, schema_builder
│   └── builtin/          # portable schema JSON bundles
├── rulebooks/
│   ├── proxy/            # rule_rows.py — CRUD URLs for rule COT rows
│   ├── matrix/           # zone matrix engine (tab context, axis filter, layout)
│   └── views/
│       ├── registry.py   # RulebookViewSpec (table / matrix tabs)
│       ├── table/        # canonical import path → CotRulebookRulesView
│       └── matrix/       # canonical import path → CotRulebookMatrixView
├── analyzers/
│   ├── registry.py       # ANALYZER_REGISTRY (object_analyzer, ip_analyzer, object_report, label)
│   ├── object_analyzer/
│   ├── ip_analyzer/
│   ├── object_report/    # check_registry.py — optional custom report checks
│   └── label/            # skeleton capability (no route yet)
├── objects/
│   └── cot_roles.py      # resolve_role, resolve_ipam_field, membership_through, …
├── addresses/            # address_cot_schema, address_ipam_fk (→ cot_roles)
├── security/             # tab, references, panel-link actions, object links
├── type_metadata/        # specs, roles, TypeConfig UI
├── api/                  # REST endpoints (ip-analyzer, object-links, …)
└── tests/
```

Details: [docs/MODULAR_ARCHITECTURE_PLAN.md](docs/MODULAR_ARCHITECTURE_PLAN.md)

Portable schema: `netbox_nsm/bundles/builtin/*.json` → Setup Preview → Apply → COT `apply_document` + `sync_metadata` → COT `comments`

## Key URLs

| View | Path |
|------|------|
| Bundles | `bundles/` |
| Type metadata | `type-metadata/` |
| Rulebooks / COT rules | `rulebooks/`, `rulebooks/cot/<slug>/rules/` |
| All rules | `rulebooks/0/rules/` |
| Object / rulebook link | `object-link/`, `rulebook-link/` |
| Object Analyzer | `object-analyzer/` |
| Object Report | `object-report/` |

Security tab: `security/tab/security_views.py` registers on NetBox object detail pages; context in `security/tab/context.py`.

## Front-end

Rules / matrix: Django templates + plugin JS. Object Analyzer: **@xyflow/react** (import map in template).

Assets: `plugin_assets/` → `/plugins/netbox-nsm/assets/…`

## Tests

`netbox_nsm/tests/` — Django test runner (not pytest). See [docs/TESTING.md](docs/TESTING.md).

CLI: `manage.py nsm_object_report` — aggregated address/group health report.
