# Benennung in netbox-nsm

Das Django-App-Label **`netbox_nsm`** (URL-Prefix `/plugins/netbox-nsm/`, Paket `netbox_nsm/`) ist der einzige „NSM“-Namespace.

Modelle, Python-Module, Templates und API-Ressourcen **ohne** `NSM`-Präfix — analog zu `TypeConfig`, `RulebookField`.

## Modelle

| Alt | Neu |
|-----|-----|
| `Section` | `Section` |
| `ObjectLink` | `ObjectLink` |
| `ObjectGroup` | `ObjectGroup` |
| `ObjectGroupMember` | `ObjectGroupMember` |
| `Rulebook` | `Rulebook` |
| `Rule` | `Rule` |
| `RuleObjectItem` | `RuleObjectItem` |
| `RuleGroupItem` | `RuleGroupItem` |
| `RulebookAssignment` | `RulebookAssignment` |
| `PropertyType` | `PropertyType` |
| `PropertyField` | `PropertyField` |
| `Property` | `Property` |

`TypeConfig`, `RulebookField`, `RulebookFieldType` bleiben unverändert.

## Python-Module (Beispiele)

| Alt | Neu |
|-----|-----|
| `models/nsm_policy.py` | `models/rulebook.py` |
| `views/nsm_policy.py` | `views/rulebook.py` |
| `tables/nsm_policy.py` | `tables/rulebook.py` |
| `forms/nsm_policy.py` | `forms/rulebook.py` |
| `filtersets/nsm_policy.py` | `filtersets/rulebook.py` |
| `api/serializers_/nsm_policy.py` | `api/serializers_/rulebook.py` |

Entsprechend für `object_group`, `object_link`, `section`, `property`, `type_config`.

## Templates

`rulebook.html` → `rulebook.html`, `rule.html` → `rule.html`, `objectgroup.html` → `objectgroup.html`, usw.

## URLs / Permissions

Django leitet Namen vom Modell ab: `plugins:netbox_nsm:rulebook_list`, Permission `netbox_nsm.view_rulebook`.

## Anwenden

Frische DB vorausgesetzt (`0001_initial` wird mit angepasst):

```bash
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm
python3 scripts/drop_nsm_prefix.py
```

Danach vom Homelab-Root (nicht aus `netbox-nsm/`):

```bash
cd /home/christian/homelab
./tools/docker-cmd.py netbox_dev down
./tools/docker-cmd.py netbox_dev up -d
```

Migrationen (Reihenfolge: zuerst Custom Objects, dann NSM):

```bash
Siehe **docs/DOCKER.md** (netbox-dev, Migrationen).

Setup-Plugin-Optionen in `configuration.py` (siehe `README.md` / `docs/using_netbox_nsm.md`):

- `setup_menu` — Setup im Menü und URLs (Default: `True`)
- `setup_allow_destructive_actions` — Sync/Demo auf Setup (Default: `True`, Prod: `False`)

**netbox-dev:** siehe `docs/DOCKER.md` und `docker/netbox_dev/DOCKER.md`
`setup_allow_destructive_actions: True` in `/config/configuration.py`.

Nach dem Skript-Lauf ggf. manuell prüfen: `filtersets/__init__.py` importiert `extras` (nicht `nsm_extra`); URL-Namen `object_link_*` (nicht `nsm_object_link_*`). Übersetzungen: `makemessages` / `compilemessages`.
