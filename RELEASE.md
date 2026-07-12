# Release Process - netbox-nsm

**Schnell**: dev bearbeiten → CHANGELOG + version erhöhen → Release Commit → **dev pushen** → **main mergen** → **Tag erstellen** → Tag pushen

## ⚠️ KRITISCH: Tag-Platzierung

Das Tag **muss auf dem neuesten main-Commit zeigen** (nach allen Merges), nicht auf einen älteren Commit!

```
3915ac5 main (after all merges) ← TAG v0.4.23 HIER! ✅
  └─ version.py = 0.4.23
  └─ Alle Features
  └─ Finale Doku
```

**WICHTIG**: 
- Tag wird **AUF main** erstellt (nicht auf dev!)
- Das muss der **neueste main** Commit sein  
- GitHub Actions triggert auf Tags und baut damit → MUSS korrekte version.py haben!
- Falls Tag auf altem Commit: PyPI-Upload schlägt fehl mit "File already exists"

**Richtig**: Tag erst nach Merge auf main erstellen!

---

## Workflow - 9 Schritte

1. **CHANGELOG.md** + **version.py** editieren
2. **Release Commit**: `git add CHANGELOG.md netbox_nsm/version.py && git commit -m "Release v0.4.23"`
3. **Dev pushen**: `git push origin dev`
4. **Zu main wechseln**: `git checkout main && git pull origin main`
5. **Mergen**: `git merge --no-ff dev -m "Merge dev into main for release v0.4.23"`
6. **Main pushen**: `git push origin main`
7. **Merge-Hash prüfen**: `git log --oneline -2`
8. **Tag erstellen** (auf Merge-Commit): `git tag -a v0.4.23 26fd0b9 -m "Release v0.4.23: ..."`
9. **Tag pushen**: `git push origin v0.4.23` + `git checkout dev`

---

## Detailliert - Step by Step

### Schritt 1-3: Release vorbereiten & committen

```bash
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm
git checkout dev
git pull origin dev

# Bearbeite diese Dateien manuell:
# - CHANGELOG.md: Neue [0.4.23] Sektion mit Added/Changed/Fixed
# - netbox_nsm/version.py: __version__ = "0.4.23"

# Release committen
git add CHANGELOG.md netbox_nsm/version.py
git commit -m "Release v0.4.23"

# Dev zu GitHub
git push origin dev
```

### Schritt 4-6: Main aktualisieren & mergen

```bash
# Zu main wechseln
git checkout main
git pull origin main

# Dev in main mergen (erzeugt Merge-Commit)
git merge --no-ff dev -m "Merge dev into main for release v0.4.23"

# Main zu GitHub
git push origin main
```

### Schritt 7-9: Tag erstellen & pushen

```bash
# Merge-Commit Hash ermitteln
git log --oneline -2
# Output z.B.:
# 26fd0b9 Merge dev into main for release v0.4.23
# 2df83ed Release v0.4.23

# Tag auf dem Merge-Commit erstellen (26fd0b9)
git tag -a v0.4.23 26fd0b9 -m "Release v0.4.23: IP Analyzer Cell-Tree improvements

## New Features
- Tenant column in Cell-Tree
- Zone/Label source info displayed
- Subnet lazy-load expansion

See CHANGELOG.md for full details."

# Tag zu GitHub pushen
git push origin v0.4.23

# Zurück zu dev
git checkout dev
```

---

## Ein-Liner für Profis

Nur wenn **CHANGELOG.md + version.py bereits editiert sind**:

```bash
su - christian -c "
cd /home/christian/homelab/docker/netbox_dev/netbox-nsm
git add CHANGELOG.md netbox_nsm/version.py && git commit -m 'Release v0.4.23' && git push origin dev && \
git checkout main && git pull origin main && git merge --no-ff dev -m 'Merge dev into main for release v0.4.23' && git push origin main && \
HASH=\$(git rev-parse HEAD) && git tag -a v0.4.23 \$HASH -m 'Release v0.4.23' && git push origin v0.4.23 && \
git checkout dev
"
```

---

## ⚠️ KRITISCH: pyproject.toml Version-Sync

