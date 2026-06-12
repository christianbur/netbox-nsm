#!/usr/bin/env python3
"""Fill German translations for NSM setup area in de.po."""

from __future__ import annotations

import re
from pathlib import Path

PO_PATH = Path(__file__).resolve().parents[1] / "netbox_nsm/locale/de/LC_MESSAGES/django.po"

TRANSLATIONS: dict[str, str] = {
    "Setup": "Einrichtung",
    "Menu label": "Menübezeichnung",
    "Top-level plugin menu entry in the NetBox sidebar.": (
        "Eintrag des Plugins im NetBox-Seitenmenü."
    ),
    "Panel label": "Panel-Bezeichnung",
    "Security card title on object detail pages.": (
        "Titel der Security-Karte auf Objektdetailseiten."
    ),
    "Setup menu dismissed": "Setup-Menü ausgeblendet",
    "When True, the Setup menu entry stays hidden until restored via plugin "
    "configuration.": (
        "Wenn True, bleibt der Setup-Menüeintrag ausgeblendet, bis er über die "
        "Plugin-Konfiguration wiederhergestellt wird."
    ),
    "Last seen setup_menu config": "Zuletzt gesehene setup_menu-Konfiguration",
    "Tracks the last observed PLUGINS_CONFIG setup_menu value for restore after "
    "toggling false → true.": (
        "Speichert den zuletzt beobachteten PLUGINS_CONFIG setup_menu-Wert zur "
        "Wiederherstellung nach false → true."
    ),
    "NSM UI Settings": "NSM-UI-Einstellungen",
    "Custom Objects": "Custom Objects",
    "Plugin ready": "Plugin bereit",
    "Migrations pending": "Migrationen ausstehend",
    "Plugin not installed": "Plugin nicht installiert",
    "<strong>netbox-custom-objects</strong> — applies bundled portable schema "
    "(<code>schema/nsm_portable_schema.json</code>).": (
        "<strong>netbox-custom-objects</strong> — wendet das gebündelte portable "
        "Schema an (<code>schema/nsm_portable_schema.json</code>)."
    ),
    "Run migrations before importing types:": (
        "Migrationen ausführen, bevor Typen importiert werden:"
    ),
    "Install netbox-custom-objects first": (
        "Zuerst netbox-custom-objects installieren"
    ),
    "Run migrations first": "Zuerst Migrationen ausführen",
    "All types already present": "Alle Typen bereits vorhanden",
    "Add all Custom Object Types": "Alle Custom-Object-Typen hinzufügen",
    "Includes built-in NSM types and NSM Panel links.": (
        "Enthält integrierte NSM-Typen und NSM-Panel-Links."
    ),
    "Section 2 complete.": "Abschnitt 2 abgeschlossen.",
    "Hide Setup": "Setup ausblenden",
    "\n"
    "      Remove the <strong>Setup</strong> entry from the Configuration menu. "
    "The page\n"
    "      stays hidden until you set <code>\"setup_menu\": true</code> in\n"
    "      <code>PLUGINS_CONFIG[\"netbox_nsm\"]</code> again (toggle\n"
    "      <code>false</code> → restart → <code>true</code> → restart).\n"
    "      ": (
        "\n"
        "      Entfernt den Eintrag <strong>Setup</strong> aus dem "
        "Konfigurationsmenü. Die Seite\n"
        "      bleibt ausgeblendet, bis Sie <code>\"setup_menu\": true</code> in\n"
        "      <code>PLUGINS_CONFIG[\"netbox_nsm\"]</code> wieder setzen (Toggle\n"
        "      <code>false</code> → Neustart → <code>true</code> → Neustart).\n"
        "      "
    ),
    "Hide Setup menu": "Setup-Menü ausblenden",
    "TypeConfig": "TypeConfig",
    "Links each Custom Object Type to NSM behaviour (matching class, display, "
    "panel). Inheritance is configured per link under Assign, not here.": (
        "Verknüpft jeden Custom-Object-Typ mit NSM-Verhalten (Matching Class, "
        "Anzeige, Panel). Vererbung wird pro Link unter Assign konfiguriert, "
        "nicht hier."
    ),
    "Complete section 2 first": "Abschnitt 2 zuerst abschließen",
    "All TypeConfigs already configured": "Alle TypeConfigs bereits konfiguriert",
    "Add all TypeConfigs": "Alle TypeConfigs hinzufügen",
    "Available after section 2 is complete.": (
        "Verfügbar nach Abschluss von Abschnitt 2."
    ),
    "waiting": "wartend",
    "Section 3 complete.": "Abschnitt 3 abgeschlossen.",
    "Menu & panel title": "Menü- & Panel-Titel",
    "Titles for the sidebar menu and the object-detail card. Default for both: "
    "<strong>Security</strong>.": (
        "Titel für das Seitenmenü und die Objektdetail-Karte. Standard für "
        "beide: <strong>Security</strong>."
    ),
    "Custom Object Type '%(slug)s' imported (TypeConfigs: use step 3).": (
        "Custom-Object-Typ „%(slug)s“ importiert (TypeConfigs: Schritt 3)."
    ),
    "All Custom Object Types imported. Create TypeConfigs in step 3.": (
        "Alle Custom-Object-Typen importiert. TypeConfigs in Schritt 3 anlegen."
    ),
    "%(label)s import could not be queued: no RQ worker is running. Start the "
    "NetBox RQ worker (e.g. container netbox-dev-worker or `manage.py rqworker`) "
    "and try again.": (
        "%(label)s-Import konnte nicht in die Warteschlange gestellt werden: "
        "Kein RQ-Worker läuft. Starten Sie den NetBox-RQ-Worker (z. B. Container "
        "netbox-dev-worker oder `manage.py rqworker`) und versuchen Sie es erneut."
    ),
    "%(label)s import is already queued or running (job %(job_id)s). The rulebook "
    "«%(rulebook)s» is replaced when that job starts; allow about %(minutes)s "
    "minutes of processing after it begins.": (
        "%(label)s-Import ist bereits in der Warteschlange oder läuft (Job "
        "%(job_id)s). Das Regelbuch «%(rulebook)s» wird ersetzt, wenn der Job "
        "startet; rechnen Sie nach Beginn mit etwa %(minutes)s Minuten "
        "Verarbeitungszeit."
    ),
    "%(label)s import queued (job %(job_id)s); %(backlog)s other job(s) are ahead "
    "in the worker queue. The rulebook «%(rulebook)s» will be recreated when this "
    "job starts (~%(minutes)s minutes of work). Find it under Security → "
    "Rulebooks.": (
        "%(label)s-Import in Warteschlange (Job %(job_id)s); %(backlog)s "
        "weitere Job(s) sind voraus. Das Regelbuch «%(rulebook)s» wird neu "
        "angelegt, wenn dieser Job startet (~%(minutes)s Minuten Arbeit). "
        "Finden Sie es unter Security → Rulebooks."
    ),
    "%(label)s import started in the background (job %(job_id)s). The rulebook "
    "«%(rulebook)s» will be recreated in about %(minutes)s minutes (any existing "
    "rulebook with that name is removed when the job starts, not when you click "
    "Create). Find it under Security → Rulebooks.": (
        "%(label)s-Import im Hintergrund gestartet (Job %(job_id)s). Das "
        "Regelbuch «%(rulebook)s» wird in etwa %(minutes)s Minuten neu angelegt "
        "(ein vorhandenes Regelbuch mit diesem Namen wird beim Jobstart entfernt, "
        "nicht beim Klick auf Erstellen). Finden Sie es unter Security → Rulebooks."
    ),
    "Import finished.": "Import abgeschlossen.",
    "Enterprise Demo imported successfully. %(summary)s": (
        "Enterprise-Demo erfolgreich importiert. %(summary)s"
    ),
    "Starter demo created: %(zone_count)s zones, %(rule_count)s rules (random "
    "permit/deny) in custom-object type '%(rb_slug)s' (portable schema, zones "
    "only). Custom Object Types / TypeConfigs were imported if missing.": (
        "Starter-Demo angelegt: %(zone_count)s Zonen, %(rule_count)s Regeln "
        "(zufällig permit/deny) im Custom-Object-Typ „%(rb_slug)s“ (portables "
        "Schema, nur Zonen). Custom-Object-Typen / TypeConfigs wurden bei Bedarf "
        "importiert."
    ),
    "Enterprise Demo cannot be imported: IP addresses already exist in the "
    "database.": (
        "Enterprise-Demo kann nicht importiert werden: Es existieren bereits "
        "IP-Adressen in der Datenbank."
    ),
    "TypeConfig for '%(slug)s' created.": (
        "TypeConfig für „%(slug)s“ angelegt."
    ),
    "All TypeConfigs created/updated (including NSM section links).": (
        "Alle TypeConfigs angelegt/aktualisiert (einschließlich NSM-Section-Links)."
    ),
    "Setup has been hidden from the menu. To show it again, set \"setup_menu\": "
    "true in PLUGINS_CONFIG[\"netbox_nsm\"] after toggling it to false and "
    "restarting NetBox.": (
        "Setup wurde aus dem Menü ausgeblendet. Zum Wiederanzeigen setzen Sie "
        "„setup_menu“: true in PLUGINS_CONFIG[\"netbox_nsm\"], nachdem Sie es "
        "auf false gesetzt und NetBox neu gestartet haben."
    ),
    "Menu label is required.": "Menübezeichnung ist erforderlich.",
    "Menu and panel labels saved.": "Menü- und Panel-Bezeichnungen gespeichert.",
    "netbox-custom-objects database tables are missing. Run: python manage.py "
    "migrate netbox_custom_objects": (
        "Datenbanktabellen von netbox-custom-objects fehlen. Ausführen: "
        "python manage.py migrate netbox_custom_objects"
    ),
    "netbox-custom-objects is not ready. Install the plugin and run migrations "
    "first.": (
        "netbox-custom-objects ist nicht bereit. Plugin installieren und zuerst "
        "Migrationen ausführen."
    ),
    "All Custom Object Types are already present.": (
        "Alle Custom-Object-Typen sind bereits vorhanden."
    ),
    "Complete section 2 (Custom Objects) before adding TypeConfigs.": (
        "Abschnitt 2 (Custom Objects) zuerst abschließen, bevor TypeConfigs "
        "hinzugefügt werden."
    ),
    "All TypeConfigs are already configured.": (
        "Alle TypeConfigs sind bereits konfiguriert."
    ),
    "Please confirm that IP addresses may be created before starting the address "
    "bench.": (
        "Bitte bestätigen Sie, dass IP-Adressen angelegt werden dürfen, bevor der "
        "Address Bench gestartet wird."
    ),
    "Unknown action: %(action)s": "Unbekannte Aktion: %(action)s",
    "Error: %(error)s": "Fehler: %(error)s",
    # IPA / API / object analyzer (added for makemessages follow-up)
    "No IP addresses resolved.": "Keine IP-Adressen aufgelöst.",
    "No analyzable address objects.": "Keine analysierbaren Adressobjekte.",
    "No valid objects selected.": "Keine gültigen Objekte ausgewählt.",
    "No valid objects selected for diff.": (
        "Keine gültigen Objekte für den Diff ausgewählt."
    ),
    "IP Analysis": "IP-Analyse",
    "Subnets: %(count)s": "Subnetze: %(count)s",
    "Ranges: %(count)s": "Bereiche: %(count)s",
    "IPs: %(count)s": "IPs: %(count)s",
    "Warnings: %(count)s": "Warnungen: %(count)s",
    "Rule %(index)s/%(col)s": "Regel %(index)s/%(col)s",
    "Rule %(index)s / %(col)s": "Regel %(index)s / %(col)s",
    "Rule %(name)s (%(index)s) / %(col)s": "Regel %(name)s (%(index)s) / %(col)s",
    "Rule %(name)s (%(index)s)": "Regel %(name)s (%(index)s)",
    "%(count)s objects": "%(count)s Objekte",
    "Merged (%(count)s objects)": "Merged (%(count)s Objekte)",
    "Diff": "Diff",
    "Diff %(a)s - %(b)s": "Diff %(a)s - %(b)s",
    "Diff %(labels)s": "Diff %(labels)s",
    "Diff (%(a)s ↔ %(b)s)": "Diff (%(a)s ↔ %(b)s)",
    "Diff (%(labels)s)": "Diff (%(labels)s)",
    "Diff (%(count)s tabs)": "Diff (%(count)s Tabs)",
    " | Fund: %(count)s": " | Fund: %(count)s",
    "%(label)s: +%(count)s": "%(label)s: +%(count)s",
    "in all: %(count)s": "in allen: %(count)s",
    "in some: %(count)s": "in einigen: %(count)s",
    "%(label_a)s: +%(count_a)s | %(label_b)s: +%(count_b)s | shared: %(both)s": (
        "%(label_a)s: +%(count_a)s | %(label_b)s: +%(count_b)s | gemeinsam: %(both)s"
    ),
    "Analyze object": "Objekt analysieren",
    "Analysis running…": "Analyse läuft…",
    "Analysis failed.": "Analyse fehlgeschlagen.",
    "Minimize": "Minimieren",
    "Close": "Schließen",
    "Add object": "Objekt hinzufügen",
    "Merge": "Merge",
    "Search…": "Suchen…",
    "Add object — %(category)s": "Objekt hinzufügen — %(category)s",
    "Enter search term…": "Suchbegriff eingeben…",
    "No matches": "Keine Treffer",
    "Searching…": "Suche…",
    "Diff (at least 2 tabs required)": "Diff (mindestens 2 Tabs erforderlich)",
    "Close tab": "Tab schließen",
    "No object types available": "Keine Objekttypen verfügbar",
    "%(count)s skipped": "%(count)s übersprungen",
    "Analysis could not be loaded.": "Analyse konnte nicht geladen werden.",
    "IP Analysis (%(count)s)": "IP-Analyse (%(count)s)",
    "Object Analyzer": "Objektanalysator",
    "Select object · click to expand · double-click to open": (
        "Objekt auswählen · Klicken zum Aufklappen · Doppelklick zum Öffnen"
    ),
    "Search: Device, VM, IP, Prefix, Label, Zone, Rule …": (
        "Suchen: Gerät, VM, IP, Präfix, Label, Zone, Regel …"
    ),
    "Analyze": "Analysieren",
    "Click a node in the graph to load its connections.": (
        "Klicken Sie auf einen Knoten im Graphen, um dessen Verbindungen zu laden."
    ),
    "IP": "IP",
    "Zone / Rule": "Zone / Regel",
    "Select object": "Objekt auswählen",
    "Select an object above – the graph starts with this node.": (
        "Wählen Sie oben ein Objekt – der Graph startet mit diesem Knoten."
    ),
}

