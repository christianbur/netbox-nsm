# netbox-nsm — Docker (netbox-dev)

Entwicklung und Betrieb des **netbox-nsm**-Plugins im Homelab-Stack `docker/netbox_dev`.

Stack-Infrastruktur (Postgres, Branching, 400-Fix, `down -v`):  
`docker/netbox_dev/DOCKER.md`

---

## Voraussetzungen

- Laufender Stack `netbox-dev` (Compose unter `homelab/docker/netbox_dev`)
- Plugin-Mount: `./netbox-nsm` → Container `/opt/netbox-nsm`
- In `PLUGINS`: `netbox_custom_objects` **vor** `netbox_nsm` (siehe `docker/netbox_dev/config/dev-plugins.py`)
- `netbox_branching` bleibt **nach** `netbox_nsm` (Stack-Vorgabe, nicht NSM-spezifisch)

NSM-relevante Plugin-Config in `dev-plugins.py`:

```python
PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_allow_destructive_actions": True,
    },
}
```

---

## Erststart / DB-Reset (`down -v` am Stack)

NSM wird vom Stack-Bootstrap mit migriert — **kein separates NSM-Setup** nötig, wenn Bootstrap durchlief.

```bash
cd /home/christian/homelab
./tools/docker-cmd.py netbox_dev config-decrypt
chmod +x docker/netbox_dev/custom-cont-init.d/*.sh
./tools/docker-cmd.py netbox_dev up -d --build
```

Logs:

```bash
docker logs netbox-dev 2>&1 | grep -E 'migrate netbox_nsm|netbox-plugin-migrate.*done'
```

Danach im UI: **Security → Configuration → Setup** (TypeConfigs / Demo).

---

## Code ändern (editable install)

Der Mount macht lokale Änderungen sofort im Container sichtbar; nach Python-/Template-Änderungen oft:

```bash
docker restart netbox-dev
```

Kein Image-Rebuild für reines NSM-Python/HTML/JS.

Nach neuen **Migrationen** im Repo:

```bash
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_nsm --no-input'
docker restart netbox-dev
```

Oder das Stack-Skript (alle Plugins, empfohlen wenn unsicher):

```bash
docker exec netbox-dev bash /opt/netbox-dev-scripts/netbox-plugin-migrate.sh
docker restart netbox-dev
```

---

## Migrationen (nur NSM)

`netbox_nsm` muss in `/config/configuration.py` unter `PLUGINS` stehen und das Paket muss installiert sein (`pip install -e /opt/netbox-nsm` — erledigt Bootstrap).

**Reihenfolge:** immer zuerst `netbox_custom_objects`, dann `netbox_nsm`.

```bash
docker exec netbox-dev python3 /opt/netbox-dev-config/apply_dev_plugins.py
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_custom_objects --no-input'
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_nsm --no-input'
docker restart netbox-dev
```

Entspricht `./manage.py migrate` für alle Apps, wenn die volle Plugin-Liste in `PLUGINS` aktiv ist:

```bash
docker exec netbox-dev python3 /opt/netbox-dev-config/apply_dev_plugins.py
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate --no-input'
docker restart netbox-dev
```

`manage.py`: `/app/netbox/netbox/manage.py`

---

## Setup-Seite & Demos

Nach Migrationen: **Security → Configuration → Setup**

| Aktion | Beschreibung |
|--------|----------------|
| Import Custom Object Types | Built-in COTs (Zones, Addresses, …) |
| Create TypeConfigs | NSM TypeConfigs |
| Demo: Zone Matrix / Addresses | Starter-Rulebooks |
| Enterprise Demo | Großes DC-Szenario (optional) |

`setup_allow_destructive_actions: True` nur auf **netbox-dev** (siehe `dev-plugins.py`).

Enterprise-Demo per Shell (wenn Setup-Button nicht reicht):

```bash
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py shell < /opt/netbox-nsm/netbox_nsm/demos/enterprise_dc/import.py'
```