**WICHTIG**: Sowohl **version.py** ALS AUCH **pyproject.toml** müssen die gleiche Version haben!

```python
# netbox_nsm/version.py
__version__ = "0.4.24"  # ← aktualisieren

# pyproject.toml  
version = "0.4.24"      # ← AUCH hier aktualisieren!
```

**Grund**: setuptools liest die Version von **pyproject.toml**, nicht von version.py! 
- Wenn pyproject.toml älter ist → setuptools baut alte Version
- GitHub Actions baut dann 0.4.22 obwohl Tag 0.4.24
- PyPI lehnt mit "File already exists" ab!

**Checkliste vor Release**:
- [ ] netbox_nsm/version.py aktualisiert
- [ ] pyproject.toml `version = "..."` aktualisiert (NICHT vergessen!)
- [ ] CHANGELOG.md neue Sektion hinzugefügt
- [ ] Beide Files im Release Commit: `git add CHANGELOG.md netbox_nsm/version.py pyproject.toml`

---

## Häufige Fehler

### ❌ PyPI: "File already exists" + falsche Version

**Symptom**: Workflow zeigt `Building netbox_nsm-0.4.22` aber Tag ist `v0.4.24`

**Ursache**: pyproject.toml hat alte Version oder nicht aktualisiert

**Lösung**:
```bash
# 1. pyproject.toml auf richtige Version setzen
# 2. Commit + Push
# 3. Tag neu erstellen auf neuesten main
# 4. GitHub Actions triggert neu → korrekte Version
```

### ❌ Tag auf falschem Commit?

```bash
# Alte Tag löschen
git tag -d v0.4.24
git push origin :refs/tags/v0.4.24

# Neu auf aktuellen main erstellen
git tag v0.4.24  # (ohne -a für Lightweight Tag, zeigt direkt auf HEAD)
git push origin v0.4.24
```

### ❌ SSH Permission Denied?

Nur als `christian` User pushen:
```bash
su - christian -c "cd /home/christian/homelab/docker/netbox_dev/netbox-nsm && git push origin main"
```

### ❌ Merge-Konflikte?

```bash
# Konflikt-Dateien prüfen
git status

# Manuell in Editor beheben, dann:
git add <konflikt-datei>
git commit -m "Merge dev into main for release v0.4.24"
git push origin main
```

### ❌ CHANGELOG format unklar?

```markdown
## [0.4.24] - 2026-07-12

### Added
- Feature 1
- Feature 2

### Changed
- Changed item

### Fixed
- Fixed issue
```

---

## GitHub Verifizierung

Nach Release prüfen:
1. GitHub Releases Tab: Tag v0.4.24 sichtbar?
2. Branch `main`: Merge-Commit sichtbar?
3. Branch `dev`: Release-Commit sichtbar?
4. Tag Details: Zeigt auf aktuellen main-Commit?
5. GitHub Actions: Workflow gestartet und baute 0.4.24? ✅
6. PyPI: https://pypi.org/project/netbox-nsm/0.4.24/ verfügbar?

Alle grün? → Release erfolgreich! ✅

---

## Release Checkliste (Schnellreferenz)

- [ ] **CHANGELOG.md** neue [0.4.24] Sektion mit Added/Changed/Fixed
- [ ] **netbox_nsm/version.py** auf "0.4.24" (beide Dateien!)
- [ ] **pyproject.toml** version = "0.4.24" (CRITICAL!)
- [ ] **Release Commit**: `git commit -m "Release v0.4.24"`
- [ ] **Dev gepusht**: `git push origin dev`
- [ ] **Main gemerged**: `git merge --no-ff dev` + `git push origin main`
- [ ] **Tag erstellt** auf aktuellem main: `git tag v0.4.24 && git push origin v0.4.24`
- [ ] **Verifiziert**:
  - [ ] `git show v0.4.24:pyproject.toml | grep version` → 0.4.24 ✓
  - [ ] `git show v0.4.24:netbox_nsm/version.py` → 0.4.24 ✓
  - [ ] GitHub Actions Workflow gestartet und lief bis zum Ende
  - [ ] Keine "File already exists" Fehler von PyPI
  - [ ] https://pypi.org/project/netbox-nsm/ zeigt neue Version
