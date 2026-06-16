# Known Issues

> Status as of 2026-06 (v0.4.5)

There are **no known critical issues** in the current release.

For recent fixes and breaking changes, see [CHANGELOG.md](CHANGELOG.md).

## Notes (non-blocking)

- **Django template cache** — NetBox uses Django's `cached.Loader`. Template changes require a full process restart (`docker compose restart netbox`).
- **i18n** — Some German (`de`) entries may still be empty or marked `fuzzy`. Refresh with `makemessages` / `compilemessages` when touching translations.
- **Security Panel inherited links** — Inherited links load on demand (user clicks **Load**); not auto-fetched on page load.
- **Zone Matrix** — Meaningful only for rulebooks with zone-typed source/destination fields; address-based rulebooks show limited matrix data.
- **Integration tests** — NSM tests run inside a full NetBox stack. Missing `custom_objects_*` tables usually indicate plugin version skew in the test environment, not NSM logic.
