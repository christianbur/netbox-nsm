# NSM — Modulare Architektur

> **Status:** Umgesetzt (Phasen A–E, mit Legacy-Shims)  
> **Stand:** 2026-06-30  
> **Kontext:** Bundle-austauschbares, firewall-neutrales Plugin; eigene COTs; vier Module; Schema-Inferenz über `related_object_types`.

## Offene Arbeitspakete

- [x] **mod-bundles** — `bundles/`: Vertrag, Override, Platform ohne `REQUIRED_COT_SLUGS` / `nsm_schema`-Gate (Phase A: `bundles/discovery.py`, Setup-Health über discovered Bundles)
- [x] **mod-cot-flex** — `cot_roles`: Inferenz aus `related_object_types` (IPAM/Group); dynamische GFK-Spalten; Metadata nur Override (Phase B: `objects/cot_roles.py`, `address_*`/`type_kind` umgestellt)
- [x] **mod-views** — `rulebooks/views/{table,matrix}/` + Registry aus `metadata.rulebook.views` (Phase C: `rulebooks/views/registry.py`, Tabs registry-getrieben)
- [x] **mod-proxy** — `rulebooks/proxy/`: add/del/clone/edit Regeln auf COT (Phase C: `rulebooks/proxy/rule_rows.py`)
- [x] **mod-analyzers** (Phase C: analyzers/{ip,object_analyzer,object_report} + shims) — `analyzers/{registry,object_analyzer,ip,object_report}/`; Migration; capability registry (Phase D: Registry verdrahtet; `modes` rollenbasiert) + Phase E `analyzers/label/`
- [x] **mod-docs** — `ARCHITECTURE.md`: 4 Module + Analyzer-Familie + Custom-COT-Matrix

---

## Vision

- **Bundles** (austauschbar) definieren COTs, Choice Sets, Seeds, Metadaten.
- Anwender können **eigene COT-Slugs, Anzeigenamen, Felder und Feldreihenfolge** definieren — NSM Platform reagiert über **Metadata + strukturelle Discovery**, nicht über feste `nsm_*`-Namen.
- Vier **Module** für Import, Darstellung, Bearbeitung, Semantik.
- **Kein** Django-ORM für Policy-Daten.

---

## Eigene COTs — Stand nach Phasen A–E

| Anforderung | Status | Hinweis |
|-------------|--------|---------|
| **Anderer Slug/Name** | ✅ | Bundle Apply; Setup-Health über `bundles/discovery.py` |
| **Andere Feldreihenfolge** | ✅ | `weight` im Schema; NSM irrelevant |
| **IPAM-Feld, anderer Name** | ✅ | `objects/cot_roles.resolve_ipam_field()`; dynamische GFK-Spalten |
| **Mehrere Address-COTs parallel** | ⚠️ Teilweise | `iter_cots_by_role("address")` / rollenbasierte CT-IDs; `get_ipam_address_cot()` noch first-match |
| **In Rulebook referenzieren** | ✅ | über `related_object_types` |
| **Security-Tab IPAM** | ⚠️ Teilweise | CT-IDs rollenbasiert; nicht alle Codepfade iterieren mehrere Address-COTs |
| **Zone/Label-Inferenz** | ⚠️ Teilweise | Metadata-`role` + `type_metadata.roles`; strukturelle Zone-Inferenz aus Rulebook-Referenzen noch offen |

**Legacy-Fallbacks (bewusst):** `REQUIRED_COT_SLUGS` (Ordering/Setup-Fallback), `ADDRESS_CONTENT_MODELS`, `SECURITY_NSM_COT_SLUGS`.

---

## Woher wissen Analyzer, was eine Address / Gruppe / Zone ist?

**Kurz:** Primär aus dem **deployed COT-Schema** — konkret aus `CustomObjectTypeField.related_object_types` (nach Bundle-Apply identisch mit dem JSON). Der Feldname (`address` vs. `ipam_ref`) ist egal. Optionales Bundle-Metadata (`role`, `ipam.field`) nur als Override, nicht als Voraussetzung.

### Ja — `related_object_types` ist der richtige Signalgeber

Beispiel aus `bundles/builtin/nsm_schema.json`:

```json
"name": "address",
"type": "object",
"is_polymorphic": true,
"related_object_types": ["ipam/ipaddress", "ipam/iprange", "ipam/prefix"]
```

**Inferenz-Regel:** Ein `object`-Feld, dessen `related_object_types` **ausschließlich** IPAM-Modelle sind → dieses COT ist eine **IPAM-Address**; das Feld ist das IPAM-Binding — **unabhängig vom Namen**.

Gleiches Muster für Gruppen:

```json
"name": "group",
"type": "multiobject",
"related_object_types": ["custom-objects/nsm_address", "custom-objects/nsm_address_custom"]
```

