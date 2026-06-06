# NSM Database Tables

[← Documentation home](README.md) · [Using netbox-nsm](using_netbox_nsm.md) · [Architecture](../ARCHITECTURE.md)

NSM persists its own data in the **NetBox PostgreSQL database**. Django uses the app label
`netbox_nsm`; table names follow the pattern `netbox_nsm_<model_name>` (lowercase).

Security **object instances** (zones, addresses, labels, services, actions, etc.) are **not**
stored in these tables. They live in `netbox-custom-objects` (and standard NetBox apps such
as IPAM/DCIM when referenced by rules). NSM tables hold configuration, links, rulebooks, and
references via `content_type_id` + `object_id`.

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

## Rulebooks and rules (core)

| Table | Model | Purpose |
|-------|--------|---------|
| `netbox_nsm_rulebook` | `Rulebook` | Named rulebook (policy container): name, platform, comment template, type |
| `netbox_nsm_rulebookfield` | `RulebookField` | **Field** (policy column): slug, name, placement, visibility, facet settings |
| `netbox_nsm_rulebookfieldtype` | `RulebookFieldType` | **Type within a field**: links a field to a `TypeConfig`, sort order, max items, name filter |
| `netbox_nsm_typeconfig` | `TypeConfig` | Global type behaviour: content type, matching class, display template, panel/inheritance flags |
| `netbox_nsm_rule` | `Rule` | One security rule: index, name, enabled, policy action, virtual groups JSON |
| `netbox_nsm_ruleobjectitem` | `RuleObjectItem` | Object assigned to a rule field (generic FK to any NetBox/custom object) |
| `netbox_nsm_rulegroupitem` | `RuleGroupItem` | `ObjectGroup` assigned to a rule field |
| `netbox_nsm_rulebookassignment` | `RulebookAssignment` | Rulebook bound to a device/VM (generic FK) |

### UI hierarchy vs tables

| UI concept | Primary table(s) |
|------------|------------------|
| **Field** (e.g. Source, Destination, Index) | `netbox_nsm_rulebookfield` |
| **Type in field** (e.g. Zones, Addresses under Destination) | `netbox_nsm_rulebookfieldtype` → `netbox_nsm_typeconfig` |
| **Rule row** in the policy table | `netbox_nsm_rule` |
| **Cell content** (objects/groups in a rule) | `netbox_nsm_ruleobjectitem`, `netbox_nsm_rulegroupitem` |

### Related rule tables

| Table | Purpose |
|-------|---------|
| `netbox_nsm_rule_source_users` | M2M: rule → source users |
| `netbox_nsm_rule_destination_users` | M2M: rule → destination users |

NetBox `PrimaryModel` / `NetBoxModel` rows also use standard extras: tags (`extras_taggeditem`),
custom fields (`custom_field_data` JSON on the model table), contacts where applicable.

---

## Object groups

| Table | Model | Purpose |
|-------|--------|---------|
| `netbox_nsm_objectgroup` | `ObjectGroup` | Named group of objects and/or nested groups |
| `netbox_nsm_objectgroupmember` | `ObjectGroupMember` | Group membership (generic FK or sub-group) |

---

## Security panel and object links

| Table | Model | Purpose |
|-------|--------|---------|
| `netbox_nsm_section` | `Section` | Security panel section definitions |
| `netbox_nsm_objectlink` | `ObjectLink` | Bidirectional link between two NetBox objects (panel) |

`Section` may reference custom object types via an M2M table
`netbox_nsm_section_custom_object_types`.

---

## Properties (NSM property catalog)

| Table | Model | Purpose |
|-------|--------|---------|
| `netbox_nsm_propertytype` | `PropertyType` | Property type definition |
| `netbox_nsm_propertyfield` | `PropertyField` | Fields on a property type |
| `netbox_nsm_property` | `Property` | Concrete property values |

---

## What is stored elsewhere

| Data | Where |
|------|--------|
| Zone / Address / Label / Service / Action **instances** | `netbox-custom-objects` tables (per COT slug) |
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
| `0001_initial` | Full NSM schema (squashed). Fresh installs: `migrate netbox_nsm` only. Depends on `netbox_custom_objects` through `0014_fix_mixed_case_field_names`. |

### Existing database after a squash (dev)

If NSM already had migrations `0002`–`0011` applied, reset the app schema before applying the squashed `0001`:

```bash
docker exec netbox-dev bash -c 'cd /opt/netbox/netbox && /opt/netbox/venv/bin/python manage.py migrate netbox_nsm zero'
docker exec netbox-dev bash -c 'cd /opt/netbox/netbox && /opt/netbox/venv/bin/python manage.py migrate netbox_nsm'
```

**Warning:** `migrate … zero` drops all NSM plugin tables (rulebooks, rules, type configs, …). Custom object instances and NetBox core data are unaffected.

If migration planning fails with missing `netbox_custom_objects` parents, upgrade that plugin to a version that includes migration `0014` (NetBox dev stack: 0.5.x).

To regenerate after model changes (dev, writable plugin mount):

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

- [ARCHITECTURE.md](../ARCHITECTURE.md) — field-level model diagrams and relationships
- [using_netbox_nsm.md](using_netbox_nsm.md) — operator guide (rulebooks, fields, policy UI)
