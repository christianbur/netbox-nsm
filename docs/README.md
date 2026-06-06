<div align="center">

# netbox-nsm Documentation

**Document network security policy inside NetBox**

[![NetBox 4.6.x](https://img.shields.io/badge/NetBox-4.6.x-0088cc?style=flat-square)](https://netboxlabs.com/)
[![Plugin 0.2.0](https://img.shields.io/badge/plugin-0.2.0-2ea043?style=flat-square)](../README.md)
[![WIP](https://img.shields.io/badge/status-work%20in%20progress-yellow?style=flat-square)](../README.md)

[← Project README](../README.md) · [Architecture](../ARCHITECTURE.md)

</div>

---

## Start here

| Guide | Audience | Description |
|---|---|---|
| **[Using netbox-nsm](using_netbox_nsm.md)** | Operators, firewall teams | Full feature walkthrough with screenshots |
| **[Database tables](DATABASE.md)** | Admins, integrators | PostgreSQL schema reference |
| **[Architecture](../ARCHITECTURE.md)** | Developers | Code layout, models, extension points |

---

## Learning paths

### 1 · First hour — get NSM running

```mermaid
flowchart LR
  A[Install plugins] --> B[Migrate DB]
  B --> C[Setup wizard 1-3]
  C --> D[Assign first zone link]
  D --> E[Open Rules tab]
```

| Step | Where | Doc |
|---|---|---|
| Install `netbox-custom-objects` + `netbox_nsm` | `configuration.py` | [Prerequisites](using_netbox_nsm.md#prerequisites--first-start) |
| Run migrations | `manage.py migrate` | [Prerequisites](using_netbox_nsm.md#prerequisites--first-start) |
| Setup Sections 1–3 | Security → Setup | [Setup Wizard](using_netbox_nsm.md#setup-wizard) |
| Link a prefix to a zone | Prefix → **+ Assign** | [Security Panel](using_netbox_nsm.md#security-panel) |
| Browse demo rules | Rulebook → Rules | [Rules grid](using_netbox_nsm.md#rules-grid) |

### 2 · Core workflow — Security Panel

The **Security Panel** is the centre of NSM: connect IPAM/DCIM objects to zones, addresses,
labels, and see matching rulebooks.

| Concept | Doc section |
|---|---|
| **+ Assign** / ObjectLinks | [Workflow](using_netbox_nsm.md#workflow-assign-view-reverse-lookup) |
| **Inheritance in the panel** | [Inheritance in the Security Panel](using_netbox_nsm.md#inheritance-in-the-security-panel) — Direct vs *Inherited*, Assign Link propagation, overrides |
| Macro vs micro zones | [Macro zones vs micro zones](using_netbox_nsm.md#macro-zones-vs-micro-zones) |
| Direct vs inherited (summary) | [Inherited Links](using_netbox_nsm.md#inherited-links) |
| Custom object types | [Extending NSM](using_netbox_nsm.md#extending-nsm-custom-and-native-object-types) |

### 3 · Policy documentation

| Feature | Menu path | Doc |
|---|---|---|
| Rulebooks | Security → Rulebooks | [Security Rulebooks](using_netbox_nsm.md#security-rulebooks) |
| Policy grid (AG Grid) | Rulebook → Rules | [Rules grid](using_netbox_nsm.md#rules-grid) |
| Zone matrix | Rulebook → Rules (matrix toolbar) | [Zone Matrix](using_netbox_nsm.md#zone-matrix) |
| All Rules (global view) | Rulebooks → **All Rules** | [Rulebook List](using_netbox_nsm.md#all-rules-virtual-rulebook) |
| IP Analysis | Security → Analysis → IP Analysis | [IP Analysis](using_netbox_nsm.md#ip-analysis) |
| Object Analyzer | Security → Analysis → Object Analyzer | [Object Analyzer](using_netbox_nsm.md#object-analyzer) |

### 4 · Integration

| Topic | Doc |
|---|---|
| REST API | [REST API Reference](using_netbox_nsm.md#rest-api-reference) |
| AG Grid + xyflow licenses | [Third-party UI libraries](using_netbox_nsm.md#third-party-ui-libraries) |

---

## Screenshot gallery

All images live in [`docs/img/`](img/). Regenerate with [`make_screenshots.py`](img/make_screenshots.py).

| Image | Topic |
|---|---|
| `01-setup.png` | Setup wizard (4 sections) |
| `02-type-config-list.png` · `03-type-config-detail.png` | Type Config |
| `05-rulebook-list.png` · `06-rulebook-detail.png` | Rulebooks |
| `07-policy-rules.png` · `07-policy-rules-demo-group.png` · `11-rule-add.png` | Rules grid (Enterprise + Demo Group view) & add form |
| `07-zone-detail.png` · `12-prefix-security-panel.png` · `17-assign-picker.png` · `17-assign-link-propagation-types.png` | Security Panel & Assign Link (form + Link type propagation dropdown) |
| `08-builtin-types.png` | Custom Object Types |
| `09-zone-matrix.png` · `09-zone-matrix-demo-undirected.png` · `09-zone-matrix-demo-directed.png` | Zone matrix (Enterprise + Demo undirected 2×2 subset + Demo full grid) |
| `10-ip-analysis.png` | IP Analysis |
| `11-object-analyzer.png` | Object Analyzer |

---

## Menu map

```
Security                          Custom Objects
├── Configuration                 └── NSM (Zones, Addresses, …)
│   ├── Setup
│   └── Type Config
├── Rulebooks
├── Analysis
│   ├── IP Analysis          → rulebooks/4/ipanalysis/
│   └── Demo – Object Analyzer
└── (optional Assignments)
```

---

## Third-party UI

| Library | License | Used in |
|---|---|---|
| [AG Grid Community 33.2.4](https://github.com/ag-grid/ag-grid) | MIT | Rules, Matrix, All Rules |
| [@xyflow/react 12](https://github.com/xyflow/xyflow) | MIT | Object Analyzer |

Details: [Third-party UI libraries](using_netbox_nsm.md#third-party-ui-libraries)

---

## Status & limitations

- **Work in progress** — not for production (0.2.x); see [CHANGELOG](../CHANGELOG.md)
- **Documentation only** — no rule push to firewalls
- **Requires** [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects)
