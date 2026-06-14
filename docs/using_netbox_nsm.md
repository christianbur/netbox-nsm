# Using netbox-nsm

Documentation plugin — no firewall configuration. Overview: [README](../README.md).

## Prerequisites

```python
PLUGINS = ["netbox_custom_objects", "netbox_nsm"]
```

```bash
./manage.py migrate netbox_custom_objects --no-input
./manage.py migrate netbox_nsm --no-input
```

## Setup wizard

**Security → Configuration → Setup**

| § | Content | Action |
|---|---------|--------|
| 1 | Menu / panel labels | Set labels |
| 2 | Custom objects | **Add all Custom Object Types** (7 `nsm_*` COTs) |
| 3 | Type config | **Add all TypeConfigs** |
| 4 | Demo | Optional **Starter demo** (recommended) |

Set `setup_allow_destructive_actions: True` in `PLUGINS_CONFIG` for demos.

## Built-in COTs

| Slug | Purpose |
|------|---------|
| `nsm_zones` | Security zones |
| `nsm_addresses` | Addresses / groups |
| `nsm_labels` | Labels |
| `nsm_services` | Services (port/proto) |
| `nsm_action` | Actions (permit, deny, …) |
| `nsm_business_apps` | Business apps |
| `nsm_network_apps` | Network apps |

Per-type behaviour: `nsm_config` in COT `comments` or **Security → Type Config**.

## Security panel & links

On supported NetBox objects (prefix, IP, device, VM, interface, …):

1. **+ Assign** — link an NSM object (zone, service, …)
2. **Link type:** direct, inherit to IPAM children, inherit to group members
3. **Reverse view** — from an NSM object, all linked hosts and rulebook references

Rule columns and the panel share the same **type config** entries — no separate zone model per product.

### Custom object types

1. Create a COT in **netbox-custom-objects**
2. **Security → Type Config → + Add** (matching, panel slugs, linkable in panel)
3. Use the type config in rulebook fields and the panel

## Rulebooks

**Security → Rulebooks**

- Fields and hierarchy per rulebook (source, destination, service, action, …)
- **Rules** tab: table, grouping, filter (`nsm_q`), matrix view
- **All Rules:** `/plugins/netbox-nsm/rulebooks/0/rules/` (read-only, all rulebooks)
- Rules are COT rows (`nsm_rb_*`), not `netbox_nsm_rule` ORM

Deployed COT rulebooks: `/plugins/netbox-nsm/rulebooks/cot/<slug>/rules/`

## IP Analysis

- **Panel:** loupe on analyzable objects
- **URL:** `/plugins/netbox-nsm/ip-analysis/`
- **API:** `GET/POST /api/plugins/netbox-nsm/ip-analysis/`

## Object Analyzer

**Security → Analysis → Object Analyzer** — xyflow graph from object to links and rulebooks.

## REST API

| Endpoint | Purpose |
|----------|---------|
| `/api/plugins/netbox-nsm/nsm-configs/<slug>/` | Read/write `nsm_config` in COT comments |
| `/api/plugins/netbox-nsm/object-links/` | Security panel links (`nsm_object_link`) |
| `/api/plugins/netbox-nsm/ip-analysis/` | Address analysis (JSON) |

Rules and policy objects: **netbox-custom-objects** API. Rulebook assignments: `object-links` with `link_type=rulebook`.

Portable schema: `POST /api/plugins/custom-objects/schema/apply/` with `netbox_nsm/schema/nsm_portable_schema.json`.

## Demos

| Demo | Creates | Trigger |
|------|---------|---------|
| **Starter** | Zones, services, actions + rulebooks “Demo - Zone Matrix”, “Demo - Addresses” | Setup §4, synchronous |
| **Enterprise DC** | DCIM/IPAM scenario + rulebooks | Setup §4, empty IP DB only |
| **Addresses Million Scale** | Bench rulebook `nsm_rb_bench_addresses` | `scripts/create_addresses_million_scale.py`, RQ |

## Configuration

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "top_level_menu": True,
        "setup_menu": True,
        "setup_allow_destructive_actions": False,
        "assignments_menu": False,
        "menu_label": "Security",
        "panel_label": "Security",
    },
}
```

Restart NetBox after changes.

## Menu

```
Security
├── Configuration → Setup, Type Config
├── Rulebooks
└── Analysis → Object Analyzer

Custom Objects → NSM (Zones, Addresses, …)
```

## See also

- [DATABASE.md](DATABASE.md) — tables
- [RULE_DATA_STORAGE.md](RULE_DATA_STORAGE.md) — storage layers
- [ARCHITECTURE.md](../ARCHITECTURE.md) — code
