# Changelog

All notable changes to **netbox-nsm** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.4.5] - 2026-06-16

### Changed

- **Object Config permissions** — view/add/change/delete use `netbox_custom_objects.view_customobjecttype` and `netbox_custom_objects.change_customobjecttype` (no more `netbox_nsm.*_typeconfig`)
- **Object Config writes** — UI edit/add/delete merge into COT `comments` via `save_nsm_config_document_for_cot` / `clear_nsm_config_from_cot_comments` (preserves non-`nsm_config` YAML)
- **Setup** — gated on `view_customobjecttype`; COT import on `add_customobjecttype`; Object Config sync on `change_customobjecttype`
- **Rulebook permissions** — removed legacy `view_rulebook` / `add_rulebook` fallbacks; access requires per-COT `netbox_custom_objects` permissions
- **`save_rulebook_config_for_cot`** — thin wrapper around unified `save_nsm_config_document_for_cot`
- **Security Panel** — object-link and panel-link views enforce COT / `nsm_object_link` permissions in `dispatch`
- **`VirtualAllRulesRulebook`** — `_meta` shim uses `RulebookListProxy` instead of removed `TypeConfig`

### Removed

- **`TypeConfig` permission anchor** — migration `0003` maps legacy typeconfig group permissions to COT permissions and deletes the model

### Migration guide (operators)

1. Upgrade plugin to **0.4.5** and run `python manage.py migrate netbox_nsm`.
2. Migration `0003` copies groups that had `view_typeconfig` / `add_typeconfig` / `change_typeconfig` / `delete_typeconfig` to the matching `netbox_custom_objects` CustomObjectType permissions.
3. Grant **Object Config** access via **Admin → Permissions → Custom Object Types** (`view` for read, `change` for edit/add/delete config).
4. Rulebook UI still uses per-rulebook COT model permissions (`view` / `change` / `add` / `delete` on each rule model).
5. Remove any custom permission assignments referencing `netbox_nsm.view_typeconfig` (etc.) — they are no longer defined.

## [0.4.4] - 2026-06-14

### Added

- **README screenshots** — `docs/img/` gallery for setup, rulebooks, rules, matrix, IP analysis
- **Rules toolbar** — bulk **Delete** next to **Add Rule** in the chrome bar

### Changed

- **Rules viewer layout** — full viewport height; zone sidebar scrolls internally; table fills remaining space
- **Matrix tab** — English UI strings; `{% trans %}` for i18n
- **Documentation** — compact English docs (`README`, `ARCHITECTURE`, `using_netbox_nsm`, etc.)

### Fixed

- **Tests** — suite green (849 pass); permissions, schema export, IPA/analysis imports aligned with 0.4.3 code
- **Rules panel height** — panel extends to viewport bottom without gap

## [0.4.3] - 2026-06-14

### Changed

