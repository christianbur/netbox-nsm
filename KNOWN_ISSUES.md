# Known Issues & Open Items

> Status as of 2025-06 (v0.1.0-dev)

---

## TypeConfig values not updated by Setup Wizard Sync

**Symptom:** After changing TypeConfig field values in `builtin_types.py` or `views/setup.py`
(e.g. `matching_class`, `panel_slugs`), re-running the Setup Wizard "Sync" does not
update existing DB records — only creates missing ones.

**Workaround:** Update TypeConfig records manually in the NetBox UI
(**NSM → Configuration → Type Configs**) or via the REST API (`type-configs`).

**Affected records (example):** Custom types whose `panel_slugs` in `TYPECONFIG_SPECS`
differ from what is already stored in the database.

---

## `builtin_types.py` areas vs. TypeConfig `panel_slugs`

`areas` in `builtin_types.py` is synced to `TypeConfig.panel_slugs` by
**Sync built-in types**. Rulebook column placement (`RulebookField.placement`) is
separate: a type can appear in panel sections `source`/`destination` while only
being attachable to `fixed` rule fields (e.g. services).

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
