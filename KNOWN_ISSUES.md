# Known Issues & Open Items

> Status as of 2025-06 (v0.1.0-dev)

---

## TypeConfig values not updated by Setup Wizard Sync

**Symptom:** After changing TypeConfig field values in `builtin_types.py` or `views/setup.py`
(e.g. `matching_class`, `allowed_placements`), re-running the Setup Wizard "Sync" does not
update existing DB records — only creates missing ones.

**Workaround:** Update TypeConfig records manually in the NetBox UI
(**Security → Configuration → Type Configs**) or via the REST API.

**Affected records (current state):**
- `nsm_business_apps`: `matching_class=other`, `allowed_placements=["fixed"]`
- `nsm_network_apps`: `matching_class=application`, `allowed_placements=["fixed"]`

---

## `setup_typeconfigs.py` SOURCE_CTS / DEST_CTS stale entries

`setup_typeconfigs.py` still lists `business apps` and `network apps` in `SOURCE_CTS` and
`DEST_CTS`, but their TypeConfigs now have `allowed_placements=["fixed"]` only.
These entries in the script have no effect (the TypeConfig overrides them) but are misleading.

**Fix:** Remove `business apps` / `network apps` from `SOURCE_CTS` / `DEST_CTS` in
`setup_typeconfigs.py`.

---

## `builtin_types.py` areas vs. TypeConfig placements mismatch

`nsm_business_apps` and `nsm_network_apps` both have `"areas": ["source", "destination"]`
in `builtin_types.py`, but their TypeConfigs use `allowed_placements: ["fixed"]`.

The `areas` field in `builtin_types.py` controls which COT "sections" (source/destination
panels on the object detail page) the type appears in — separate from rule column placement.
The mismatch may be intentional (show in source/dest panels, but only allow in fixed rule
columns) — needs clarification.

---

## Django template cache requires restart after template changes

NetBox uses Django's `cached.Loader`, which holds compiled templates in RAM.
**Any `.html` file change requires a full process restart** — a reload is not sufficient.

```bash
docker compose restart netbox
```

This applies to all template changes (CSS inside `<style>` blocks included).

---

## i18n: `rule index`, `rule description` translations

The strings `"rule index"` and `"rule description"` have German translations
(`"Regelindex"`, `"Beschreibung"`) but appear verbatim (English) in the rule editor
because they're used as JavaScript placeholder strings, not Django `{% trans %}` blocks.
These need to be injected via a `data-i18n` attribute or a JSON translation dict.

---

## Security Panel: inherited links need manual "Load" click

Inherited links are not loaded on page load — the user must click **Load** to fetch them.
This avoids extra API calls on every page view but may not be obvious.
Consider auto-loading inherited links for objects that have no direct links at all.

---

## Zone Matrix: address-based rulebooks show unhelpful matrix

The Zone Matrix view is only useful for rulebooks that use Zone objects in Source and
Destination. For address-based or label-based rulebooks, the matrix shows no meaningful data.
A "not applicable" notice should be shown when no zone-typed fields exist.