REMOVE_FUZZY_FOR = {
    "Plugin not installed",
    "All types already present",
    "Add all Custom Object Types",
    "Hide Setup",
    "TypeConfig",
    "All TypeConfigs already configured",
    "Add all TypeConfigs",
    "All Custom Object Types are already present.",
    "All TypeConfigs are already configured.",
    "Custom Objects",
}


def parse_po(content: str) -> list[dict]:
    entries: list[dict] = []
    i = 0
    lines = content.splitlines(keepends=True)
    while i < len(lines):
        line = lines[i]
        if not line.startswith("msgid "):
            i += 1
            continue
        block_start = i
        while i > 0 and lines[i - 1].startswith("#"):
            block_start = i - 1
            if i > 1 and not lines[i - 2].startswith("#"):
                break
            i -= 1
        i = block_start
        block_lines: list[str] = []
        while i < len(lines):
            block_lines.append(lines[i])
            if lines[i].startswith("msgstr "):
                break
            i += 1
        while i + 1 < len(lines) and lines[i + 1].startswith('"'):
            i += 1
            block_lines.append(lines[i])
        msgid = _read_po_string(block_lines, "msgid")
        msgstr = _read_po_string(block_lines, "msgstr")
        entries.append(
            {
                "start": block_start,
                "end": i,
                "lines": block_lines,
                "msgid": msgid,
                "msgstr": msgstr,
            }
        )
        i += 1
    return entries