→ **Address Group** (Members zeigen auf Address-COTs), nicht nur weil das Feld `group` heißt.

Rulebooks nutzen `related_object_types` schon so (`rules_layout.py`, Security-Panel, Matrix). Address/IPAM-Helfer und Analyzer nutzen seit Phase B **`objects/cot_roles.py`** (kein hardcodiertes Feld `address`/`group` mehr).

### Heute: Signal da, aber Code blockiert am Feldnamen

In `address_cot_schema.py` existiert `_field_targets_ipam()` — liest `related_object_types` korrekt. **Aber:**

```python
# nur Feld name="address"
for field in CustomObjectTypeField.objects.filter(
    custom_object_type=cot, name="address", ...
):
    if _field_targets_ipam(field): ...

# GFK-Spalten vom Feldnamen abhängig
_POLYMORPHIC_CT_ATTR = "address_content_type_id"   # nur wenn Feld "address" heißt
```

Address Group: nur `name="group"` geprüft, **nicht** wohin `related_object_types` zeigt.

### Ziel: Schema-Inferenz zuerst, Metadata optional

**Inferenz-Tabelle** (aus deployed `CustomObjectTypeField`, nicht aus Slug):

| Erkannt wenn | Rolle | IPAM-/Member-Feld |
|--------------|-------|-------------------|
| `object`/`multiobject` + `related_object_types` ⊆ `{ipam/ipaddress, ipam/prefix, ipam/iprange}` | `address` (IPAM) | dieses Feld |
| `text`-Felder `ipv4`+`ipv6`+`prefix_len`/`subnet`, kein IPAM-Feld | `address` (manual) | `literal.fields` |
| `multiobject` + `related_object_types` ⊆ COTs mit Rolle `address` | `address_group` | dieses Feld |
| in Rulebook-Zone-Spalten referenziert (`related_object_types` auf Rulebook-Feld) | `zone` | — |
| Feld `label_type` (Taxonomy-Select) oder in Label-Spalten referenziert | `label` | — |

GFK-Spalten dynamisch: `{field.name}_content_type_id` / `{field.name}_object_id`.

**Zone/Label:** anders als Address — **kein** ausgehendes IPAM-Feld auf dem Zone/Label-COT. Zone über **eingehende** Rulebook-Referenz (`source_zones` → `custom-objects/corp_zone`); Label zusätzlich über Struktur-Fingerprint `label_type`.

### Was `related_object_types` allein nicht abdeckt

| Fall | Warum Schema nicht reicht |
|------|---------------------------|
| **ANY** (`0.0.0.0/0`) | Kein IPAM-Link; Literal in Instanz-`comments` |
| **Capabilities** (welcher Analyzer) | Verhalten, nicht Struktur |
| **object_builder** / status_map | In `nsm_config`, nicht im Feldschema |
| **Mehrdeutigkeit** (2 IPAM-Felder) | Metadata `ipam.field` nötig |

### Semantische Rollen (`role`)

| `role` | Bedeutung |
|--------|-----------|
| `address` | Policy-Adresse (IPAM-Link und/oder Literal-Felder) |
| `address_group` | Sammlung von Address-Objekten |
| `zone` | Security Zone |
| `label` | Klassifikations-Label |
| `service` / `service_group` | Dienst(e) |
| `action` | Policy-Aktion |
| `rule` / `rulebook` | Regel / Regelsammlung |
| `object_link` | Verknüpfung Panel ↔ Rulebook |

### Platform-API (neu: `objects/cot_roles.py`)

```python
resolve_role(cot) -> str | None
iter_cots_by_role("address") -> Iterator[COT]
resolve_ipam_field(cot) -> CustomObjectTypeField | None
resolve_members_field(cot) -> CustomObjectTypeField | None
membership_through(group_cot) -> (Through, group_fk, member_fk)
is_universal_address(obj) -> bool
resolve_literal_network(obj) -> str | None
```

**Regel:** Analyzer enthalten **keine** Slug-Listen und **kein** `ipaddress`-Parsing im Core — nur `cot_roles` + analyzer-spezifische Logik.

### ANY / „alle IPs“

ANY ist **kein** eigener COT-Typ; Erkennung **nicht** am Namen `ANY`:

```yaml
# Instanz-comments
nsm_config:
  - network: 0.0.0.0/0
```

Heute: `address_literal.py` — `get_network_literal()`, `is_literal_address()`, nur `0.0.0.0/0` in `ALLOWED_NETWORK_LITERALS`.

**Address Custom** (`ipv4`/`ipv6`/`subnet`-Felder) ist ein **eigener** Manual-Address-COT — nicht dasselbe wie ANY in comments.

---

## Vier Module

