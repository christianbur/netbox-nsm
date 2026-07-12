# Release Process - netbox-nsm

Dokumentation für manuelles Bauen und Veröffentlichung eines Releases.

**Wichtig**: netbox-nsm verwendet ein **dev→main Merge-Modell**:
- `dev` = Entwicklungs-Branch mit neuen Features
- `main` = Production/Release-Branch
- **Release**: dev wird in main gemerged, dann tagged

## ⚠️ KRITISCH: Tag-Platzierung

Das **v0.4.23 Tag muss auf dem Merge-Commit zeigen**, nicht auf dem Release-Commit!

**Richtig:**
```
Merge dev into main (26fd0b9) ← TAG v0.4.23 HERE!
Release v0.4.23 (2df83ed)     ← Nicht hier!
```

**Warum?** Das Release muss den finalen main-Code enthalten, inkl. aktualisierter Doku/Prozess.

**Fix (falls falsch getaggt):**
```bash
git tag -d v0.4.23                    # Lokales Tag löschen
git push origin :refs/tags/v0.4.23   # Remote Tag löschen
git tag -a v0.4.23 26fd0b9 -m "..."  # Neues Tag auf Merge-Commit
git push origin v0.4.23
```

## Schnelleinstieg - 9 Schritte

1. ✏️ **CHANGELOG.md** aktualisieren
2. ✏️ **version.py** erhöhen (0.4.22 → 0.4.23)
3. 💾 **Release Commit** erstellen
4. 🚀 **Dev branch** zu GitHub pushen
5. 🔀 **Dev in main mergen** (Merge-Commit) ← **Zuerst mergen!**
6. 🚀 **Main branch** zu GitHub pushen
7. 🏷️ **Git Tag auf Merge-Commit** erstellen (v0.4.23) ← **Nach dem Merge!**
8. 🚀 **Tag** zu GitHub pushen
9. ✅ **GitHub** verifizieren (Tag + Branches)

**⚠️ WICHTIG**: Das Tag muss auf dem **Merge-Commit** zeigen, nicht auf dem Release-Commit! Nur so enthält die Release den finalen main-Code.

---



## Schritt 1: Vorbereitung auf dev branch

```bash
# In den Projekt-Verzeichnis wechseln
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm

# Sicherstellen, dass man auf dem dev branch ist
git checkout dev

# Alle lokalen Änderungen committen (oder stashen)
git status
```

## Schritt 2: Aktuelle Version ermitteln

```bash
# Letzte Release-Tags anzeigen
git tag -l | grep "^v0.4" | sort -V | tail -5

# Commits seit letztem Release anzeigen
git log --oneline v0.4.22..HEAD
```

## Schritt 3: CHANGELOG.md aktualisieren

1. Datei `CHANGELOG.md` öffnen
2. Neue Version-Sektion am Anfang hinzufügen mit Format:

```markdown
## [0.4.23] - 2026-07-12

### Added
- Feature 1
- Feature 2

### Changed
- Improvement 1
- Improvement 2

### Fixed
- Bugfix 1
```

3. Die Commits seit letztem Release kategorisieren (Added, Changed, Fixed)
4. Datei speichern

## Schritt 4: Version erhöhen

```bash
# Datei netbox_nsm/version.py öffnen
# Alte Version: __version__ = "0.4.22"
# Neue Version: __version__ = "0.4.23"
```

Bearbeite `netbox_nsm/version.py`:
```python
__version__ = "0.4.23"
```

## Schritt 5: Release Commit erstellen

```bash
# Alle Änderungen stagen
git add -A

# Release Commit mit aussagekräftiger Message erstellen
git commit -m "Release v0.4.23

## IP Analyzer Cell-Tree improvements

- Add Tenant column after Type
- Zone/Label source info in tooltips
- Subnet lazy-load expansion
- Dynamic column widths (content-responsive)

Commits:
- a7b0a4e IP Analyzer Cell-Tree: Add Tenant column
- 67ef560 IP Analyzer: Add source info to Labels and Zones
- (weitere Commits auflisten)"
```

Oder verkürzt:
```bash
git commit -m "Release v0.4.23"
```

## Schritt 6: Dev Branch pushen

```bash
# Dev zu GitHub pushen
git push origin dev
```

**Note**: Tag wird NACH dem Merge erstellt (siehe Schritt 7)!

## Schritt 7: Dev in Main mergen

```bash
# Main aktualisieren
git checkout main
git pull origin main

# Dev mit --no-ff mergen (Merge-Commit)
git merge --no-ff dev -m "Merge dev into main for release v0.4.23"

# Main pushen
git push origin main
```

## Schritt 8: Git Tag auf Merge-Commit erstellen

**⚠️ WICHTIG**: Das Tag muss auf dem **gerade erstellten Merge-Commit** zeigen!

```bash
# Den Merge-Commit Commit-Hash prüfen
git log --oneline -3

# Tag auf dem Merge-Commit erstellen (z.B. 26fd0b9)
git tag -a v0.4.23 26fd0b9 -m "Release v0.4.23: IP Analyzer Cell-Tree improvements

## New Features
- Tenant column in Cell-Tree
- Zone/Label source info displayed
- Subnet lazy-load expansion

See CHANGELOG.md for full details."
```

## Schritt 9: Tag zu GitHub pushen (als christian-User)

```bash
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git push origin v0.4.23"
```

Oder lokal pushen (SSH müsste konfiguriert sein):
```bash
git push origin v0.4.23
```

