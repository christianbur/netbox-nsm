# NSM Database Tables

[← Documentation home](README.md) · [How rule data is stored](RULE_DATA_STORAGE.md) · [Using netbox-nsm](using_netbox_nsm.md) · [Architecture](../ARCHITECTURE.md)

NSM persists its own data in the **NetBox PostgreSQL database**. Django uses the app label
`netbox_nsm`; table names follow the pattern `netbox_nsm_<model_name>` (lowercase).

Security **object instances** (zones, addresses, labels, services, actions, rulebook rules,
object links) are **not** stored in these native NSM tables. They live in
`netbox-custom-objects` (and standard NetBox apps such as IPAM/DCIM when referenced by rules).
NSM native tables hold configuration, hierarchy metadata, and generic assignments via
`content_type_id` + `object_id`.

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

## Native NSM models (current)

| Table | Model | Purpose |
|-------|--------|---------|
| `netbox_nsm_cotrulebook` | `CotRulebook` | Parent/child hierarchy, matrix tab flag, and **Grouped rows** column id (`row_group_by_col_id`) for deployed COT rulebooks (`nsm_rb_*` slugs) |
| `netbox_nsm_cotrulebookassignment` | `CotRulebookAssignment` | Assign a COT rulebook to Device / VM / VDC (generic FK) |
| `netbox_nsm_typeconfig` | `TypeConfig` | Global type behaviour: content type, matching class, display template, panel/inheritance flags |
| `netbox_nsm_section` | `Section` | Security panel section definitions |
| `netbox_nsm_nsmuisettings` | `NsmUiSettings` | Singleton UI labels and Setup menu flags |

`Section` may reference custom object types via M2M table
`netbox_nsm_section_custom_object_types`.

---

## Removed legacy tables

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
| Security Panel **links** | COT `nsm_object_link` |
| IP prefixes, IP addresses, devices, VMs | NetBox core (`ipam_*`, `dcim_*`, `virtualization_*`, …) |
| Tags, custom fields, changelog | NetBox `extras_*` |

`TypeConfig.content_type` points at the Django `django_content_type` row for the model
that holds the actual objects (custom object table or core model).

---

## Migrations

Schema changes ship with the plugin under `netbox_nsm/migrations/`. After upgrading NSM,
run NetBox migrations as usual:

```bash
python manage.py migrate netbox_nsm
```

| Migration | Purpose |
|-----------|---------|
| `0001_initial` | Squashed baseline for **fresh empty databases** (includes transitional legacy models later removed). Depends on `netbox_custom_objects` through `0014_fix_mixed_case_field_names`. |
| `0002_add_rulebook_permission` | Custom permissions on `CotRulebookAssignment` |
| `0003_cot_rulebook_hierarchy` | Adds `CotRulebook` parent/child slugs |
| `0004_delete_objectlink` | Drops native `ObjectLink` (migrate to COT first) |
| `0005_remove_legacy_object_and_property_models` | Drops `ObjectGroup*`, `Property*` |
| `0006_cotrulebook_matrix_tab_enabled` | Adds `matrix_tab_enabled` on `CotRulebook` |
| `0007_remove_typeconfig_panel_slugs_order_id` | Removes deprecated `TypeConfig.panel_slugs` / `order_id` |
| `0002_cotrulebook_row_group_by_col_id` | Adds `row_group_by_col_id` on `CotRulebook` (Rules tab **Grouped rows** setting) |

**Squashing:** `0001_initial` is already regenerated as a squashed baseline for new installs
(`docker/netbox_dev/scripts/generate_nsm_0001.sh`). Incremental migrations `0002`–`0007` must
remain for existing databases that applied them; do not squash further without a coordinated
release and migration replacement plan.

If migration planning fails with missing `netbox_custom_objects` parents, upgrade that plugin to a version that includes migration `0014` (NetBox dev stack: 0.5.x).

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
