# netbox-nsm — Architecture

For developers. Operations: [docs/using_netbox_nsm.md](docs/using_netbox_nsm.md)

## Dependency

Policy data (zones, rules, links) is stored as **Custom Object Types** via [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects).

- Type behaviour: YAML `nsm_config` in `CustomObjectType.comments` (`objects/nsm_config.py`)
- Instances: COT rows (`nsm_zone`, `nsm_rb_*`, `nsm_object_link`, …)
- Built-in schemas: `objects/builtin_types.py`; sync via Setup or schema API

## Data model (0.4.x)

| Layer | Where | Examples |
|-------|-------|----------|
| UI labels | `PLUGINS_CONFIG` | `menu_label`, `panel_label` |
| Type metadata | COT `comments` → `nsm_config` | `panel`, `rule_view`, `rulebook` |
| Instances | COT rows | zones, rules, links |

`nsm_object_link`: panel links (`link_type=policy`) and rulebook assignments (`link_type=rulebook`).

Details: [docs/DATABASE.md](docs/DATABASE.md), [docs/RULE_DATA_STORAGE.md](docs/RULE_DATA_STORAGE.md)

## Layout

```
netbox_nsm/
├── analysis/          IP / address analysis
├── analyzer/          Object Analyzer graph
├── api/               object-links, nsm-configs, ip-analysis
├── objects/           builtin_types, nsm_config, IPAM inheritance
├── rulebooks/         grid, Rules tab, matrix, views
├── security/          Security panel, object-rules API
├── demos/             starter, enterprise_dc, addresses_million_scale
├── views/             Setup, Object Analyzer, Object Report (IP analysis is applet + API only)
└── tests/
```

Portable schema: `nsm-schema.json` → `POST /api/plugins/custom-objects/schema/apply/`

## Key URLs

| View | Path |
|------|------|
| Setup | `setup/` |
| Object config | `type-config/` |
| Rulebooks / COT rules | `rulebooks/`, `rulebooks/cot/<slug>/rules/` |
| All rules | `rulebooks/0/rules/` |
| Object / rulebook link | `object-link/`, `rulebook-link/` |
| IP analysis (legacy redirect) | `ip-analysis/` → Object Analyzer (standalone page removed; applet + APIs only) |
| Object Analyzer | `object-analyzer/` |
| Object Report | `object-report/` |

Security panel: `template_content.py` → `NsmSecurityLinksExtension`

## Front-end

Rules / matrix: Django templates + plugin JS. Object Analyzer: **@xyflow/react** (import map in template).

Assets: `plugin_assets/` → `/plugins/netbox-nsm/assets/…`

## Tests

`netbox_nsm/tests/` — Django test runner (not pytest). See [docs/TESTING.md](docs/TESTING.md).

CLI: `manage.py nsm_analyze_address_sync` — IPAM ↔ `nsm_address` report.
