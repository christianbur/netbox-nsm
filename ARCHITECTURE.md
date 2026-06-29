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

## Layout

```
netbox_nsm/
├── bundles/           # Portable schema JSON, Setup wizard views, dispatch/apply/sync
│   ├── builtin/       # nsm_schema.json, demo bundles (*.json only)
│   ├── setup_context.py
│   ├── dispatch.py
│   └── schema_builder.py
├── bench/             # Standalone performance/bench generators (not Setup)
├── security/tab/      # Security tab context, badge, linked-object rows
├── objects/           # nsm_config, type specs, group M2M
├── addresses/         # Address COT schema, IPAM FK helpers
├── rulebooks/         # Grid, Rules tab, matrix, COT views
├── security/          # Rule references, panel-link actions, host analysis, object links
├── ui/                  # Shared split-action helpers
├── views/               # Type metadata, object analyzer/report, rulebook links
├── analysis/            # IP / address analysis
├── analyzer/            # Object Analyzer graph
├── api/                 # object-links, nsm-configs, ip-analysis
└── tests/
```

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