def _read_po_string(block_lines: list[str], key: str) -> str:
    parts: list[str] = []
    collecting = False
    for line in block_lines:
        if line.startswith(key + " "):
            collecting = True
            val = line[len(key) + 1 :].strip()
            parts.append(_unquote(val))
            continue
        if collecting and line.startswith('"'):
            parts.append(_unquote(line.strip()))
            continue
        if collecting and not line.startswith('"'):
            break
    return "".join(parts)


def _unquote(s: str) -> str:
    if s.startswith('"') and s.endswith('"'):
        return bytes(s[1:-1], "utf-8").decode("unicode_escape")
    return s


def _quote(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    if "\n" in s:
        chunks = escaped.split("\\n")
        return "\n".join(f'"{part}\\n"' for part in chunks[:-1]) + (
            f'\n"{chunks[-1]}"' if chunks[-1] else ""
        )
    return f'"{escaped}"'


def format_msgstr(msgstr: str) -> list[str]:
    if "\n" in msgstr:
        parts = msgstr.split("\n")
        lines = [f'msgstr ""\n']
        for part in parts:
            lines.append(f'"{part}\\n"\n')
        return lines
    return [f"msgstr {_quote(msgstr)}\n"]


def main() -> None:
    content = PO_PATH.read_text(encoding="utf-8")
    entries = parse_po(content)
    lines = content.splitlines(keepends=True)
    offset = 0

    for entry in entries:
        msgid = entry["msgid"]
        if msgid not in TRANSLATIONS:
            continue
        new_msgstr = TRANSLATIONS[msgid]
        start = entry["start"] + offset
        end = entry["end"] + offset

        block = lines[start : end + 1]
        new_block: list[str] = []
        msgstr_written = False
        for line in block:
            if line.startswith("#, fuzzy"):
                if msgid in REMOVE_FUZZY_FOR:
                    continue
            if line.startswith("msgstr "):
                if not msgstr_written:
                    new_block.extend(format_msgstr(new_msgstr))
                    msgstr_written = True
                continue
            if msgstr_written and line.startswith('"'):
                continue
            new_block.append(line)

        lines[start : end + 1] = new_block
        offset += len(new_block) - (end - start + 1)

    PO_PATH.write_text("".join(lines), encoding="utf-8")
    print(f"Updated {PO_PATH}")


if __name__ == "__main__":
    main()
