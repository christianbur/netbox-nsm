# Known Issues & Open Items

> Status as of 2025-06 (v0.2.0)

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

## i18n: `de.po` quality

Many `de` entries are still empty (English fallback) or marked `fuzzy` with incorrect
translations. Refresh with:

```bash
docker exec -u root netbox-dev bash -c 'cd /opt/netbox/netbox && /opt/netbox/venv/bin/python -c "
import os, django
os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\", \"netbox.settings\")
django.setup()
os.chdir(\"/opt/netbox-nsm/netbox_nsm\")
from django.core.management import call_command
call_command(\"makemessages\", locale=[\"de\", \"en\"], verbosity=1)
"'
./scripts/netbox-compilemessages.sh   # or msgfmt as root if mount permissions block writes
```

Source strings (`msgid`) must stay **English**; only `de/LC_MESSAGES/django.po` carries German `msgstr`.

## Security Panel: inherited links need manual "Load" click

Inherited links are not loaded on page load — the user must click **Load** to fetch them.
This avoids extra API calls on every page view but may not be obvious.
Consider auto-loading inherited links for objects that have no direct links at all.

---

## Zone Matrix: address-based rulebooks show unhelpful matrix

The Zone Matrix view is only useful for rulebooks that use Zone objects in Source and
Destination. For address-based or label-based rulebooks, the matrix shows no meaningful data.
A "not applicable" notice should be shown when no zone-typed fields exist.

---

## Integration tests (`test_netbox` / CI)

NSM tests run inside a full NetBox stack. Errors such as missing `custom_objects_*`
tables or `_cable_peer_id` columns usually mean **plugin version skew** in the test
environment (especially `netbox_custom_objects`), not NSM logic. Align plugin versions
with the dev Docker stack before debugging NSM test failures.

---

## Planned for 0.3.x (not bugs)

- **Locale `.po`:** stale `#:` comments pointing at removed templates (cosmetic; refresh via
  `makemessages` when touching translations).
