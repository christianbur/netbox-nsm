# IP Analyzer (IPA) — Architektur

Alle **Geschäftslogik** des IP Analyzers liegt in Python. JavaScript ist ausschließlich für
Anzeige und UI-Interaktion zuständig.

## Python (Single Source of Truth)

| Modul | Verantwortung |
|-------|---------------|
| `analysis/addr_tree.py` | Adress-Baumknoten, IPAM-Auflösung |
| `analysis/addr_merge.py` | Multi-Objekt-Merge, Typ-Zählungen |
| `analysis/addr_diff*.py` | Diff zwischen Seiten, Fundament, Hierarchie |
| `analysis/ipa_object_tree.py` | Objektbaum für Zellen/Applet |
| `analysis/ipa_ipam_tree.py` | IPAM-Drilldown-Knoten |
| `analysis/ipa_tree_dedupe.py` | Dedupe/Warnungen im Objektbaum |
| `analysis/addr_netmask.py` | IPv4 CIDR → Netmask (serverseitig) |
| `analysis/ipa_yaml_export.py` | YAML-Export |
| `analysis/ip_analyzer_service.py` | Gemeinsame Payload-Erzeugung (HTML + JSON) |

## API-Endpunkte

### UI (Session-Auth, HTML + JSON)

| Endpunkt | Funktion |
|----------|----------|
| `GET /plugins/netbox-nsm/api/ip-analyzer/` | Merge, Diff, YAML (`format=yaml`) |
| `GET /plugins/netbox-nsm/api/ip-analyzer/category/` | Lazy-Load Prefix/Range-Kategorien |
| `GET /plugins/netbox-nsm/api/ip-analyzer/object/` | Lazy-Load Objekt-Drilldown |
| `GET /plugins/netbox-nsm/api/ip-analyzer/add-object-types/` | Add-Object-Menü |

### REST (Token-Auth, nur JSON)

| Endpunkt | Funktion |
|----------|----------|
| `GET\|POST /api/plugins/netbox-nsm/ip-analyzer/` | Merge/Diff für Skripte und Integrationen |

## JavaScript (nur Anzeige)

| Datei | Rolle |
|-------|-------|
| `plugin_assets/js/nsm_ip_analyzer_applet.js` | Floating Applet: Tabs, Drag/Resize, API-Fetch, HTML-Injection |
| `plugin_assets/js/nsm_ipa_util.js` | i18n, Query-Strings, Footer-Formatierung, Blob-Download |
| `plugin_assets/js/nsm_ipa_cell.js` | Loupe-Klick: `ct`/`pk` aus DOM sammeln |
| `templates/.../ip_analyzer_assets.html` | CIDR/Netmask-Toggle, Lazy-Load-Handler |

**Erlaubt in JS:** DOM lesen, API aufrufen, HTML einfügen, Expand/Collapse, Tab-Verwaltung,
i18n-Formatierung von serverseitigen Zählungen (`diff_summary`, `count_*`).

**Nicht in JS:** Merge/Diff-Berechnung, Baumaufbau, Dedupe, IP-Adress-Auflösung,
Netmask-Berechnung, YAML-Generierung.

### Zell-Pills (ADDRESS vs. ADDRESS_GROUP)

Ob eine Zellzeile als **ADDRESS** oder **ADDRESS_GROUP** dargestellt wird, entscheidet
ausschließlich Python: `_mark_ipa_cell_pill_roles` (`analysis/ipa_object_tree.py`) setzt
`cell_pill_group=True` für Knoten mit `node_role == nsm_group` (z. B. eingeklappte
Adressgruppen-Zeilen großer `bench-grp-*`-Gruppen). Das Template
`inc/ipa_cell_object_row_labels.html` rendert das Pill nur anhand dieses Flags —
strukturelle IPAM-Filler/Synthetic-Zeilen sind nie NSM-Objekte und bleiben grau.

Bei verschachtelten Gruppen (Gruppe direkt selektiert und zugleich Mitglied einer
übergeordneten Gruppe) entfernt `_scrub_ipa_cell_group_self_refs` die eigene Identität
aus `cell_groups`. Die Zeile zeigt dann genau ein Self-Pill (Primärspalte) plus
Vorfahren-Gruppen in der Mitgliedschaftsspalte — keine doppelte ADDRESS_GROUP-Anzeige.

### Prefix-Containment (Performance)

`_IpaContainingPrefixCache` sammelt Host-Adressen aus dem Zellbaum (`register_tree`)
und lädt passende NetBox-Prefixes beim ersten Lookup in **einer** ORM-Abfrage
(`prefix__net_contains` per OR-Kette). Cache-Misses fallen auf die uncached
Implementierung zurück (SimpleTestCase-kompatibel). Die Schritte
`_insert_ipam_filler_prefixes`, `_synthesize_ipa_cell_ipam_parent_prefixes` und
`_insert_ipa_host_gap_info_rows` nutzen den Cache statt N Einzel-Lookups pro Host.

## Applet display features (current)

> English summary of the current applet UI (the rest of this file is German).

- **Flat cell object table — 8 columns:** **Network**, **IP/Range/Prefix**, **Dup**,
  **Address**, **Address group**, **Merge**, **Diff**, **Used by**. The standalone
  *Parent* column was removed; parent/containment hints live in **Dup** and tooltips.
  *Used by* (DE: *Verwendet von*) is the renamed former *Us* column.
- **Merge appends a new tab:** running **Merge** creates an additional merged tab
  (`mergeTabs`, `this.tabs.push(mergedTab)`) and keeps the existing tabs instead of
  replacing them.
- **Diff:** the IPAM tree rolls IPAM children up under their containing prefixes; each
  side of the **Diff** column is labelled with its source **tab name** (e.g. `Rule 1/5`),
  and the former *fund* marker is shown as a clear **Name conflict** badge
  (DE: *Namenskonflikt*).
- **YAML export v2:** the applet export emits `ipa_export_version: "2"` with a primary
  `displayed` section (visible tree, counts, `copy_lines`, `addr_analysis`,
  `object_tree`) plus an optional `ipam_children` section.
- **Rules-TOML export:** the rulebook rules table (not the applet) exports the visible
  rows as a structured TOML document (`format = "netbox-nsm-rules-visible-v1"`,
  `application/toml`, `*.toml`) via `exportRulesToml`; the previous CSV export is gone.
- **Standalone IP Analyzer page removed:** `/plugins/netbox-nsm/ip-analyzer/` permanently
  redirects to **Object Analyzer**; address resolution lives only in this applet and the
  analysis APIs.

## Datenfluss

```
Rules-Zelle / Loupe
    → JS sammelt ct/pk (+ optional Regel-Kontext)
    → GET api/ip-analyzer/?ct=…&pk=…
    → Python: merge/diff → HTML + counts
    → JS injiziert HTML in Applet-Body

Lazy-Load (Prefix-Kategorie)
    → GET api/ip-analyzer/category/?prefix_pk=…&category=…&offset=…
    → Python rendert Baum-Fragment
    → JS fügt HTML ein, re-init Prefix-Toggle

Export
    → GET api/ip-analyzer/?format=yaml&…
    → Python serialisiert YAML
    → JS löst Blob-Download aus
```