- **Migrations** — squash `0001`–`0007` into a single `0001_initial` with `replaces` (fresh installs + upgrades from 0.4.1/0.4.2 without re-running data migrations)
- **Rulebook permissions** — UI and `nsm_config` API use per-COT `netbox-custom-objects`
  permissions (view / change / add / delete on each rulebook's rule model) instead of global
  `view_rulebook` / `add_rulebook`; legacy anchors removed (migration `0006`)
- **Navigation** — Rulebooks and Object Analyzer menu items require login only; Add rulebook
  button and page access are gated in views

### Removed

- **`Rulebook` permission anchor model** — `view_rulebook` / `add_rulebook` remain as legacy
  fallbacks in code but are no longer registered in Django

## [0.4.2] - 2026-06-12

### Added

- **`nsm_object_link.link_type` + `rulebook_slug`** — policy vs rulebook links on one COT; VDC on
  `netbox_object`; portable schema + choice set `nsm_object_link_type`
- **`nsm_config` areas + panel** — `rule_view.areas` and `panel` blocks in COT comments (replaces
  Section M2M and TypeConfig panel fields)
- **`nsm_analyze_address_sync`** management command — report-only address/IPAM sync analysis
  (`--format json`, exit code on issues)
- **Rulebook link UI** — assign/remove rulebooks via `nsm_object_link` (`rulebook-link/assign`,
  bulk assign on rulebook detail)

### Changed

- **Breaking:** native tables `CotRulebookAssignment`, `Section`, `NsmUiSettings`, and data
  `TypeConfig` removed; data migrated to COT comments / `nsm_object_link` (migration `0005`)
- **UI labels** — `menu_label`, `panel_label`, `setup_menu` only via `PLUGINS_CONFIG` (no Setup GUI)
- **Permissions** — rulebook host assignments use `netbox_custom_objects` on `nsm_object_link`;
  `TypeConfig` retained as unmanaged permission anchor only
- **Object Sync UI** removed; use `python manage.py nsm_analyze_address_sync`
- **`/type-configs/` API** removed; SSOT is `/nsm-configs/<slug>/`

### Removed

- Object Sync view, navigation entry, filters/pagination helpers
- Setup UI for menu/panel labels and hide-setup button
- Rulebook Assignment CRUD views, API, and sidebar menu


### Added

- **Rules tab row grouping** — per-rulebook column grouping (`row_group_by_col_id`), vertical side tabs,
  and resizable tab sidebar on the COT rules table
- **Object sync** — filterable NSM custom-object browser with pagination and object-link display
- **IP analysis** — service-layer refactor and expanded applet/API coverage
- **TypeConfig / custom objects** — list UI, schema setup panel, export and builder helpers
- **Tests** — row-grouping context and performance, security link groups, and related rulebook/setup
  coverage

### Changed

- **Rulebook metadata** — `parent_slug`, `matrix_tab_enabled`, and `row_group_by_col_id` move from
  `CotRulebook` into `nsm_config.rulebook` on the rulebook COT comments (migration `0003`)
- **Permissions** — `Rulebook` and `RulebookAssignment` anchor models for `view_rulebook` /
  `add_rulebook` and assignment custom perms (migration `0004`)
- **Migrations** — squash to `0001_initial` with upgrade migrations `0002`–`0004` (see `docs/DATABASE.md`)
- **Documentation** — architecture, rule storage, database, and usage guides aligned with row grouping

### Removed

- Legacy `OLD/` shim tree and superseded incremental migrations merged into the squash
- In-table Rule-Group rows and `rules_col_mode_locked` stub (tab-based Grouped rows only)

## [0.4.0] - 2026-06-09

### Added

- **COT rulebooks** — policies, rules tab, matrix, metadata, and list/detail UI on
  `CustomObjectType` slugs `nsm_rb_*` (native `Rulebook` / `Rule` models removed)
- **Rulebook templates** — four bundled templates (`nsm_rb_0001_template` …) with shared field
  catalog; setup import syncs schema and field `group_name` sort keys on all rulebook COTs
- **`rulebook_groups`** — bundled groups `1# Common` … `7# Notes`, display-label resolution for
  form sections and rules-tab column headers
- **Rulebook add/edit form** — NSM template override: section headings (`1== Common` + line),
  polymorphic M2M tabs, lazy object picker
- **Enforcement targets** — panel **Edit** / **Done** mode: Add, Remove, and link actions only
  while editing
- **IP Analyzer applet** — expanded object tree, warnings, drill-down, and stylesheet/JS coverage
- **Code layout** — packages `rulebooks/`, `security/`, `objects/`, `core/`, `analyzer/`

### Changed

- **Migrations** — single `0001_initial` for fresh empty databases (`CotRulebookAssignment`,
  `TypeConfig`, `NsmUiSettings`, …); incremental `0002`–`0007` for upgrades (see `docs/DATABASE.md`)
- **Rules tab** — group sort keys resolve to display labels (`Zones (Source)` not `2# Source`);
  collapsed column headers and Security Panel labels aligned
- **Enforcement targets** — host interface list always visible (collapse chevron removed)
- **Setup** — demo and `import_rulebook_templates()` re-apply template schema and sync groups

### Removed

- Native rulebook CRUD, rules editor, matrix view, object-group UI, and related API/serializers/tests
- `nsm_setting` / `nsm_replace` YAML in COT comments (labels are code-defined defaults)
- Legacy maintenance scripts (`drop_nsm_prefix`, `apply_nsm_unification`, …)

### Fixed

- **`resolve_group_name_for_display`** — strips leading `N# ` sort prefix (N = 1–9) and matches
  groups case-insensitively

## [0.3.2] - 2026-06-05

### Added

- **Rulebook detail** — **Enforcement targets** panel: assigned devices/VMs/VDCs with expandable
  interfaces, Security Panel object links (assign/edit/delete), host type badges (Device/VM/VDC),
  **All interfaces** toggle, and link-off icon when no zone/label links exist
- **Security Panel** — **Rulebooks** section on device/VM/VDC pages with count badge and **+**
  shortcut to add a rulebook assignment
- **`security_panel_links.build_object_link_rows`** — shared ObjectLink row builder for Security
  Panel and rulebook panel
- Tests for enforcement targets panel, bulk-assign GET/POST, and link row building

### Changed

- **Rulebook list** — **Assigned Objects** column renamed to **Target of enforcement targets**
- **Rulebook detail** — flat “Assigned Objects” attribute row removed in favour of the new panel
- **Security Panel** — rulebook assignment rows no longer show rulebook-type badge; indentation
  aligned with other link rows

### Fixed

- **`RulebookBulkAssignView`** — render via `ObjectView.get_extra_context` (fixes missing
  `render_to_response` on GET)
- **`RulebookBulkAssignView` POST** — do not shadow gettext `_` in `get_or_create` unpacking
  (fixes `RulebookAssignment object is not callable`)

## [0.3.1] - 2026-06-05

### Added

- **Rules tab** — **Clone** action in the Edit split-button dropdown; opens the add form with
  `copy_from` pre-filling metadata, object/group assignments, virtual groups, and the next free
  index (name left empty)
- **Rulebook list** — **Copy schema** action in the actions dropdown; creates a new rulebook from
  the add form with cloned metadata and field layout (`copy_schema_from`)
- **Setup** — **Hide Setup menu** control (section 5); dismiss is stored in `NsmUiSettings` and
  restored when `PLUGINS_CONFIG["netbox_nsm"]["setup_menu"]` goes from `false` back to `true`
- Tests for rule clone, rulebook schema copy, setup menu dismiss/restore, TypeConfig list UI,
  rules bulk-delete HTMX modal, and rulebook list delete dropdown

### Changed

- **Rulebook list** — hierarchy marker uses NetBox `record-depth` bullets instead of a custom dot;
  **Delete** moves into the Edit split-button dropdown when the rulebook has no rules
- **Rulebook detail** — Edit/Delete header buttons only on the primary tab (not Rules or Matrix)
- **Rulebook Fields tab** — subfield rows use `record-depth`; row actions use standard Edit button
  with **Add type** / **Delete** in the dropdown (system fields: Edit only)
- **TypeConfig list** — standard NetBox split Edit button; bulk Edit/Delete and row selection
  checkboxes removed
- **Rules tab** — bulk **Edit Selected** removed; **Delete Selected** opens an HTMX confirmation
  modal (dependent objects) instead of redirecting to the bulk-delete page; row actions use Edit
  with **Clone** / **Delete** in the dropdown

### Fixed

- **Rulebook Copy schema** — `copy_schema_from` is preserved on form submit so field layout is
  cloned correctly
- **Rules bulk delete modal** — dependent-object lookup uses `django.db.router` (fixes empty modal
  on HTMX confirmation)
- **Tests** — NetBox 4.6 compatibility (`SimpleTestCase` import), copy-schema list URL with
  `return_url`, delete hidden on detail when the rulebook has rules

### Migration

- **`0002_nsmuisettings_setup_menu_state`** — adds `setup_menu_dismissed` and
  `setup_menu_config_enabled` on `NsmUiSettings`. Run:
  `python manage.py migrate netbox_nsm`

## [0.3.0] - 2026-06-07

Major UI refresh: server-rendered **Rules** table and dedicated **Matrix** tab replace the
bundled AG Grid views. Documentation realigned to the **Starter demo** (Demo - Zone Matrix).

### Added

- **Rules tab** — server-rendered HTML table with filter query bar, Table / Group / Matrix
  toolbar, per-column search, pagination, CSV export, and cell display modes (comma / lines /
  **+N more** with per-cell expand)
- **Matrix tab** — dedicated zone matrix page per rulebook (`matrix_tab_enabled` on Rulebook)
- **Rulebook list** — hierarchy dot before child rulebook names (depth from parent chain)
- **Rulebook form** — parent picker excludes self and descendant rulebooks
- **IP Analysis** — CSV copy paths include object names (`all,branch,10.0.0.0/24` on **All**)
- **TypeConfig list** — readable *All types* badge in Panel column (`bg-primary-subtle`, dark-mode friendly)
- **Documentation** — Starter demo screenshots, [Universal linking](docs/using_netbox_nsm.md#universal-linking--any-netbox-object--nsm) (macro/micro zones, same zone in panel and rulebook), [`RULE_DATA_STORAGE.md`](docs/RULE_DATA_STORAGE.md)
- Bench script `scripts/create_addresses_million_scale.py`: nested `nsm_addresses` (200k hosts
  default) and 13k policy rules — **not** part of Setup wizard. See `docs/bench_addresses_million_scale.md`.

### Changed

- **All Rules** virtual rulebook no longer pinned in the rulebook list — open via
  `/plugins/netbox-nsm/rulebooks/0/` (overview) and `/rulebooks/0/rules/`
- **Setup demo** — Matrix scale test card removed from UI (backend action `create_demo_scale` unchanged)
- **Policy views** — Rules and Matrix no longer use AG Grid Community; vendored
  `ag-grid-community` assets and related grid API endpoints removed
- **Object Analyzer** docs and screenshots use Starter demo only (no Enterprise DC dataset required)

### Removed

- Bundled **AG Grid Community** vendor CSS/JS and grid-specific templates (`rulebook_ag_*`,
  `rulebook_rules_grid_*`, All Rules AG Grid view/API)
- Matrix / All Rules REST grid APIs (`matrix_grid_api`, `all_rules_grid_api`, …)

### Fixed

- Parent rulebook dropdown could still offer the current rulebook (and descendants) in search results
- Rules cell expand (`+N more`) did not remove `nsm-pill-hidden` after click
- TypeConfig *All types* panel badge had poor contrast in NetBox dark mode

### Migration

- **Squashed** migrations `0002`–`0005` into a single `0001_initial` (current schema only —
  no legacy `panel_linkable` or incremental data migrations).
- Existing dev/test databases that already applied old migrations:  
  `python manage.py migrate netbox_nsm zero` then `migrate netbox_nsm`  
  (**drops all NSM plugin tables**; re-run Setup wizard / Starter demo).

### Notes

- **Breaking for bookmarks:** Rules/Matrix URLs and query parameters changed; deep links using
  old AG Grid view state may need updating. See [Rules grid](docs/using_netbox_nsm.md#rules-grid)
  and [Zone matrix](docs/using_netbox_nsm.md#zone-matrix).
- Requires NetBox **4.5+** (tested through **4.6.x**).

## [0.2.6] - 2026-06-07

_Superseded by [0.3.0](#030---2026-06-07) — bench script and doc items rolled into 0.3.0._

### Added

- Bench script `scripts/create_addresses_million_scale.py` (see 0.3.0).

## [0.2.5] - 2026-06-06

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

## [0.2.4](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.4) - 2026-06-06

### Handling problem

## [0.2.3](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.3) - 2026-06-06

### Changed

- COT: Changed shema nsm_portable_schema.json

## [0.2.2](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.2) - 2026-06-06

### Changed

- COT: Change nsm_portable_schema.json

## [0.2.1](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.1) - 2026-06-06

### Changed

- COT: Changed nsm_portable_schema.json

## [0.2.1](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.1) - 2026-06-06

### Added

- COT: change nsm_portable_schema.json

## [0.2.1](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.1) - 2026-06-05

### Changed

- Portable schema (`nsm_portable_schema.json`): remove field-level `group_name` UI
groups from all built-in custom object types
- Remove `display_template` fields from `nsm_labels` and `nsm_zones` in the portable
schema; display templates remain in TypeConfig metadata applied by Setup
- Normalize `nsm_addresses` field weights (`range` 11, `prefix` 12, `group` 13) and
`nsm_labels.custom_type` weight (11) for consistent form ordering

### Notes

- Re-run Setup → Custom Objects (schema apply) to sync existing NetBox instances

## [0.2.0](https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.0) - 2025-06-06

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
[0.4.0]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.0
[0.3.2]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.3.2
[0.3.1]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.3.1
[0.3.0]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.3.0
[0.2.5]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.2.5
[0.4.1]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.1
