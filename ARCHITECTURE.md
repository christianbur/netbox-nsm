# netbox-nsm — Architektur

Für Entwickler. Bedienung: [docs/using_netbox_nsm.md](docs/using_netbox_nsm.md)

## Abhängigkeit

Policy-Daten (Zonen, Regeln, Links) liegen als **Custom Object Types** in [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects).

- Typ-Verhalten: YAML `nsm_config` in `CustomObjectType.comments` (`objects/nsm_config.py`)
- Instanzen: COT-Zeilen (`nsm_zone`, `nsm_rb_*`, `nsm_object_link`, …)
- Built-in Schemas: `objects/builtin_types.py`, Sync via Setup oder Schema-API

## Datenmodell (0.4.x)

| Schicht | Wo | Beispiele |
|---------|-----|-----------|
| UI-Labels | `PLUGINS_CONFIG` | `menu_label`, `panel_label` |
| Typ-Metadaten | COT `comments` → `nsm_config` | `panel`, `rule_view`, `rulebook` |
| Instanzen | COT-Zeilen | Zonen, Regeln, Links |

`nsm_object_link`: Panel-Links (`link_type=policy`) und Rulebook-Zuweisungen (`link_type=rulebook`).

Details: [docs/DATABASE.md](docs/DATABASE.md), [docs/RULE_DATA_STORAGE.md](docs/RULE_DATA_STORAGE.md)

## Layout

```
netbox_nsm/
├── analysis/          IP/Adress-Analyse
├── analyzer/          Object-Analyzer-Graph
├── api/               object-links, nsm-configs, ip-analysis
├── objects/           builtin_types, nsm_config, IPAM-Vererbung
├── rulebooks/         Grid, Rules-Tab, Matrix, Views
├── security/          Security Panel, object-rules API
├── demos/             Starter, enterprise_dc, addresses_million_scale
├── views/             Setup, IP Analysis, Object Analyzer
└── tests/
```

Portable Schema: `nsm-schema.json` → `POST /api/plugins/custom-objects/schema/apply/`

## Wichtige URLs

| View | Pfad |
|------|------|
| Setup | `setup/` |
| Object Config | `type-config/` |
| Rulebooks / COT Rules | `rulebooks/`, `rulebooks/cot/<slug>/rules/` |
| All Rules | `rulebooks/0/rules/` |
| Object / Rulebook Link | `object-link/`, `rulebook-link/` |
| IP Analysis | `ip-analysis/` |
| Object Analyzer | `object-analyzer/` |

Security Panel: `template_content.py` → `NsmSecurityLinksExtension`

## Front-end

Rules/Matrix: Django-Templates + Plugin-JS. Object Analyzer: **@xyflow/react** (Import-Map in Template).

Assets: `plugin_assets/` → `/plugins/netbox-nsm/assets/…`

## Tests

`netbox_nsm/tests/` — Django-Testrunner (nicht pytest). Siehe [docs/TESTING.md](docs/TESTING.md).

CLI: `manage.py nsm_analyze_address_sync` — IPAM ↔ `nsm_address` Report.
