# Changelog

All notable changes to **netbox-nsm** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.4] - unreleased

### Fixed

- [#18](https://github.com/christianbur/netbox-nsm/issues/18): Assign Link element picker loads first page on focus without typing `*` (aligned with rule editor browse)
- [#18](https://github.com/christianbur/netbox-nsm/issues/18): Assign Link picker dropdown closes on blur even when showing "No results"
- [#18](https://github.com/christianbur/netbox-nsm/issues/18): Assign Link picker layout and markup aligned with rule editor (assign field structure, pill markup, scroll load-more)
- [#18](https://github.com/christianbur/netbox-nsm/issues/18): Assign Link form fields unified styling — element search matches native `form-select`, flat layout without nested panel
- Rulebook Changelog: field layout, rule CRUD, assignments, and TypeConfig panels with readable summaries (UI + REST API)
- Assign Link picker UX aligned with rule editor (dropdown only on focus)
- [#17](https://github.com/christianbur/netbox-nsm/issues/17): ObjectLink delete raised
  `SerializerNotFound` for custom objects (`TableNModel`) as `object_b` — fixed via
  `serialize_object()` fallback in `ObjectLinkSerializer` (Security Panel and REST API).

## [0.2.3] - 2026-06-06

### Changed

- COT: Changed shema nsm_portable_schema.json

## [0.2.2] - 2026-06-06

### Changed

- COT: Change nsm_portable_schema.json

## [0.2.1] - 2026-06-06

### Changed

- COT: Changed nsm_portable_schema.json

## [0.2.1] - 2026-06-06

### Added

- COT: change nsm_portable_schema.json

## [0.2.1] - 2026-06-05

### Changed

- Portable schema (`nsm_portable_schema.json`): remove field-level `group_name` UI
  groups from all built-in custom object types
- Remove `display_template` fields from `nsm_labels` and `nsm_zones` in the portable
  schema; display templates remain in TypeConfig metadata applied by Setup
- Normalize `nsm_addresses` field weights (`range` 11, `prefix` 12, `group` 13) and
  `nsm_labels.custom_type` weight (11) for consistent form ordering

### Notes

- Re-run Setup → Custom Objects (schema apply) to sync existing NetBox instances

## [0.2.0] - 2025-06-06

First release in the 0.2.x line.

### Added

- Security Panel on prefixes, IPs, devices, VMs, and custom objects
- Rulebooks with flexible field/column layout and AG Grid policy views
- Zone matrix, All Rules grid, IP Analysis, and Object Analyzer
- Setup wizard with built-in custom object types and demo rulebooks
- REST API for rulebooks, rules, type configs, object links, and related objects
- Squashed database schema in a single `0001_initial` migration

### Requires

- NetBox 4.5+
- [netbox-custom-objects](https://github.com/netboxlabs/netbox-custom-objects)

### Notes

- Documentation-only plugin — no firewall push or policy enforcement
- See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for open items

[0.2.1]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.1
[0.2.0]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.0
[0.2.2]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.2
[0.2.3]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.3
