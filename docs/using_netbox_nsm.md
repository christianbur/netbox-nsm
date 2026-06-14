# Using netbox-nsm

Dokumentations-Plugin — keine Firewall-Konfiguration. Übersicht: [README](../README.md).

## Voraussetzungen

```python
PLUGINS = ["netbox_custom_objects", "netbox_nsm"]
```

```bash
./manage.py migrate netbox_custom_objects --no-input
./manage.py migrate netbox_nsm --no-input
```

## Setup-Wizard

**Security → Configuration → Setup**

| § | Inhalt | Aktion |
|---|--------|--------|
| 1 | Menü-/Panel-Titel | Labels setzen |
| 2 | Custom Objects | **Add all Custom Object Types** (7 `nsm_*` COTs) |
| 3 | TypeConfig | **Add all TypeConfigs** |
| 4 | Demo | Optional **Starter demo** (empfohlen) |

`setup_allow_destructive_actions: True` in `PLUGINS_CONFIG` für Demos.

## Built-in COTs

| Slug | Zweck |
|------|-------|
| `nsm_zones` | Security Zones |
| `nsm_addresses` | Adressen / Gruppen |
| `nsm_labels` | Labels |
| `nsm_services` | Services (Port/Proto) |
| `nsm_action` | Aktionen (permit, deny, …) |
| `nsm_business_apps` | Business Apps |
| `nsm_network_apps` | Network Apps |

Verhalten pro Typ: `nsm_config` in COT-`comments` oder **Security → Type Config**.

## Security Panel & Links

Auf unterstützten NetBox-Objekten (Prefix, IP, Device, VM, Interface, …):

1. **+ Assign** — NSM-Objekt verknüpfen (Zone, Service, …)
2. **Link-Typ:** Direct, Inherit to IPAM children, Inherit to group members
3. **Reverse View** — vom NSM-Objekt alle verknüpften Hosts + Rulebook-Referenzen

Regelspalten und Panel nutzen dieselben **TypeConfig**-Einträge — kein separates Zonen-Modell pro Produkt.

### Eigene Objekttypen

1. COT in **netbox-custom-objects** anlegen
2. **Security → Type Config → + Add** (Matching, Panel-Slugs, Linkable in panel)
3. TypeConfig in Rulebook-Feldern und Panel nutzen

## Rulebooks

**Security → Rulebooks**

- Felder/Hierarchie pro Rulebook (Source, Destination, Service, Action, …)
- **Rules**-Tab: Tabelle, Gruppierung, Filter (`nsm_q`), Matrix-Ansicht
- **All Rules:** `/plugins/netbox-nsm/rulebooks/0/rules/` (read-only, alle Rulebooks)
- Regeln sind COT-Zeilen (`nsm_rb_*`), nicht `netbox_nsm_rule`-ORM

Deployed COT-Rulebooks: `/plugins/netbox-nsm/rulebooks/cot/<slug>/rules/`

## IP Analysis

- **Panel:** Lupe auf analysierbaren Objekten
- **URL:** `/plugins/netbox-nsm/ip-analysis/`
- **API:** `GET/POST /api/plugins/netbox-nsm/ip-analysis/`

## Object Analyzer

**Security → Analysis → Object Analyzer** — Graph (xyflow) von Objekt zu Links und Rulebooks.

## REST API

| Endpoint | Inhalt |
|----------|--------|
| `/api/plugins/netbox-nsm/nsm-configs/<slug>/` | `nsm_config` in COT-Comments lesen/schreiben |
| `/api/plugins/netbox-nsm/object-links/` | Security-Panel-Links (`nsm_object_link`) |
| `/api/plugins/netbox-nsm/ip-analysis/` | Adressanalyse (JSON) |

Regeln und Policy-Objekte: **netbox-custom-objects** API. Rulebook-Zuweisungen: `object-links` mit `link_type=rulebook`.

Portable Schema: `POST /api/plugins/custom-objects/schema/apply/` mit `netbox_nsm/schema/nsm_portable_schema.json`.

## Demos

| Demo | Erzeugt | Auslöser |
|------|---------|----------|
| **Starter** | Zonen/Services/Actions + Rulebooks „Demo - Zone Matrix“, „Demo - Addresses“ | Setup §4, synchron |
| **Enterprise DC** | DCIM/IPAM-Szenario + Rulebooks | Setup §4, nur leere IP-DB |
| **Addresses Million Scale** | Bench-Rulebook `nsm_rb_bench_addresses` | `scripts/create_addresses_million_scale.py`, RQ |

## Konfiguration

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

NetBox nach Änderung neu starten.

## Menü

```
Security
├── Configuration → Setup, Type Config
├── Rulebooks
└── Analysis → Object Analyzer

Custom Objects → NSM (Zones, Addresses, …)
```

## Weiterführend

- [DATABASE.md](DATABASE.md) — Tabellen
- [RULE_DATA_STORAGE.md](RULE_DATA_STORAGE.md) — Speicherschichten
- [ARCHITECTURE.md](../ARCHITECTURE.md) — Code