| Modul | Pfad | Aufgabe |
|-------|------|---------|
| **1 Import** | `bundles/` | COTs, Choice Sets, Seeds; `bundle_paths` Override |
| **2 Views** | `rulebooks/views/` | Table, Matrix — **nur Anzeige** |
| **3 Proxy** | `rulebooks/proxy/` | add / del / clone / edit **Regel-Zeilen** |
| **4 Analyzers** | `analyzers/` | Object Analyzer, IP-Analyse, Object Report, später Label |

---

## Modul 4 — Analyzers

| Analyzer | URL / Einstieg | Capability |
|----------|----------------|------------|
| **Object Analyzer** | `/object-analyzer/`, `/api/analyzer/` | `analyzer.object_analyzer` |
| **IP-Analyse** | Applet in Rulebooks, `/api/ip-analysis/` | `analyzer.ip` |
| **Object Report** | `/object-report/` | `analyzer.object_report` |

| Frage | Object Analyzer | IP-Analyse | Object Report |
|-------|-----------------|------------|---------------|
| Was? | „Womit ist X verknüpft?“ | „Welche Regeln treffen auf diese IP?“ | „Ist der Address-Layer konsistent?“ |
| UI | Volle Seite + Graph | Applet | Volle Seite + Job |

Gemeinsame **`analyzers/registry.py`** (`AnalyzerSpec`: key, capability, url_name, run_mode, build).

---

## Ziel-Paketstruktur

```
netbox_nsm/
├── bundles/
├── rulebooks/
│   ├── core/
│   ├── proxy/
│   └── views/
│       ├── registry.py
│       ├── table/
│       └── matrix/
├── analyzers/
│   ├── registry.py
│   ├── object_analyzer/
│   ├── ip/
│   ├── object_report/
│   └── label/
├── objects/
│   ├── cot_roles.py
│   ├── address_cot_schema.py   # Legacy-Shim → cot_roles
│   └── address_ipam_fk.py
├── security/
└── type_metadata/
```

**URLs bleiben stabil:** `/object-report/`, `/object-analyzer/`, `/api/ip-analysis/`

---

## Roadmap

### Phase A — Bundles + Platform entkoppeln ✅
- `core_bundle_applied("nsm_schema")`-Gate entfernt; `all_cots_ok` prüft nur noch discovered COTs
- `REQUIRED_COT_SLUGS` ist jetzt **Fallback/Ordering-Hint** — Setup-Health kommt aus `bundles/discovery.py` (`discovered_policy_cot_slugs`)
- `setup_context` + `bench/prerequisites` über `expected_cot_slugs()` / Discovery

### Phase B — Flexible COTs / Rollen-Vertrag ✅
- `objects/cot_roles.py`: `resolve_role`, `iter_cots_by_role`, `resolve_ipam_field`, `resolve_members_field`, `membership_through`, `ipam_gfk_attrs`, `is_universal_address`, `resolve_literal_network`
- `addresses/address_cot_schema.py` + `address_ipam_fk.py`: keine hardcodierten Feldnamen `address`/`group` mehr (cot_roles + dynamische GFK-Spalten, Fast-Path-Fallback)
- `core/type_kind.address_content_type_ids()` rollenbasiert (ADDRESS_CONTENT_MODELS nur Fallback), Cache + Invalidierung in `sync_metadata`
- `object_report._group_membership_through` → `cot_roles.membership_through`

### Phase C — Module strukturieren ✅
- `rulebooks/views/registry.py` (RulebookViewSpec, `resolve_rulebook_view_keys` aus `metadata.rulebook.views`)
- `rulebooks/views/{table,matrix}/` (kanonische Importpfade, URLs stabil via `views/cot`)
- `rulebooks/proxy/` (`rule_add/edit/delete_url`, `rulebook_clone_url`, `can_edit_rules`)
- Tabs (`virtual_cot_tabs`) registry-getrieben
- Analyzer-Migration bereits in Phase-C-Commit (analysis/analyzer/object_report → Shims)

### Phase D — Metadata überall ✅
- `analyzers/registry.py`: Helper (`get_analyzer`, `analyzer_reverse`, …); verdrahtet in Security-Tab + IP-Legacy-Redirect; `urls.py` auf kanonische `analyzers.*`-Pfade
- `analyzers/object_analyzer/modes.py`: `SECURITY_NSM_COT_SLUGS` → rollenbasiert (`SECURITY_ALLOWED_ROLES` + cot_roles), Slug-Liste nur Fallback

### Phase E — Erweiterungen ✅
- `analyzers/label/` Skeleton + `analyzer.label`-Capability in `ANALYZER_REGISTRY`
- `analyzers/object_report/check_registry.py`: `register_object_report_check` Hook; in `build_object_report` / `prepare_object_report_check_rows` integriert

---

## Scope

- Repository: `netbox-nsm` (Plugin)
- Inkrementelle Migration mit kurzen Shims
