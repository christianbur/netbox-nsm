# TODO

Offene Verbesserungen und bekannte UI-Probleme (noch nicht umgesetzt).

---

## IP Analyzer — doppelte Linien zwischen Zeilen

**Status:** offen  
**Priorität:** niedrig (kosmetisch)  
**Betroffen:** Cell-Tree-Tabelle (`nsm-ipa-cell-tree-table`) im IP Analyzer

### Symptom

Zwischen Tabellenzeilen erscheinen manchmal **zwei Trennlinien** statt einer — nicht überall, sondern situativ.

### Ursachen (CSS/Layout, kein Datenfehler)

1. **Überlappende Border-Quellen**
   - Bootstrap/Tabler `.table` setzt `border-bottom` auf jede `td`.
   - IPA-CSS setzt zusätzlich `border-top` auf `tr + tr > td` (`nsm_ip_analyzer_applet.css`, ca. Zeile 1325–1334).
   - Mit `border-collapse: collapse` sollten die Linien zusammenfallen; bei unterschiedlichen Stilen/Farben wirkt es trotzdem oft doppelt.

2. **Eingeklappte Address Groups**
   - Summary-Zeile `nsm-ipa-root-groups-collapsed-header` hat bewusst `border-top` **und** `border-bottom` (gestrichelt).
   - Member-Zeilen darunter bekommen die normale durchgezogene `tr + tr`-Linie → gestrichelt + solid = Doppellinie.

3. **Ausgeblendete Zeilen (`display: none`)**
   - Zugeklappte Group-Member (`.nsm-ipa-root-groups-collapsed-member`) und Diff-Filter-Zeilen (`.nsm-ipa-diff-filtered-row`) bleiben im DOM.
   - `tr + tr`-Regel gilt weiter; Border-Collapse zwischen sichtbaren Zeilen bricht → Lücke oder Doppellinie.

4. **Lazy-Batch / Drilldown**
   - Lazy-Batch: verschachtelte `nsm-ipa-cell-tree-table--nested` in einer äußeren `<tr>` → äußere + innere Zeilentrenner.
   - Drilldown: zusätzliche volle `<tr>` nach Prefix-Kindern.

### Relevante Dateien

- `netbox_nsm/plugin_assets/css/nsm_ip_analyzer_applet.css` — Border-Regeln
- `netbox_nsm/templates/netbox_nsm/inc/ipa_object_tree_node.html` — collapsed groups, lazy batch, drilldown
- `netbox_nsm/templates/netbox_nsm/inc/ipa_cell_tree_row.html` — normale Datenzeilen

### Möglicher Fix (später)

- Auf Cell-Tree-`td` einheitlich `border-bottom: none` setzen; nur **eine** Trennlinie pro Übergang via `tr + tr > td { border-top: … }`.
- Für Summary-Zeilen gezielte Ausnahme: entweder nur `border-top` **oder** nur `border-bottom`, nicht beides + Nachbarzeile.
- Bei `display: none`-Zeilen: Border-Regel anpassen (z. B. `:not(.nsm-ipa-root-groups-collapsed-member):not(.nsm-ipa-diff-filtered-row)` oder Zeilen beim Ausblenden aus Border-Kette nehmen).
- Lazy-Batch: innere Tabelle ohne oberen Rand an der Batch-Grenze, oder äußere Zeile ohne doppelte Trennung.
- Asset-Cache-Version in `nsm_ip_analyzer_applet_assets.html` bumpen nach CSS-Änderung.

### Testplan (nach Fix)

- Normale flache Liste: einzelne Linie zwischen allen Zeilen.
- Collapsed groups (zu / aufgeklappt): keine Doppellinie an Summary-Grenzen.
- Diff-Filter aktiv (Focus / Changes / Warnings): keine Doppellinie an Stellen mit ausgeblendeten Zeilen.
- Lazy-Batch und IPAM-Drilldown visuell prüfen.
