# Release Process - netbox-nsm

**Schnell**: dev bearbeiten → CHANGELOG + version erhöhen → Release Commit → **dev pushen** → **main mergen** → **Tag erstellen** → Tag pushen

## ⚠️ KRITISCH: Tag-Platzierung

Das Tag **muss auf dem Merge-Commit zeigen**, nicht auf Release-Commit!

```
Merge dev into main (26fd0b9) ← TAG v0.4.23 HIER! ✅
Release v0.4.23 (2df83ed)     ← NICHT hier! ❌
```

**Richtig**: Tag erst nach Merge erstellen!

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

## Häufige Fehler

### ❌ Tag auf falschem Commit?

```bash
# Alte Tag löschen
git tag -d v0.4.23
git push origin :refs/tags/v0.4.23

# Neu auf Merge-Commit erstellen
git tag -a v0.4.23 26fd0b9 -m "Release v0.4.23"
git push origin v0.4.23
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
git commit -m "Merge dev into main for release v0.4.23"
git push origin main
```

### ❌ CHANGELOG format unklar?

```markdown
## [0.4.23] - 2026-07-12

### Added
- Tenant column in Cell-Tree
- Zone/Label source info

### Changed
- Dynamic column widths

### Fixed
- Collect all inherited zones
```

---

## GitHub Verifizierung

Nach Release prüfen:
1. GitHub Releases Tab: Tag v0.4.23 sichtbar?
2. Branch `main`: Merge-Commit sichtbar?
3. Branch `dev`: Release-Commit sichtbar?
4. Tag Details: Zeigt auf Merge-Commit (26fd0b9)?

Alle grün? → Release erfolgreich! ✅