## Schritt 10: Release auf GitHub verifizieren

1. Browser: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.23
2. Tag sollte visible sein mit Release-Notes
3. **Dev Branch** sollte aktualisiert sein
4. **Main Branch** sollte den Merge-Commit enthalten
5. `origin/HEAD` sollte auf main zeigen (main ist primary)

## Vollständiger Workflow (Schritt-für-Schritt)

```bash
# 1. Als christian-User anmelden
su - christian
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm

# 2. Dev branch aktualisieren
git checkout dev
git pull origin dev

# 3. Letzte Release prüfen
git tag -l | grep "^v0.4" | sort -V | tail -1
git log --oneline -10

# 4. CHANGELOG.md und version.py bearbeiten (manuell!)
nano CHANGELOG.md
nano netbox_nsm/version.py

# 5. Release Commit erstellen
git add CHANGELOG.md netbox_nsm/version.py
git commit -m "Release v0.4.23"

# 6. Dev zu GitHub pushen
git push origin dev

# 7. Wechsel zu main und mergen
git checkout main
git pull origin main
git merge --no-ff dev -m "Merge dev into main for release v0.4.23"
git push origin main

# 8. Merge-Commit Hash ermitteln
git log --oneline -2  # Zeigt den Merge-Commit

# 9. Tag auf dem Merge-Commit erstellen (ersetze 26fd0b9 mit aktuellem Hash!)
git tag -a v0.4.23 26fd0b9 -m "Release v0.4.23: IP Analyzer Cell-Tree improvements

New Features:
- Tenant column in Cell-Tree
- Zone/Label source info displayed
- Subnet lazy-load expansion

See CHANGELOG.md for full details."

# 10. Tag zu GitHub pushen
git push origin v0.4.23

# 11. Zurück zu dev
git checkout dev

# 12. Logout
exit
```

## Kompakter Workflow (für erfahrene Benutzer)

Als christian-User:

```bash
su - christian -c "
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm

# Release Commit erstellen und dev pushen
git add CHANGELOG.md netbox_nsm/version.py && git commit -m 'Release v0.4.23' && git push origin dev

# Wechsel zu main und mergen
git checkout main && git pull origin main
git merge --no-ff dev -m 'Merge dev into main for release v0.4.23'
git push origin main

# Tag auf dem Merge-Commit erstellen
MERGE_HASH=\$(git rev-parse HEAD)
git tag -a v0.4.23 \$MERGE_HASH -m 'Release v0.4.23'
git push origin v0.4.23

# Zurück zu dev
git checkout dev
"
```

**Wichtig**: CHANGELOG.md und version.py müssen manuell VOR diesem Workflow bearbeitet werden!

## Automatisierte Checks vor Release (optional)

```bash
# Tests laufen (falls vorhanden)
python manage.py test netbox_nsm.tests

# Statische Code-Analyse
pylint netbox_nsm

# Python-Syntax prüfen
python -m py_compile netbox_nsm/**/*.py

# Git Status prüfen
git status

# Commits seit letztem Release
git log --oneline v0.4.22..HEAD
```

## Troubleshooting

### SSH Permission Denied
```bash
# Als falscher User? Als christian-User raus:
su - christian

# SSH-Keys checken
ssh -T git@github.com

# Sollte antworten: "Hi christianbur! You've successfully authenticated..."
```

### Falscher Branch
```bash
# Aktuellen Branch prüfen
git branch

# Zu dev wechseln
git checkout dev
```

### Unstaged Changes
```bash
# Änderungen stagen
git add -A

# Oder nur bestimmte Dateien
git add CHANGELOG.md netbox_nsm/version.py
```

### Merge-Konflikte bei dev→main

```bash
# Falls Konflikte auftreten beim Merge
git status

# Konflikt-Dateien öffnen und Konflikte beheben
# Dann:
git add <konflikt-datei>

# Nach allen Konflikten behoben:
git commit -m "Merge dev into main for release v0.4.23"
git push origin main
```

### Falscher Tag-Name

```bash
# Tag lokal löschen
git tag -d v0.4.23

# Remote Tag löschen (vorsichtig!)
git push origin :refs/tags/v0.4.23

# Neu erstellen mit korrektem Namen
git tag -a v0.4.23 -m "Release v0.4.23"
git push origin v0.4.23
```

### Bereits auf main?

```bash
# Aktuellen Branch prüfen
git branch

# Falls bereits auf main und nicht auf dev:
git checkout dev
```

### Main ist nicht aktuell

```bash
# Main pullen bevor mergen
git checkout main
git pull origin main
git checkout dev
git merge main dev  # dev mit main synchronisieren falls nötig
git checkout main
git pull origin main
git merge --no-ff dev -m "Merge dev into main for release v0.4.23"
```

## Version Numbering

netbox-nsm verwendet **Semantic Versioning**:

- `v0.4.23` = MAJOR.MINOR.PATCH
  - MAJOR (0) = grundlegende Architektur
  - MINOR (4) = Feature-Releases
  - PATCH (23) = Bugfixes und kleine Verbesserungen

Nächste Versionen:
- Bugfix: `v0.4.24`
- Feature: `v0.5.0`
- Major: `v1.0.0`

## Refs

- GitHub Repo: https://github.com/christianbur/netbox-nsm
- CHANGELOG: [CHANGELOG.md](CHANGELOG.md)
- Version: [netbox_nsm/version.py](netbox_nsm/version.py)
