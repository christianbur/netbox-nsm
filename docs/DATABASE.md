# NSM Database Tables

[← Documentation home](README.md) · [How rule data is stored](RULE_DATA_STORAGE.md) · [Using netbox-nsm](using_netbox_nsm.md) · [Architecture](../ARCHITECTURE.md)

NSM persists its own data in the **NetBox PostgreSQL database**. Django uses the app label
`netbox_nsm`; table names follow the pattern `netbox_nsm_<model_name>` (lowercase).

Security **object instances** (zones, addresses, labels, services, actions, rulebook rules,
policy links, rulebook host assignments) are **not** stored in native NSM tables. They live in
`netbox-custom-objects` COT rows (`nsm_object_link` for panel links and rulebook assignments).
Type metadata (`sort_order`, `display_template`, `areas`, `links`, `rulebook`) lives in each COT type's **`comments`** field
(`nsm_config` YAML). Plugin-wide UI labels use
**`PLUGINS_CONFIG`** only (`menu_label`, `panel_label`, `setup_menu`, `setup_allow_destructive_actions`, `top_level_menu`, `bundle_paths`, `builtin_bundles`).

---

## Quick inspection

```sql
-- PostgreSQL (inside netbox-dev-db or your NetBox DB)
\dt netbox_nsm_*
```

```bash
# Django shell
python manage.py dbshell -c "\dt netbox_nsm_*"
```

---

## Native NSM models (0.4.2+)

| Model | Purpose |
|-------|---------|
| `RulebookListProxy` | **Unmanaged** NetBoxTable / object-list shim for the rulebook list UI only. Marked `_netbox_private` — **no physical table**, **not** a permission source. Rulebook access is enforced per deployed COT via `netbox_custom_objects` permissions on each rulebook's rule model (see `rulebooks/permissions.py`). |

Type Metadata / `nsm_config` permissions (0.4.5+) use `netbox_custom_objects.view_customobjecttype` and `netbox_custom_objects.change_customobjecttype` — there is no `TypeConfig` anchor model.

Bundle apply writes **`metadata`** (JSON) → COT **`comments`** via `schema/dispatch.sync_metadata`.

No `netbox_nsm_*` data tables exist in current NSM. Configuration lives in COT `comments`; rulebook instances live in `netbox-custom-objects`.

---

## Removed in 0.4.2 (migration `0005`)

| Removed table | Replaced by |
|---------------|-------------|
| `netbox_nsm_cotrulebookassignment` | COT `nsm_object_link` with `link_type=rulebook` |
| `netbox_nsm_typeconfig` (data rows) | `nsm_config` in COT `comments` |
| `netbox_nsm_section` | `rule_view.areas` in COT `comments` |
| `netbox_nsm_nsmuisettings` | `PLUGINS_CONFIG` |

---

## Earlier removed legacy tables

These tables existed in early NSM versions and were dropped during the COT migration:

| Removed table | Replaced by |
|---------------|-------------|
| `netbox_nsm_rulebook`, `netbox_nsm_rule`, `netbox_nsm_rulebookfield`, … | COT rulebooks (`nsm_rb_*`) and rule rows in `netbox-custom-objects` |
| `netbox_nsm_objectlink` | COT `nsm_object_link` |
| `netbox_nsm_objectgroup`, `netbox_nsm_objectgroupmember` | COT `group` M2M on Custom Objects |
| `netbox_nsm_propertytype`, `netbox_nsm_propertyfield`, `netbox_nsm_property` | Custom Object Types / fields |

See migrations `0004_delete_objectlink` and `0005_remove_legacy_object_and_property_models`.

---

## What is stored elsewhere

| Data | Where |
|------|--------|
| Zone / Address / Label / Service / Action **instances** | `netbox-custom-objects` tables (per COT slug) |
| Rulebook **rules** (grid rows) | COT tables for each `nsm_rb_*` rulebook |
| Security Panel **links** (policy + rulebook) | COT `nsm_object_link` (`link_type`: `policy` \| `rulebook`) |
| Type **metadata** (sort order, panel, areas, object builder) | COT type `comments` (`nsm_config`) |
| Address sync analysis | `python manage.py nsm_analyze_address_sync` |
| IP prefixes, IP addresses, devices, VMs | NetBox core (`ipam_*`, `dcim_*`, `virtualization_*`, …) |
| Tags, custom fields, changelog | NetBox `extras_*` |

`TypeConfig` was removed in 0.4.5. Configuration is edited via Type Metadata UI or
`/api/plugins/netbox-nsm/nsm-configs/<slug>/` (updates COT `comments`). Requires
`netbox_custom_objects.view_customobjecttype` (read) or `change_customobjecttype` (write).

---

## Address sync (CLI)

Object Sync UI was removed in 0.4.2. Run:

```bash
python manage.py nsm_analyze_address_sync
python manage.py nsm_analyze_address_sync --format json
```

Exit code is non-zero when issues are found (report only — no automatic fixes).

## Migrations

Schema changes ship with the plugin under `netbox_nsm/migrations/`. After upgrading NSM,
run NetBox migrations as usual:

```bash
python manage.py migrate netbox_nsm
```

| Migration | Purpose |
|-----------|---------|
| `0001_initial` | **Squashed** baseline: unmanaged permission anchors `TypeConfig` + `RulebookListProxy` only (`managed=False`, no data tables). Replaces legacy migrations `0002`–`0007` from 0.4.1/0.4.2; DBs that already applied those are marked applied without re-running data steps. |
| `0002_private_permission_anchors` | Mark permission anchors `_netbox_private` (excluded from `/core/system/` object counts) and drop legacy empty stub tables if present. |
| `0003_remove_typeconfig_permissions` | Map legacy `*_typeconfig` group permissions to `netbox_custom_objects` COT permissions; delete `TypeConfig` model. |
| `0004_nsm_metadata` | **No-op placeholder** — type/rulebook metadata lives in COT `comments` (`nsm_config`), not in Django tables. Keeps migration numbering stable for 0.4.10+ upgrades. |

**Current chain (0.4.10):** `0001` → `0002` → `0003` → `0004` — no native NSM data tables; panel links and rulebook assignments use COT `nsm_object_link`. Schema-only changes (e.g. removing `propagation` from `nsm_object_link`) are applied via **Bundles → nsm_schema**, not Django migrations.

**Squashing:** `0001_initial` is regenerated for new installs via
`docker/netbox_dev/scripts/generate_nsm_0001.sh` (removes numbered migrations in the dev
container, `makemigrations`, then add `replaces` for prior release migrations when shipping).

To regenerate `0001_initial` after model changes (dev, writable plugin mount):

```bash
# In netbox-dev — remove numbered migrations, then:
docker exec -u root netbox-dev bash -c 'cd /opt/netbox/netbox && /opt/netbox/venv/bin/python -c "
import os, django
os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\", \"netbox.settings\")
django.setup()
from django.conf import settings
settings.DEVELOPER = True
from django.core.management import call_command
call_command(\"makemigrations\", \"netbox_nsm\", name=\"initial\", verbosity=2)
"'
```

Or use `docker/netbox_dev/scripts/generate_nsm_0001.sh`.

---

## See also

- [RULE_DATA_STORAGE.md](RULE_DATA_STORAGE.md) — layer model, COT rule storage, rules grid
- [ARCHITECTURE.md](../ARCHITECTURE.md) — field-level model diagrams and relationships
- [using_netbox_nsm.md](using_netbox_nsm.md) — operator guide (rulebooks, fields, policy UI)
