# Release Process - netbox-nsm

Dokumentation für manuelles Bauen und Veröffentlichung eines Releases.

**Wichtig**: netbox-nsm verwendet ein **dev→main Merge-Modell**:
- `dev` = Entwicklungs-Branch mit neuen Features
- `main` = Production/Release-Branch
- **Release**: dev wird in main gemerged, dann tagged

## Schnelleinstieg - 9 Schritte

1. ✏️ **CHANGELOG.md** aktualisieren
2. ✏️ **version.py** erhöhen (0.4.22 → 0.4.23)
3. 💾 **Release Commit** erstellen
4. 🏷️ **Git Tag** erstellen (v0.4.23)
5. 🚀 **Dev branch** zu GitHub pushen
6. 🚀 **Tag** zu GitHub pushen
7. 🔀 **Dev in main mergen** (Merge-Commit)
8. 🚀 **Main branch** zu GitHub pushen
9. ✅ **GitHub** verifizieren (Tag + Branches)

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

## Schritt 6: Git Tag erstellen

```bash
# Annotated Tag mit aussagekräftiger Nachricht
git tag -a v0.4.23 -m "Release v0.4.23: IP Analyzer Cell-Tree improvements

## New Features
- Tenant column in Cell-Tree
- Zone/Label source info displayed
- Subnet lazy-load expansion

See CHANGELOG.md for full details."
```

## Schritt 7: Dev und Tag zu GitHub pushen (als christian-User)

```bash
# Sicherstellen, dass man die richtigen SSH-Keys hat
ssh -T git@github.com

# Dev Branch pushen
git push origin dev

# Tag pushen
git push origin v0.4.23
```

Oder mit `su`:
```bash
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git push origin dev && git push origin v0.4.23"
```

## Schritt 8: Dev in Main mergen (als christian-User)

```bash
# Wechsel zu main und aktualisieren
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git checkout main && git pull origin main"

# Dev in main mergen mit Merge-Commit
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git merge --no-ff dev -m 'Merge dev into main for release v0.4.23'"

# Main zu GitHub pushen
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git push origin main"

# Zurück zu dev
git checkout dev
```

**Wichtig**: Das Merge-Commit erstellt eine klare Trennlinie zwischen den Releases. Die `--no-ff` Flag erzeugt immer einen Merge-Commit, auch wenn es ein Fast-Forward sein könnte.

Merge-Commit Message Format:
```
Merge dev into main for release v0.4.23
```

## Schritt 9: Release auf GitHub verifizieren

1. Browser: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.23
2. Tag sollte visible sein mit Release-Notes
3. **Dev Branch** sollte aktualisiert sein
4. **Main Branch** sollte den Merge-Commit enthalten
5. `origin/HEAD` sollte auf main zeigen (main ist primary)

## Vollständiger Workflow (all in one) - als christian-User

```bash
# 1. Zur christian-User wechseln und ins Projekt gehen
su - christian
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm

# 2. Dev branch aktualisieren und auf dem Neuesten sein
git checkout dev
git pull origin dev

# 3. Version prüfen - Commits seit letztem Release
git log --oneline -5
git tag -l | grep "^v0.4" | sort -V | tail -1   # Letzte Version

# 4. CHANGELOG.md und version.py manuell editieren
nano CHANGELOG.md
nano netbox_nsm/version.py

# 5. Release committen
git add CHANGELOG.md netbox_nsm/version.py
git commit -m "Release v0.4.23"

# 6. Tag erstellen
git tag -a v0.4.23 -m "Release v0.4.23: IP Analyzer Cell-Tree improvements

New Features:
- Tenant column in Cell-Tree
- Zone/Label source info displayed
- Subnet lazy-load expansion

See CHANGELOG.md for full details."

# 7. Dev Branch zu GitHub pushen
git push origin dev
git push origin v0.4.23

# 8. Dev in main mergen
git checkout main
git pull origin main
git merge --no-ff dev -m "Merge dev into main for release v0.4.23"
git push origin main

# 9. Zurück zu dev
git checkout dev

# 10. Logout
exit
```

## Kompakter Workflow (Einzelcommand)

```bash
su - christian -c "
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm

# Git Status prüfen
git status

# (CHANGELOG.md und version.py manuell editieren!)

# Release Commit
git add CHANGELOG.md netbox_nsm/version.py
git commit -m 'Release v0.4.23'

# Tag erstellen
git tag -a v0.4.23 -m 'Release v0.4.23'

# Dev pushen
git push origin dev
git push origin v0.4.23

# In main mergen
git checkout main
git pull origin main
git merge --no-ff dev -m 'Merge dev into main for release v0.4.23'
git push origin main

# Zurück zu dev
git checkout dev
"
```

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
