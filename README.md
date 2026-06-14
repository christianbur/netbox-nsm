# netbox-nsm

NetBox-Plugin für **Security Policy Dokumentation** (Zonen, Rulebooks, Object Links).  
Kein Push zu Firewalls — nur Inventar + Policy in NetBox.

**Status:** WIP · **NetBox:** 4.5–4.6 · **Plugin:** 0.4.2 · **Abhängigkeit:** [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects)

## Features

- **Security Panel** auf Prefix, IP, Device, VM, Custom Objects — `+ Assign` für Zonen/Adressen/…
- **Rulebooks** mit flexiblen Spalten (Zonen, Adressen, Labels, …)
- **Rules** — Tabelle, Gruppierung, Zone-Matrix
- **IP Analysis** — Adressauflösung (Panel-Lupe oder `/plugins/netbox-nsm/ip-analysis/`)
- **Object Analyzer** — Graph aus beliebigem NetBox-Objekt

## Installation

```bash
pip install netbox-nsm
```

```python
PLUGINS = ["netbox_custom_objects", "netbox_nsm"]

PLUGINS_CONFIG = {
    "netbox_nsm": {
        "menu_label": "Security",
        "panel_label": "Security",
        "setup_menu": True,
        "setup_allow_destructive_actions": True,  # Demos; in Prod aus
    },
}
```

```bash
./manage.py migrate netbox_custom_objects --no-input
./manage.py migrate netbox_nsm --no-input
```

## Erster Start

**Security → Configuration → Setup** — Abschnitte **1 → 2 → 3** (Labels, COTs, TypeConfigs), dann optional **4 Starter demo**.

Danach: Prefix öffnen → Security Panel → `+ Assign` → Zone. Rulebooks unter **Security → Rulebooks**.

Details: [docs/using_netbox_nsm.md](docs/using_netbox_nsm.md)

## API

`/api/plugins/netbox-nsm/` — `nsm-configs/<slug>/`, `object-links/`, `ip-analysis/`  
Regeln und Policy-Objekte: **netbox-custom-objects** API.

## Demos

| Demo | Wo | Hinweis |
|------|-----|---------|
| Starter | Setup §4 | Sync, empfohlen — Zone Matrix + Addresses-Schema |
| Enterprise DC | Setup §4 | Nur leere IPAM-DB |
| Addresses Million Scale | CLI `scripts/create_addresses_million_scale.py` | Bench, RQ-Worker nötig |

## Doku

| Datei | Inhalt |
|-------|--------|
| [docs/using_netbox_nsm.md](docs/using_netbox_nsm.md) | Bedienung |
| [docs/DATABASE.md](docs/DATABASE.md) | PostgreSQL-Tabellen |
| [docs/RULE_DATA_STORAGE.md](docs/RULE_DATA_STORAGE.md) | Datenmodell UI vs. DB |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Code für Entwickler |
| [CHANGELOG.md](CHANGELOG.md) | Versionen |

## Lizenz

[LICENSE](LICENSE)
