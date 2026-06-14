# Bench: 200k addresses + 13k rules (COT rulebooks)

Standalone load generator for performance and UI testing. **Not** part of the Setup wizard.

Policy rules are stored as **Custom Object rows** on a deployed COT rulebook (`nsm_rb_bench_addresses`) with `source_addresses` / `destination_addresses` multiobject fields — **not** native `Rulebook` / `Rule` / `RuleObjectItem`.

## Dateien

| Path | Rolle |
|------|--------|
| `scripts/create_addresses_million_scale.py` | CLI-Einstieg |
| `netbox_nsm/demos/addresses_million_scale.py` | Implementierung |
| `netbox_nsm/demos/cot_demo_common.py` | Gemeinsame COT-Helfer |

## Voraussetzungen

1. Stack läuft: `cd docker/netbox_dev && docker compose up -d netbox netbox-worker`
2. Plugin-Mount aktiv: `./netbox-nsm` → `/opt/netbox-nsm` (sonst Image neu bauen)
3. NSM Setup abgeschlossen:
   - **Import all types** (COTs: `nsm_address`, `nsm_service`, `nsm_action`, …)
   - **Create all TypeConfigs**
   - Alternativ: Setup → **Starter demo** (legt u. a. Standard-Services/Actions an)

Das Skript legt bei Bedarf automatisch das Rulebook **`nsm_rb_bench_addresses`** an (Template 0002 — nur Adressen).

## Datenmodell

Alle Bench-Objekte nutzen das Präfix `bench-` (getrennt von Setup-Demos `demo-*`).

### Adress-Hierarchie (vereinfacht für COT)

Die frühere Selbst-Referenz über `nsm_addresses.group` entfällt. Stattdessen:

```
2 000 Subnetze   bench-net-00000 … bench-net-01999   (nsm_address + ipam.Prefix /24)
  └─ bis 200 000 Hosts   bench-ip-0000000 …          (nsm_address + ipam.IPAddress /32 + prefix-FK)
```

IP-Raum: fortlaufende `/24`-Blöcke in **10.128.0.0/9** (2 000 Subnetze × 100 Hosts).

Region/Site-Container (`bench-reg-*`, `bench-site-*`) werden im COT-Modell nicht mehr erzeugt (Address Groups können nur `nsm_address`-Mitglieder halten, keine verschachtelten Gruppen).

### Policy-Regeln (COT)

Standard **13 000** Regeln in `nsm_rb_bench_addresses`:

- Name: `bench-rule-00001` …
- **Source / Destination:** je 1–20 zufällige Leaf-Adressen (deterministischer Seed)
- **Service / Action:** eingebaute COT-Objekte (`HTTPS`, `SSH`, … / `Permit`, `Deny`)

## Ausführung

```bash
cd /home/christian/homelab/docker/netbox_dev
docker compose up -d netbox netbox-worker

# Vollständiger Lauf (200k IPAM-Zeilen + Regeln — dauert lange)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py

# Smoke-Test (Sekunden bis wenige Minuten)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --leaf-count 1000 --rule-count 100

# Nur Regeln (Leaves bereits vorhanden)
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-addresses

# Nur Adressen
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --skip-rules

# Bench-Daten entfernen
docker compose exec netbox python3 /opt/netbox-nsm/scripts/create_addresses_million_scale.py \
  --purge
```

Alternativ über Django-Shell (gleiche Logik):

```bash
docker compose exec netbox python /opt/netbox/netbox/manage.py shell
```

```python
from netbox_nsm.demos.addresses_million_scale import create_addresses_million_scale
print(create_addresses_million_scale(leaf_count=1000, rule_count=100))
```

### CLI-Optionen

| Option | Default | Beschreibung |
|--------|---------|--------------|
| `--rulebook-slug` | `nsm_rb_bench_addresses` | Ziel-COT-Rulebook |
| `--rulebook-id` | — | Legacy: COT per Primary Key |
| `--leaf-count` | `200000` | Anzahl Host-Adressen |
| `--rule-count` | `13000` | COT-Regeln |
| `--skip-addresses` | aus | IPAM + Adressen überspringen |
| `--skip-rules` | aus | Regeln überspringen |
| `--keep-rules` | aus | Bestehende `bench-rule-*` nicht löschen |
| `--purge` | aus | Bench-Daten löschen und beenden |

## Erwartete Laufzeit / Ausgabe

| Skalierung | Größenordnung |
|------------|----------------|
| 1 000 Leaves + 100 Regeln | Sekunden |
| 200 000 Leaves | viele Minuten (DB, Platte, Postgres-Tuning) |
| 13 000 Regeln | Minuten (M2M-Zuweisungen) |

Beispielausgabe (Smoke-Test):

```text
Rulebook Bench Addresses (nsm_rb_bench_addresses, pk=…): 1,000 leaves, 100 new rules, … multiobject assignments, 12.34s
```

Rulebook in der UI: **Security → Rulebooks → Bench Addresses**.

## Verwandte Demos

| Demo | Rulebook | Skript |
|------|----------|--------|
| Starter | `nsm_rb_demo` | Setup → Starter demo |
| Enterprise DC | (manuell COT) | `netbox_nsm/demos/enterprise_dc/import.py` — Rulebooks übersprungen |