(Pfad prüfen — Import liegt unter `netbox_nsm/demos/enterprise_dc/import.py` im Mount.)

---

## NSM in `PLUGINS` aktivieren / deaktivieren

Nur in Repo editieren: `docker/netbox_dev/config/dev-plugins.py` — `netbox_nsm` in Liste `PLUGINS` eintragen oder entfernen.

```bash
docker exec netbox-dev python3 /opt/netbox-dev-config/apply_dev_plugins.py
docker restart netbox-dev
```

`netbox_nsm` nicht als letztes Plugin eintragen (das ist `netbox_branching` im Stack).

---

## HTTP 400 Bad Request

Fast immer **falsche `ALLOWED_HOSTS`** in `/config/configuration.py` (ein String mit Kommas statt Liste).

```bash
docker exec netbox-dev python3 /opt/netbox-dev-config/fix_allowed_hosts.py
docker exec netbox-dev python3 /opt/netbox-dev-config/apply_dev_plugins.py
docker exec netbox-dev bash /opt/netbox-dev-scripts/netbox-plugin-migrate.sh
docker restart netbox-dev
```

Prüfen (mehrere Host-Einträge, kein Komma **in** einem String):

```bash
docker exec netbox-dev grep '^ALLOWED_HOSTS' /config/configuration.py
```

Stack-Details: `docker/netbox_dev/DOCKER.md#http-400-bad-request`

---

## Typische Fehler (NSM)

### `No installed app with label 'netbox_nsm'`

- `PLUGINS` enthält `netbox_nsm` nicht → `apply_dev_plugins.py`
- Paket nicht installiert → Bootstrap-Skript (pip `-e /opt/netbox-nsm`)

```bash
docker exec netbox-dev bash /opt/netbox-dev-scripts/netbox-plugin-migrate.sh
docker exec netbox-dev grep PLUGINS /config/configuration.py
```

### `netbox_nsm_typeconfig` (oder andere NSM-Tabelle) does not exist

Plugin-Migration nicht gelaufen, während uWSGI schon startete:

```bash
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_nsm --no-input'
docker restart netbox-dev
```

### Setup: „Migrations pending“ / `netbox_custom_objects_…` does not exist

Zuerst Custom Objects migrieren:

```bash
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_custom_objects --no-input'
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py migrate netbox_nsm --no-input'
```

### `relation "netbox_custom_objects_customobjecttype" does not exist`

`netbox_custom_objects` fehlt in DB — siehe Migrationen oben.

### Änderungen am Plugin sichtbar?

1. Datei unter `docker/netbox_dev/netbox-nsm/` gespeichert?
2. `docker restart netbox-dev`
3. Browser-Cache / Hard-Reload

---

## Tests im Container

```bash
docker exec netbox-dev bash -c 'cd /app/netbox/netbox && python3 manage.py test netbox_nsm.tests --no-input'
```

Integration (wenn konfiguriert):

```bash
docker exec netbox-dev bash -c 'cd /opt/netbox-nsm && python3 tests/integration_test.py'
```

---

## Pfade (Übersicht)

| Was | Host | Container |
|-----|------|-----------|
| Plugin-Quellcode | `homelab/docker/netbox_dev/netbox-nsm/` | `/opt/netbox-nsm` |
| Stack-Config | `homelab/docker/netbox_dev/config/` | `/opt/netbox-dev-config` |
| NetBox `configuration.py` | Volume `netbox-dev-config` | `/config/configuration.py` |
| Migrate-Skript | `homelab/docker/netbox_dev/scripts/` | `/opt/netbox-dev-scripts/` |

---

## Siehe auch

- [using_netbox_nsm.md](using_netbox_nsm.md) — Funktionen, Setup-UI, API
- [../README.md](../README.md) — Plugin-Überblick
- [../../DOCKER.md](../../DOCKER.md) — gesamter netbox-dev-Stack
