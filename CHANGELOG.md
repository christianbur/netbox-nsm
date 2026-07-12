# Changelog

All notable changes to **netbox-nsm** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.23] - 2026-07-12

### Added

- **IP Analyzer Cell-Tree — Tenant column** — new **Tenant** column (after **Type**) displays IPAM object tenant with link; shows "—" if no tenant assigned.
- **IP Analyzer Cell-Tree — Zone/Label source info** — Zone and Label cells now display source info in tooltips. Zones show all inherited zones from parent-prefix chain with prefix context; Labels show which direct object (host/interface) has the label.
- **IP Analyzer Cell-Tree — Subnet lazy-load expansion** — subnet children now load on-demand via "+" button in Network column (requires parent prefix with child subnets).

### Changed

- **IP Analyzer Cell-Tree — dynamic column widths** — table layout switched from `table-layout: fixed` to `table-layout: auto` for content-responsive width. All columns use `min-width` only (no fixed width), enabling table to expand/contract based on cell content.
- **IP Analyzer Cell-Tree — column reorganization** — **Duplicate** moved to position 2 (after Network), **Type** to position 3, **Tenant** to position 4 (new). Full order: Network | Duplicate | Type | Tenant | Address | Address group | IPAM | DNS | Description | Zone | Label | Merge | Diff | Used by.
- **IP Analyzer Cell-Tree — Type+CIDR combination** — Type column now displays Type label and CIDR/IP pill inline using flexbox, removing separate display in Network column.

### Fixed

- IP Analyzer Cell-Tree renders all zones from ancestor prefix chain (not just first), enabling multi-tenant/multi-zone networks.

## [0.4.22] - 2026-07-12

### Added

- IP Analyzer export now respects current view state (including already opened lazy drilldowns) via view-only snapshot refs.

### Changed

- YAML export bypasses payload cache to reflect live UI state reliably.
- Applet export query now carries expanded lazy object refs.

### Fixed

- HTTP 504 analyzer failures now show collapsible debug details in the applet error view.
- Used-by evaluation remains restricted to direct IPAddress objects in cell context.

## [0.4.21] - 2026-07-12

### Changed

- IP Analyzer intern refactored: Netzwerk-Identitaet in ipa_network_identity.py und Merge/Collapse-Orchestrierung in ipa_cell_merge.py ausgelagert (verhaltensstabil).

### Fixed

- IP Analyzer: Host-Merge nutzt konsequent Python-ipaddress-Normalisierung (IP/Prefix/Range) und verhindert falsche DUP/MERGE-Marker bei Prefix-only-Hinweisen.

## [0.4.20] - 2026-07-12

### Fixed

- IP Analyzer: Gleiche Host-IP wird jetzt strikt anhand der IPAM-IP zusammengefuehrt (auch bei FQDN/Domain-Labels), sodass mehrere Address-Objekte in einer IP-Zeile landen.

## [0.4.19] - 2026-07-12

### Notes

- Release

## [0.4.18] - 2026-07-12

### Notes

- Release

## [0.4.18] - unreleased

## [0.4.17] - 2026-07-09

### Added

- **IP Analyzer — Zone / Label columns** — flat cell-tree table adds **Zone** and **Label** after **Description** (12 columns total). Zone shows direct `nsm_object_link` refs or inherits from parent prefixes; labels are direct links only. Backend: `ipa_zone_label.py`, `ipa_cell_tree_zone_cell.html`, `ipa_cell_tree_label_cell.html`. Asset cache bump.
- **Type metadata — `rule_view` in bundle** — `metadata.types` in `nsm_schema.json` now carries `rule_view` (incl. `nsm_address_custom`); `sync_metadata()` writes it into COT `comments` alongside `role` and `menu`.
- **Bundle generator — canonical metadata maps** — `BUNDLE_ROLE_BY_SLUG`, `BUNDLE_MENU_BY_ROLE`, `BUNDLE_SORT_ORDER_BY_SLUG` in `generate_schema_bundles.py`; service display template supports port ranges.

### Changed

- **Type metadata — bundle/comments only** — removed Python runtime fallbacks (`DEFAULT_ROLE_BY_SLUG`, `TYPECONFIG_SPECS`, `DEFAULT_MENU_BY_ROLE`, `sync_cot_display_templates_from_specs()`). Resolvers read instance metadata exclusively from COT `comments` / bundle apply (`config.py`, `dispatch.py`, `roles.py`, `menus.py`, `specs.py`).
- **IP Analyzer — Dup column position** — **Dup** moved to column 2 (directly after **Network**).
- **NSM object menu labels** — navigation uses COT `verbose_name_plural` instead of removed `TYPECONFIG_SPEC_BY_SLUG` labels.
- **Rules layout sort order** — column sort uses `resolve_nsm_config_for_cot().sort_order` instead of slug-based Python defaults.
- **Docs** — `using_netbox_nsm.md` notes `rule_view` in schema bundle sync.

### Fixed

- **Type metadata tests** — updated for comment-only resolver and bundle-sourced defaults.

## [0.4.16] - 2026-07-08

### Added

- **Rules table — dynamic field columns** — non-multiobject COT scalar fields render as `kind: field` columns automatically when new fields are added to the rulebook type.
- **Rules table — Configure Table** — NetBox-style column visibility dropdown with `localStorage` persistence (`rulebook_rules_columns.js`).
- **Rules table — NetBox object-list controls** — Add, Import, and Export via `custom_object_*` buttons in page controls; Bulk Edit and Bulk Delete below the table via CO bulk button tags.

### Changed

- **Rules table — button layout** — aligned with NetBox `object_list`: primary actions in header controls, rule count + display options + Configure Table in the table-controls row, bulk actions in sticky footer on selection.
- **Rules table — display options** — Grouped columns, cell mode, and Export JSON moved from the in-card chrome bar to the centered table-controls row (before Configure Table).
- **Rules table — status column** — enabled/disabled shown as green checkmark / red X (NetBox `checkmark.html` style) instead of On/Off text badges.

### Fixed

- **Rules table — Configure Table menu** — checkbox rows no longer clipped to thin bars (flex layout, zero negative margin, improved contrast).

### Removed

- **Rules table — sticky chrome bulk actions** — `rulebook_rules_sticky_actions.html` replaced by footer bulk-action bar.

## [0.4.15] - 2026-07-08

### Removed

- **Object links — rulebook/enforcement types** — removed `link_type` and `rulebook_slug` COT fields, rulebook/enforcement_point link storage, assigned-objects UI on rulebook detail, bulk-assign views, and Security Panel enforcement-point / Rulebooks section. Policy-only object links remain the sole Security Panel assignment mechanism.

### Added

- **Object link config** — Security → Configuration → Object Links UI to view and edit Object A/B polymorphic type allow-lists (preview, destructive-change guard, apply).
- **`nsm_address_custom` — ANY** — built-in custom address type for universal IPv4 match (`0.0.0.0/0`); seeded in NSM schema and demo bundle.
- **Security tab eligibility** — tab and badge shown only for content types listed on deployed `nsm_object_link` endpoints.
- **Security tab — type-metadata filter** — combined-tab CO reference rows limited to link-table COTs and COTs with `nsm_config` metadata.
- **Service display template sync** — bundle apply syncs canonical service display template (incl. port ranges) into COT comments via `sync_cot_display_templates_from_specs()`.
- **Field migration** — `policy_object` → `security_object` rename on deployed link-table COT (idempotent startup helper).

### Changed

- **`nsm_object_link` schema** — Object B field renamed to `security_object`; polymorphic allow-lists trimmed to policy types only.
- **Object link assign URL** — Security tab uses shared `object_link_assign_url()` helper.

### Fixed

- **Object link config apply** — updates `related_object_types` M2M in-place instead of full portable-schema apply (avoids FieldError when `schema_id` was never backfilled, e.g. legacy `security_object` column).
- **IP Analyzer — custom ANY nesting** — `_renest_ipa_contained_cell_siblings()` restores depth consistency when ANY or subnet cells share a parent; subnet containment warnings on child rows.

## [0.4.13] - 2026-07-06

### Fixed

- **Security tab YAML crash** — linked address instances with free-text comments (e.g. Tufin metadata) no longer crash the IPAM prefix Security tab; `address_literal._load_yaml_document()` catches `yaml.YAMLError` instead of raising.
- **`nsm_config` YAML scope** — runtime parsing is limited to `CustomObjectType.comments`; COT instances and IPAM objects (prefix, IP, range) are never parsed as `nsm_config` (`_comments_may_contain_nsm_config`, guards on `resolve_menu_for_cot`, `resolve_rulebook_config_for_cot`, `parse_role_from_comments`, `parse_menu_from_comments`).

### Added

- **Tests** — `test_security_tab_yaml.py` (prefix Security tab + Tufin address comments); extended `test_nsm_config` and `test_address_literal` for invalid YAML / IPAM guards.

## [0.4.12] - 2026-07-05

### Added

- **IP Analyzer — DNS / Description column** — flat cell-tree table adds a ninth column after **IP/Range/Prefix** showing NetBox IPAM metadata: IP addresses show `dns_name` and `description`; prefixes and IP ranges show `description` only. **IP/Range/Prefix** stays counter-only (`0/0/0` badges). Backend: `_ipa_ipam_object_display_ref()`, `_attach_ipa_cell_ipam_object_refs()`, template `ipa_cell_tree_ipam_desc_cell.html`. Asset cache bump (`?v=202607053`).
- **Special IPAM CSV import** — `bundles/import_csv/special_prefixes.csv` (46 IANA/IETF special-use prefixes) and `special_ip_addresses.csv` (13 special host addresses) for NetBox IPAM bulk import with descriptions.

### Changed

- **NSM Schema bundle — nested address/service groups** — `nsm_address_group.group` and `nsm_service_group.group` are polymorphic multiobject fields (nested groups, custom addresses, etc.); descriptions updated in `nsm_schema.json`.
- **Demo IPAM seed** — `seed_demo_address_ipam()` sets `description` on linked prefixes and `dns_name` + `description` on linked host IPs so IPA demo rows are not empty.

### Fixed

- **IP Analyzer — IPAM metadata resolution** — host rows resolve `IPAddress` via `prefix_display_cidr` and NSM IPAM FK (`obj_by_key`); NSM `description` fills in when IPAM `description` is empty.

## [0.4.11] - 2026-07-05

### Added

- **Security tab links** — TYP column links to filtered rulebook lists or rulebook URLs; WERT values link via `get_absolute_url()` (`value_items` in row payload).
- **Rules row-group sidebar** — human-readable group labels from rulebook column metadata (not raw `nsm_rb_*` slugs); cache key `:v2` with tab-summary refresh after cache hit.

### Changed

- **`nsm_config` parsing API** — runtime paths use `parse_nsm_config_from_cot()` / `parse_nsm_config_document_from_cot()` on `CustomObjectType` only; `_parse_nsm_config_yaml()` remains internal for bundle setup/sync.
- **Security tab table** — wider TYP/WERT/Object columns with wrap; localized COT type labels; unified edit split-button + dropdown actions; full field values (no truncation).
- **Display labels** — `type_config_display_name()` no longer title-cases IPAM labels (`IP addresses` / `IP-Adressen`).
- **Docs** — README plugin version, REST API table, migration chain note in `DATABASE.md`.

### Fixed

- **Security tab YAML crash** — invalid or free-text COT **instance** comments (e.g. Tufin metadata) are never parsed as `nsm_config`; guards on `resolve_nsm_config_dict_for_cot`, `cot_link_table_flag`, and `object_builder_in_nsm_config`.
- **Invalid YAML in type comments** — `_load_yaml_document()` catches `yaml.YAMLError` and returns `None` instead of raising on the Security tab.

## [0.4.10] - 2026-07-02

### Added

- **`bundles/builtin/*.json` in PyPI wheel** — built-in schema/demo bundles are packaged again (`pyproject.toml`); new `test_bundle_discovery.py`.
- **PLUGINS_CONFIG documentation** — `bundle_paths`, `builtin_bundles`, and full key table in `docs/using_netbox_nsm.md`.

### Changed

- **Docs / locale / API** — Bundles and Type Metadata replace legacy Setup wizard / Object Config wording; removed dead config keys from examples.

### Fixed

- **`link_table` metadata on bundle apply** — `sync_metadata()` now writes `link_table: true` into COT `comments` when netbox-custom-objects has no native `link_table` field (0.5.x). Fixes `RuntimeError: link-table COT is not deployed` on Security Panel **Assign**.
- **Link-table discovery fallback** — `get_object_link_cot()` resolves deployed `nsm_object_link` by slug/field topology when comments lack the flag.
- **Assign UX** — missing link-table shows a redirect + message instead of HTTP 500.

### Removed

- **Link type / propagation** — removed `propagation` from `nsm_object_link` bundle schema, Assign/Edit UI, REST API, and link service; new links are always direct. Re-apply **nsm_schema** bundle to drop the field from deployed COTs.

## [0.4.9] - 2026-07-02

### Added

- **Rules export JSON** — the Rules tab **Export JSON** button downloads filtered rules as a bundle-compatible document (`objects[].records[]` with portable refs like `nsm_zone/zone_01`). Import via **Security → Configuration → Bundles**.
- **`format_portable_ref()`** — shared helper for portable object references in bundle export/import.

### Changed

- **README** — updated for v0.4.9 UI (Bundles, Type Metadata, Object Report, Export JSON) and refreshed screenshots.
- **Grouped columns toggle** — button active state matches grouped (`collapsed`) vs per-type (`expanded`) column layout.
- **Rules row-group performance** — lightweight tab-summary scan (`include_links=False`), queryset pagination for the visible page, cached `parse_menu_from_comments`, direct NSM object URLs in rule rows.
- **Plugin startup** — warm Django URL resolver in `SecurityConfig.ready()` to avoid a multi-second penalty on the first `reverse()` per worker.
- **Assigned objects panel** — bulk interface prefetch per host type; early return before `reverse()` when the panel is empty.

### Fixed

- **Expanded column mode** — polymorphic object types render in separate columns (e.g. Address / Address Custom / Address Group) instead of a single merged column.
- **Rulebook detail** — faster enforcement-targets panel on COT object pages.

## [0.4.8] - 2026-07-01

### Changed

- **IP Analyzer naming** — URLs, url_names, modules, views, templates, JS constants, and JSON payload keys use `ip_analyzer` / `addr_analyzer` instead of `ip_analysis` / `addr_analysis` (e.g. `/api/ip-analyzer/`, `ip_analyzer_api`). Legacy plugin UI path `/plugins/netbox-nsm/ip-analysis/` remains 404.
- **Modular architecture (phases A–E)** — bundle discovery without `REQUIRED_COT_SLUGS` gating; rulebook matrix helpers under `rulebooks/matrix/`; object-link propagation under `security/links/`; legacy import shims removed after package moves.
- **Type metadata** — drop `nsm_config.links` bundle blocks and UI/API fields (`linkable`, `inherit_links`, `inherit_stop_on_own`, `allow_virtual_groups`); linkability follows registered NSM type config instead.

### Removed

- **netbox-custom-objects PR #602 patch tooling** — local `patch/apply_pr602.py` and v0.5.2 runtime patch removed from the plugin repo.
- **Legacy packages** — unused top-level modules (`ui/`, `models/`, `graphql/`, `bench/`, and related shims) after layout consolidation.

### Fixed

- **Rulebooks list** — restore split edit/delete button helper at `netbox_nsm.core.split_actions` after `ui/` removal (`ModuleNotFoundError: netbox_nsm.ui`).

## [Unreleased]

## 0.4.7 - 2026-06-19

### Removed

- **IP Analyzer — IPAM filler rows removed from flat cell tree** — IPAM hierarchy filler/synthetic prefix rows (e.g. `10.128.0.0/20` between a cell-selected `/24` and its NetBox parent) no longer appear as table rows in the IPA cell-tree object list. They remain in the backend tree for parent/containment hints (`_mark_ipa_cell_tree_parent_hints`, `subnet_contained_in`) and still render grey in legacy nested `addr_tree_node.html` drilldown markup. Flat render skips them via `ipa_cell_tree_row.html` / `ipa_object_tree_node.html`; visible depth does not increment through skipped fillers (`_annotate_ipa_cell_tree_depth`). Asset cache bump.

- **IP Analyzer standalone page** — the two-column compare UI at `/plugins/netbox-nsm/ip-analyzer/` (`IPAnalysisView`, `ip_analysis.html`, `ipa_object_analysis_table.html`) is removed. IP address resolution now lives only in the **IP Analyzer applet** on rule detail pages and via the analysis APIs. The old URL permanently redirects to **Object Analyzer**; legacy `ip_ct` / `ip_pk` / `ip_name` query params pre-select the first object when present. Unused `nsm_ip_analysis_url` context from the Security tab is dropped.

### Changed

- **IP Analyzer — cell tree drops the Parent column** — the flat cell object table now renders **eight** columns (**Network**, **IP/Range/Prefix**, **Dup**, **Address**, **Address group**, **Merge**, **Diff**, **Used by**); the standalone **Parent** column is removed (parent/containment hints stay in the **Dup** column and tooltips). The depth-toggle row spans `colspan="8"` and the **Used by** column is widened (`--us` ≈ `18rem`). Internal keys/CSS (`--us`, `nsm-ipa-cell-tree-header-col--us`) are unchanged. Asset cache bump.
- **IP Analyzer — "Us" column renamed to "Used by"** — the rightmost usage column header now reads **Used by** (DE: *Verwendet von*); the diff "fund"/"Fund" badge is presented as a clear **Name conflict** label (DE: *Namenskonflikt*). Internal keys (`diff_fund`, `fund_count`, `fund_tooltip`) and CSS class names are intentionally kept.
- **IP Analyzer — IPAM counter counts unique IPs** — the IPAM/leaf counter de-duplicates IPAM IP references so the same IPAM IP is no longer counted twice across merged objects/groups.
- **IP Analyzer — Diff rollup and tab-named diff column** — the IPAM tree now rolls IPAM children up under their containing prefixes, and the **Diff** column labels each side with its source tab name (e.g. `Rule 1/5`).
- **IP Analyzer — Merge appends a new tab** — running **Merge** now creates a new merged tab and keeps the existing tabs instead of replacing them (`mergeTabs`, `this.tabs.push(mergedTab)`).
- **IP Analyzer — YAML export v2** — the applet YAML export emits `ipa_export_version: "2"` with a primary `displayed` section (the visible tree, counts, `copy_lines`, `addr_analysis`, `object_tree`) plus an optional `ipam_children` section; the trigger tooltip reads *Export displayed data and IPAM children (YAML)*.
- **Rulebook rules table — export is JSON, not TOML** — the Rules tab **Export JSON** button downloads bundle-compatible JSON (`objects[].records[]`, portable refs). Import via **Security → Configuration → Bundles**. The previous visible-rules TOML export is removed.
- **IP Analyzer — Explain tooltips, group coverage, and summary v2** — flat cell-tree rows now carry an Explain tooltip on the **Network** cell (`direct in rule cell`, `group member`, `contained by`, alias/duplicate names, diff status/presence, non-active status). The All summary includes coverage-oriented counters (**Groups**, **Addresses**, **Merged**, **Non-active**, **Direct/Indirect**) in addition to Subnets/Ranges/IPs/Warnings. A collapsible **Group coverage** panel lists every directly selected address group and whether it is visible as its own row, merged into a member row, or missing. Summary subnet/range/IP counts use the visible group anchor CIDRs as well as address rows, so bench-scale groups like `bench-grp-00001` contribute to the current table counts instead of collapsing the summary to `1/0/1`. Asset cache bump.

- **IP Analyzer — cell tree Network column containment color** — flat cell-tree rows with `subnet_contained_in` (e.g. `10.128.0.0/24` nested under `10.128.0.0/16`) no longer render orange CIDR text or `nsm-ipa-subnet-contained` in the **Network** column. Cell-direct network links stay teal; indirect rows stay grey. Subnet containment warnings remain in the **Dup** column (`dup` badge + tooltip) and **Address** (`cell_addresses_multi` orange links only). Row class `nsm-ipa-object-node--subnet-warning` is kept for legacy drilldown markup; flat cell-tree orange CIDR styling is scoped to non-table drilldown nodes. Asset cache bump.

- **IP Analyzer — cell tree Dup column parent containment** — depth-nested cell-direct rows under a prefix in the IPAM tree (e.g. `bench-ip-0000000` depth 2 under `bench-net-00000` on `bench-rule-00001`, with `bench-grp-00000` in **Address group**) now receive `subnet_contained_in` and the `dup` badge when their host CIDR was only on `ip_ref` with NSM type label `Address` (not `IP Address`): `_addr_node_prefix_cidr` resolves `/32` host refs for both labels so `_mark_ipa_subnet_containment_warnings` can run. Collapsed address groups nested under a cell-selected prefix with the **same** `/24` CIDR are also marked redundant via `_ipa_subnet_containment_ancestor_match`. Root-level-only groups (e.g. `bench-grp-00346` without a wider prefix in the cell) stay without `dup`. Asset cache bump.

- **IP Analyzer — cell tree Dup column multi-address overlap** — rows where several NSM address names share the same network (`cell_addresses_multi`, e.g. bench overlap `bench-ip-*` + `bench-dup-*` + `bench-alias-*` peers) now show the compact `dup` badge in the **Dup** column (tooltip: “Multiple address names share this network in the rule cell”). Orange multi-name links stay in **Address** only; **Merge** keeps its separate `merge` badge. Toolbar **Warnings** count (`_count_ipa_object_tree_duplicates`) includes `cell_addresses_multi` and `count_duplicate` alongside existing overlap signals (`subnet_contained_in`, `is_doppelt`, `object_duplicate`). Asset cache bump.

- **IP Analyzer — cell tree Address column tooltips** — address links in the flat cell-tree **Address** column now expose a native `title` tooltip (same pattern as **Parent**, **Dup**, multi-address warning): NSM address name plus network/CIDR when `prefix_display_cidr` is available; non-active status (`deprecated`, `reserved`) appended; collapsed group rows show anchor context (`Anchor address … for group …`); indirect rows (not `in_cell` / `is_cell_direct`) append `| Indirect (not directly in rule cell)`. Multi-address wrapper tooltip unchanged. Built via `ipa_cell_tree_address_link_title` template tag. `cursor: help` on address links. Asset cache bump.

- **IP Analyzer — Parent column standard link colors** — the flat cell-tree **Parent** column (`ipa_subnet_containment_meta.html` → `nsm-ipa-cell-parent-hint`) no longer uses orange `text-warning` styling. Parent prefix/CIDR links use the same teal NetBox link treatment as **Network** (`nsm-ipa-cell-cidr-link`); indirect rows stay grey via `cell-indirect` CSS. Subnet containment warnings remain in the **Dup** column only (`subnet_contained_in` → dup badge). Asset cache bump.

- **IP Analyzer — Diff/Merge flat cell-tree table** — Diff and Merge modes now render the same nine-column flat `object-list` table as single-column cell selection (**Network**, **IP/Range/Prefix**, **Dup**, **Address**, **Address group**, **Parent**, **Merge**, **Diff**, **Us**). Diff groups (`only-a`, `only-b`, `in-some`, `both` / `in-all`) become table blocks with `nsm-addr-diff-group--*` row backgrounds; diff badges, fund markers, and `diff_present_labels` live in the **Diff** column (and fund rows in **Address**). Backend: `_build_ipa_cell_object_tree_from_diff` converts diff `addr_analysis` groups into `object_tree` nodes; `build_ip_analyzer_payload` builds `object_tree` for `mode=diff` as well as merge. Legacy nested `addr_tree_node.html` / `addr_intersection_flat_node.html` markup is no longer used when `object_tree` is present. Asset cache bump.

- **IP Analyzer — cell tree Dup column non-active status** — the **Dup** column now shows compact status badges (`deprecated`, `reserved`) in addition to `dup` overlap badges when any NSM object on the row (row object, `cell_address_primary`, `cell_addresses`, or `cell_groups` refs) has a non-active status. Statuses are collected in `_attach_ipa_dup_cell_statuses` after `_attach_ipa_object_tree_status` (no extra DB queries). Toolbar **Warnings** count excludes deprecated/reserved-only rows; overlap signals are `subnet_contained_in`, `cell_addresses_multi`, `is_doppelt`, `object_duplicate`, and `count_duplicate`. Asset cache bump.

- **IP Analyzer — cell tree IP/Range/Prefix CIDR lookup** — prefix/range rows that only had `prefix_display_cidr` (no NSM FK, e.g. depth-1 `subnet-warning` rows like `10.128.228.0/24`) showed `—` in **IP/Range/Prefix** because `_lookup_ipam_prefix_for_cidr` passed Python `ipaddress.IPv4Network` into NetBox’s `IPNetworkField` (expects `netaddr.IPNetwork`). **Fix:** use `netaddr.IPNetwork` for exact CIDR lookup; `_resolve_ipa_drilldown_meta_for_node` also tries name-derived CIDR hints. Asset cache bump.

- **IP Analyzer — cell tree Address column for group members** — collapsed address-group rows (`cell_pill_group`, e.g. `bench-grp-*` on `bench-rule-00001`) that show a member subnet CIDR in **Network** now also render the anchor member’s NSM address name/link in **Address** via `_attach_ipa_cell_address_fields` / `cell_group_anchor_address` (same subnet pick as `_enrich_ipa_collapsed_group_networks_from_members`; distinct from alias compact `cell_address_primary`). Pure group rows without a resolvable member address still show an em dash; group membership stays in **Address group**. Expanded group members with `cell_groups` use the address-link path even when not cell-direct. Asset cache bump.

- **IP Analyzer — cell tree Network / IPAM / warning consistency** — **Network** column links every row with an NSM object (`node.url`) or IPAM ref (`ip_ref.url`), including cell-direct prefixes that previously showed plain CIDR text when `ip_ref` was missing (`ipa_cell_tree_network_cell.html`, `_ensure_ipa_cell_tree_network_links`). **IP/Range/Prefix** counters attach to all prefix/range rows (not only `is_cell_direct`) via `_attach_ipa_drilldown_meta` + IPAM CIDR fallback. **Orange** row styling (`subnet-warning`) applies only for subnet containment (`subnet_contained_in`); multi-address/group warnings stay orange in **Address** / **Address group** columns only. Cell-direct network text stays teal unless containment warns. Asset cache bump.

- **IP Analyzer — cell tree direct vs indirect styling** — flat cell-tree rows that are **not** directly selected in the rule cell (`in_cell` / `is_cell_direct`) render muted/grey across all columns (`nsm-ipa-object-node--cell-indirect`: secondary text, grey CIDR/links, dimmed depth markers •). Cell-direct rows keep teal NetBox links and orange multi-address/group warnings; **Dup** badges and doppelt (red) links stay visible on indirect rows. IPAM filler/synthetic/parent-prefix and drilldown/expanded group members are indirect. Asset cache bump.

- **IP Analyzer — cell tree Dup column order** — **Dup** moved from near the right edge (before **Us**) to position 3, directly after **IP/Range/Prefix**: **Network**, **IP/Range/Prefix**, **Dup**, **Address**, **Address group**, **Parent**, **Merge**, **Diff**, **Us**. The narrow warning column stays visible without horizontal scroll in typical applet widths. Asset cache bump.

- **IP Analyzer — cell tree Address column (multi-name)** — when several NSM address names share the same network (`cell_addresses_multi`), the **Address** column lists every name as a separate link stacked vertically (flex column) instead of a primary name plus `+N aliases` expand hint. Links use orange warning styling (`nsm-ipa-cell-tree-address--multi`); tooltip: “Multiple address names share this network in the rule cell”. Compact alias hints remain for legacy drilldown / **Cell object** pills only. Asset cache bump.

- **IP Analyzer — cell tree Merge/Diff columns** — the flat cell object table now has nine columns: **Network**, **IP/Range/Prefix**, **Address**, **Address group**, **Parent**, **Merge** (compact `merge` badge or `+N` alias count when multiple address names share a network via `_merge_ipa_cell_nodes_by_network` / `cell_addresses_multi`), **Diff** (compact diff status badges — `a` / `b` / `both` / `all` / `some` / `fund` plus multiline `diff_present_labels` — moved out of **Us**), **Dup**, and **Us**. Row classes (`nsm-addr-diff-group--*`, `nsm-addr-diff-leaf--*`) are unchanged for background/border styling; address column still renders diff name pills and fund rows. Asset cache bump.

- **IP Analyzer — cell tree Dup column** — the flat cell object table now has seven columns: **Network**, **IP/Range/Prefix**, **Address**, **Address group**, **Parent** (containment CIDR link), **Dup** (compact `dup` warning badge when the row is redundant: `subnet_contained_in` — network already covered by a parent prefix in the same cell tree — and/or `is_doppelt`, `object_duplicate`, `count_duplicate`), and **Us** (IPAM gap summaries and leaf-count preview only; duplicate badges moved out of **Us**). Toolbar **Warnings** / duplicate counts unchanged (`_count_ipa_object_tree_duplicates`). Asset cache bump.

- **IP Analyzer — cell tree IP/Range/Prefix column** — the flat cell object table now has six columns: **Network**, **IP/Range/Prefix** (NetBox child counters: compact `prefixes/ranges/IPs` badge from existing `ipam_stats` / `ipa_drilldown_meta`, tooltip with full labels), **Address**, **Address group**, **Parent** (containment link — kept; not redundant with Network which shows the row’s own CIDR/IP), and **Us** (IPAM gap summaries, duplicate/warning badges, leaf-count preview — IPAM short stats moved out of **Us**). No new DB queries; reuses `_attach_ipam_stats_meta`, `_build_ipa_drilldown_source_meta`, and `addr_ipam_stats.html`.

- **IP Analyzer — cell tree column content split** — alias/dup peer names (`+N aliases`, `bench-dup-*`, `bench-ip-*` links) render in the **Address** column (primary name + expandable peer links with line breaks), not in **Us**. **Us** keeps IPAM gap summaries (`[99 used / 155 unused ip]`) and warning badges only (`dup`, `duplicate`, IPAM duplicate counts) — no peer object names and no IPAM short stats (those moved to **IP/Range/Prefix**). **Parent** and **Address group** stay limited to parent prefix and group memberships respectively.

- **IP Analyzer — cell tree dedicated columns** — the flat cell object table now uses five data columns instead of the mixed **Cell object** / **Groups** / **Info** layout: **Network** (CIDR/IP + depth markers), **Address** (NSM address name/link only; em dash when the row is not an address object), **Address group** (address-group object link for group rows plus comma-separated membership links), **Parent** (orange `subnet_contained_in` prefix/CIDR link), and **Us** (usage/warning column: IPAM gap summaries such as `[99 used / 155 unused ip]`, duplicate/warning badges, and IPAM short stats). Row data is split per column; NetBox `object-list` link styling is unchanged (no pills).

- **IP Analyzer — cell tree columns without pills** — the flat cell object table (**Network** / **Cell object** / **Groups** / **Info**) no longer renders ADDRESS / ADDRESS_GROUP pills in the object column. **Cell object** shows the NSM object as a plain `nsm-addr-obj-link` with a muted type label (`address` / `address group`); **Groups** lists comma-separated group links (collapsed memberships stay as a `N groups` `<details>` summary). Parent containment (`subnet_contained_in`) is shown in **Info** as the orange **Parent** pill (`nsm-ipa-cell-pill--parent` via `ipa_subnet_containment_meta.html`), together with alias/dup hints and warning badges. Legacy drilldown / diff rows that still use `addr_tree_node.html` keep pill styling where applicable.

- **IP Analyzer — cell object tree layout** — the cell object tree now renders as a flat NetBox-style `table table-hover object-list` (one row per prefix/range/IP/group node) instead of a nested `<details>` hierarchy with border lines. Hierarchy depth uses NetBox **`record-depth`** bullet markers (•) in the **Network** column, with an optional **Hide Depth Indicators** toggle (`toggle-depth`, same behaviour as IPAM Prefixes). Expand/collapse remains only for lazy IPAM drilldown rows and optional collapsed root-group summaries; fully merged trees are flat. Columns **Network**, **Cell object**, **Groups**, and **Info** are unchanged. Light/dark styling follows NetBox `object-list` and existing IPA CSS variables.

- **IP Analyzer — per-row INFO stats removed** — cell object summary rows no longer render the INFO badge line (object name, tenant, Subnets/Ranges/Client IPs counts) beneath CIDR and pills. Toolbar aggregate stats (Subnets/Ranges/IPs/Warnings) are unchanged; prefix/range drilldown expand behaviour is unchanged.

- **IP Analyzer — Interface/Host pill removed** — grey assignment pill (`Interface: … · VM/Device: …`) on IPAM leaf nodes (`/32`) is no longer rendered in the cell object tree. Backend lookup (`_ipa_ip_assignment_pill_from_ipam`) and template `ipa_cell_ip_assignment_pill.html` removed; rest of IPA display unchanged.
- **IP Analyzer — CIDR parent hint removed** — the muted inline `⊂ parent-prefix` link next to the cell CIDR (replacing the orange PARENT pill in the UX refresh) is removed. Parent containment is shown again via the orange **Parent** pill (`ipa_subnet_containment_meta.html`); backend `cell_cidr_parent_hint` / `cell_parent_hint_compact` display hints dropped.

### Added

- **Object Analyzer — view modes (All / Security)** — the Object Analyzer form (`#nsm-oa-form`) adds a segmented **All** / **Security** control (Bootstrap `btn-group` + `btn-check`, same pattern as the Rules tab cell-mode selector). The selected mode is passed as `mode=all|security` on page load and on every analyzer API call (`/api/analyzer/`, `/api/analyzer/picker/`). Server-side filtering lives in `analyzer/modes.py` (`filter_edges_for_mode`, `get_filtered_edges`) and is applied in `picker.build_picker_tree` and `AnalyzerAPIView`. **Security** shows only NSM objects (address, address group, object link, and other NSM COT types), IPAM (prefix, IP, IP range), interfaces, and hosts (device, VM); labels, zones, rules, cable/console ports, and other infrastructure categories are hidden. Each mode has its own search placeholder, compact in-card legend, empty-state copy, and (for Security) a short hint describing what is included/excluded. Mode persists via URL query param (shareable) with `localStorage` (`nsm_oa_mode`) as fallback when the URL omits `mode`; switching the segment reloads the page immediately.
- **Address / address-group name templates** — configure Jinja2 naming globally via `PLUGINS_CONFIG['netbox_nsm']['address_name_templates']` and `address_group_name_templates`. Short syntax `{ipam>ip}` maps to `{{ ipam.ip }}`; native Jinja2 is supported. First matching template per IPAM / group kind wins; COT `object_builder.build_template` remains the fallback. Central helpers: `render_ipam_object_name`, `render_address_name`, `render_address_group_name` (`netbox_nsm/objects/address_name_templates.py`). See [docs/address_name_templates.md](docs/address_name_templates.md).
- **Daily Object Report** — a background job builds an aggregated report of `nsm_address` / `nsm_address_group` objects once per day, viewable and manually startable under **NSM → Configuration → Object Report**.
  - **Job mechanism** — `ObjectReportJob` (`netbox_nsm/object_report/jobs.py`) is a NetBox `JobRunner` registered with `@system_job(interval=JobIntervalChoices.INTERVAL_DAILY)`. NetBox's `rqworker` schedules it idempotently at startup (`enqueue_once`) and re-schedules after each run via the interval. Manual runs use `ObjectReportJob.enqueue()`.
  - **Persistence** — the aggregated report is stored on the run's `Job.data` (JSONField); the viewer reads the latest completed job (no recomputation, no extra model/migration). Retention follows NetBox `Job` housekeeping.
  - **Checks** — (a) NSM address `status` vs the status mapped from its linked IPAM object (Object Builder `status_map`), (b) `ipam_duplicates`: multiple address objects pointing at the same IPAM resource, (c) `ipam_orphans`: NSM addresses with no IPAM reference at all (intentional literal-network objects excluded, reported as `literal_skipped`), (d) `multi_group`: addresses that are members of more than one group, (e) `empty_groups`: address groups with no members, (f) `single_member_groups`: groups wrapping exactly one member, (g) `similar_groups`: groups with overlapping membership (duplicate/redundancy detection), (h) `deprecated` objects. The `ipam_duplicates`, `multi_group`, and `similar_groups` checks were optimized to pure through-table/DB aggregation (no per-object scans).
  - **Export (TOML)** — the Checks card has an **Export TOML** button (`?export=toml` on the report view) that streams the full last run as a structured TOML document (`format = "netbox-nsm-object-report-v1"`, MIME `application/toml`, `nsm_object_report_<timestamp>.toml`). Server-side from `Job.data` (no DOM scrape), enforcing the same `VIEW_CUSTOM_OBJECT_TYPE` permission; a tiny hand-rolled writer (`object_report/toml_export.py`) avoids a third-party TOML dependency.
  - **Sample pagination** — each check's collapsible sample list is paginated client-side in `SAMPLE_PAGE_SIZE` (50) steps with **Previous / Next** buttons and a `start–end of total` status line (`plugin_assets/js/object_report_samples.js`). The stored sample set stays bounded by `DEFAULT_SAMPLE_LIMIT` (500); when a check exceeds the cap the pager shows `… of <stored> (of <total> total)`.
  - **Scale (> 1,000,000 objects)** — analysis (`netbox_nsm/object_report/object_report.py`) is aggregated, not materialized: duplicate/multi-group checks run as pure DB `annotate`/`Count`, the status check streams the address table with `.iterator()` in chunks resolving IPAM statuses in bounded `pk__in` batches, and every check stores only counts + grouped breakdowns + a capped sample list.
  - **UI** — the last-run timestamp is shown prominently; a **Run now** button enqueues a fresh run (requires an RQ worker). Summary counters render as large pills; all checks appear in one NetBox `object-list` table with expandable sample rows (up to 50 per check).
- **Security tab — NetBox-style linked-objects table** — the Security tab now renders linked objects in a NetBox `object-list` table (sortable **Name** header, `table-hover`, NetBox paginator) instead of a flat list. Linked objects are grouped into **object-type tabs** (e.g. *COT Aktion*, *Prefix*) with per-tab count badges, scaling to large link counts without loading every object into one list. Tab/sort/page state lives in query-string params (`nsm_lt`, `nsm_lv`, `nsm_lp`, `nsm_pp`, `nsm_lo`) so deep links and back/forward work.
- **Security tab — value sub-grouping** — within an object-type tab, objects are further grouped by their **value** (e.g. *Permit* / *Deny* derived via `nsm_object_group_value` in `security/tab/value_groups.py`) and surfaced as filter pills above the table. Pills carry per-value counts and are hidden when a type has no distinguishing value, keeping single-value types uncluttered.
- **Security tab — server-side pagination** — `prepare_link_tab_view` (`security/tab/links.py`) paginates the active tab/value slice with Django's `Paginator` (default + selectable page sizes), so at most one page of rows reaches the browser even with 50k+ linked objects. Expensive per-row payload work (URL reversing, status icons, parent lookups) is deferred to the rows on the active page; counts for tabs/pills use lightweight descriptors instead of full scans.

### Fixed

- **Security tab — vanished on NSM custom objects** — the **Security** tab disappeared when viewing NSM-managed Custom Objects because the tab view did not extend the NSM Custom Object base template that renders the tab nav-link. `security/tab/views.py` (`_get_base_template`) now returns `netbox_nsm/customobject.html` for `netbox_custom_objects` instances whose COT slug is an NSM object menu slug (`is_nsm_object_menu_slug`), so the Security tab stays visible/active on those detail pages.
- **IP Analyzer — cell tree dropped address-group rows under shared IPAM parents** — flat cell-tree tables silently lost most rows when several cell objects nested under the **same** synthesized IPAM parent prefix. On `bench-rule-00001` / `source_addresses` the cell holds 18 `bench-grp-*` groups (each a `/24`), but only ~8 rows rendered: `bench-grp-00001`…`bench-grp-00012` (all inside `10.128.0.0/20`) disappeared while siblings outside that `/20` (`bench-grp-00228`, `…00491`) survived. Root cause: `_insert_ipam_filler_prefixes` builds one IPAM-filler prefix node **per child**, so a dozen `10.128.0.0/20` filler siblings were created; `_collapse_ipa_cell_siblings_by_network` then merged them by network via `_merge_ipa_cell_node_metadata`, which combined metadata but **discarded the non-keeper filler’s `children`** — taking every group/address row under those fillers with it. **Fix:** `_merge_ipa_cell_node_metadata` now appends the merged node’s `children` onto the keeper before the recursive `_collapse_ipa_cell_siblings_by_network` pass re-collapses the combined subtree, so every distinct cell object (group or address) keeps a row (real duplicates/fillers still collapse by CIDR). `bench-rule-00001` now renders all 18 groups (21 tree nodes vs. 11 before). Asset cache bump.

- **IP Analyzer — All summary counts for flat cell tree** — toolbar counters now count the visible IPAM networks represented by the current IPA cell-tree table, including collapsed address-group rows with CIDR and rows marked with subnet containment warnings. This fixes cells such as `bench-rule-00001` / `source_addresses` where many visible `bench-grp-*` `/24` rows were reduced to `Subnets: 1 Ranges: 0 IPs: 1`; duplicate/containment state remains reflected separately in **Warnings**. No asset cache bump required.

- **IP Analyzer — Analysis failed for bench alias rows (`subnet_contained_in`)** — opening the IPA applet on bench overlap rules (e.g. `bench-alias-0000000` with `ipa_tree_parent_*` but no duplicate marker) returned HTTP 500 `Analysis failed: Failed lookup for key [subnet_contained_in]`. Root cause: `ipa_subnet_containment_meta.html` used `|default:node.subnet_contained_in` in a shared `{% with %}` block; Django resolves filter arguments eagerly, so the Parent column’s `elif ipa_tree_parent_cidr` branch still touched the missing key. **Fix:** `ipa_cell_tree_parent_cell.html` passes explicit `cidr` / `name` / `url` via separate `{% if %}` / `{% elif %}` includes (no cross-fallback); optional name/url use `|default:""`. **Dup** column unchanged — badge only for `subnet_contained_in`, `is_doppelt`, `object_duplicate`, or `count_duplicate` (not `cell_addresses_multi` alone). Backend keeps `subnet_contained_in` (redundant-network marker) separate from `ipa_tree_parent_*` (structural parent hint). Asset cache bump.

- **IP Analyzer — cell tree Parent column empty under IPAM hierarchy** — depth-nested cell rows (e.g. bench overlap: alias/group + 10.128.x net, depth 3 with `subnet-warning`) showed `—` in **Parent** even though depth markers implied an enclosing prefix. Root cause: IPAM-synthesized/filler prefix rows could carry a broken `ip_ref.str` while `prefix_display_cidr` was valid, so `_addr_tree_node_network` returned `None`, `_mark_ipa_subnet_containment_warnings` never walked those ancestors, and `_mark_ipa_subnet_containment_peer_fallback` skipped structural fillers as containers. **Fix:** `_addr_tree_node_network` falls back to `prefix_display_cidr`; synthesized prefix `ip_ref` uses `str(prefix.prefix)`; peer fallback includes IPAM filler/synthetic rows; `_mark_ipa_cell_tree_parent_hints` fills `ipa_tree_parent_*` from the nearest prefix ancestor when `subnet_contained_in` is still absent. Asset cache bump.

- **IP Analyzer — cell tree IP/Range/Prefix column counts** — prefix/range rows with visible address children in the cell tree no longer replace NetBox IPAM child counters with visible-subtree counts (e.g. `0/0/1` when NetBox reports 259 child prefixes). `_attach_ipa_drilldown_meta` and `_attach_ipa_object_tree_ipam_stats` now always use `_build_ipa_drilldown_source_meta` / `_prefix_ipam_stats` (same sources as the NetBox prefix detail tabs). Asset cache bump.

- **IP Analyzer — cell tree column text wrap** — long **Address group** memberships (e.g. `bench-grp-00000 , bench-grp-ovlp-00000 , none`), **Address** names, and **Us** gap/stats text wrap onto multiple lines instead of clipping in a fixed 168px column. **Address group** col width is 12.5rem (200px); `table-layout: fixed` is unchanged. **Network** (CIDR + depth markers) stays `nowrap` with depth-marker overflow clipping only in that column. Asset cache bump.

- **IP Analyzer — IPAM info-gap rows removed from cell tree** — muted gap summaries between visible hosts under a prefix (e.g. `[99 used / 155 unused ip]`) no longer appear as table rows in the flat IPA cell-tree object list. `_insert_ipa_host_gap_info_rows` is skipped in `_build_ipa_cell_object_tree`; `_prune_ipa_info_gap_nodes` drops any residual gap nodes before render. Gap helpers remain for unit tests; `addr_tree_node.html` still has a gap branch for legacy addr-tree markup but no builder inserts gaps today. Asset cache bump.

- **IP Analyzer — IPAM info-gap rows** — muted gap summaries between visible hosts under a prefix (e.g. `[99 used / 155 unused ip]`) render again in the **Us** column after the five-column cell-tree refactor; address, group, and parent columns show an em dash. Rows without gap text are omitted (no blank info-gap line with only a depth bullet in **Network**). Gap text also appears in **Network** (after depth markers) so the row is not visually empty when the table is scrolled left; label-less or duplicate consecutive gap nodes are pruned in the tree builder.

- **IP Analyzer — cell tree table width explosion** — the flat object-list table in the applet no longer blows out to hundreds of thousands of pixels (`div.nsm-addr-children` width ~788k px), leaving only a single narrow column visible. Root cause: `width: 100%` on `.nsm-ipa-cell-tree-table` inside a flex/`max-content` scale-host chain created an unbounded width feedback loop; the previous column-alignment fix skipped body-scale shrink but did not constrain the host. Fix: table uses fixed `--nsm-ipa-cell-tree-min-width` (~47rem), cell-tree `.nsm-addr-children` is `display: block` with `overflow-x: auto`, scale-host/inner switch to `width: 100%` when a cell-tree table is present, network column clips depth markers; horizontal scroll stays on the table wrapper. Asset cache bump.

- **IP Analyzer — cell tree table column alignment** — the flat object-list table in the applet (`bench-rule-00001` and similar) no longer shows misaligned or truncated headers (**Address** / **Address group** clipped to e.g. `ess` / `ss Group`). Root cause: legacy CSS from the pre-table layout set `display: flex` on `.nsm-ipa-object-tree-rows`, which now is a `<tbody>` and must stay `table-row-group`; leftover `grid-column` header rules and `nsm-ipa-applet-body-scale` transform scaling also fought `table-layout`. Fix: `<colgroup>` + `table-layout: fixed` with shared column widths on `th`/`td`, horizontal scroll on `.nsm-addr-children` when the table exceeds the ~530px applet width, skip body-scale shrink when a cell-tree table is present, asset cache bump.

- **IP Analyzer — Parent hint for subnet duplicates** — flat cell-tree rows with `subnet_contained_in` (bench overlap rules such as `bench-rule-00011`, alias/dup peers, nested prefix containment) render the orange parent prefix/CIDR in the **Parent** column again (`ipa_subnet_containment_meta.html` → `nsm-ipa-cell-parent-hint`). A peer-prefix fallback (`_mark_ipa_subnet_containment_peer_fallback`) marks containment when hosts and their /24 prefixes are root siblings in the flattened tree.
- **Legacy audit-report URL** — `/plugins/netbox-nsm/audit-report/` permanently redirects to `/plugins/netbox-nsm/object-report/` after the Audit Report → Object Report rename.
- **UI API auth** — `object-rules` and `inherited-links` endpoints now require login (`LoginRequiredMixin`), consistent with other plugin UI APIs.
- **Rules tab row-group layout** — grouped rules vanished when scroll-layout CSS set `flex-direction: column` on `.nsm-rules-body` without overriding it for `.nsm-rules-body--with-side-tabs`; side tabs and table now lay out in a row again (`flex-direction: row`, `min-height: 0` on the scroll container). Sidebar height sync uses the rules-body viewport height instead of table content height.
- **Rules tab All Rules group** — the virtual **All Rules** tab shows every rule again (`active_group_key is None` skips group filtering); COT and virtual-all-rules contexts prepend the tab via `prepend_all_rules_tab`.
- **Object Report — false "Run in progress"** — the viewer no longer treats the next daily `@system_job` successor (`status=scheduled`, e.g. job #17) as an active run. Only `pending`/`running` jobs block **Run now**; stale pending/running rows with no RQ entry are marked errored after two hours.
- **IP Analyzer — ADDRESS_GROUP pill** — collapsed NSM address-group rows (e.g. large `bench-grp-*` groups that are not member-expanded, and empty groups) now render an **ADDRESS_GROUP** pill instead of a misleading **ADDRESS** pill. The cell tree builder (`_mark_ipa_cell_pill_roles` in `analysis/ipa_object_tree.py`) tags group rows server-side; `ipa_cell_object_row_labels.html` renders the pill from that flag (logic stays in Python).
- **IP Analyzer — group-in-group pill duplication** — when an address group is directly selected and also listed in its own `cell_groups` metadata (nested group-in-group), `_scrub_ipa_cell_group_self_refs` removes the self ref so the row shows one self ADDRESS_GROUP pill and ancestor groups only in the membership column.
- **IP Analyzer — IPv6 role classification** — `_ipa_object_node_role_from_cidr_hint` now classifies IPv6 CIDR/host hints (previously IPv4-only, returning no role for IPv6). The host-containment helper (`_ipa_object_tree_containment_network`) uses the address family's max prefix length instead of a hardcoded `/32`, so IPv6 `/128` hosts resolve correctly instead of collapsing to a spurious `/32` supernet.
- **Object Analyzer — graph canvas grid** — the React-Flow dot grid is visible again in light and dark mode after the full-viewport layout change: the graph wrap fills `#nsm-oa-graph` via `position: absolute; inset: 0`, `colorMode` tracks Tabler `data-bs-theme`, and the Background uses explicit dot variant, canvas `bgColor`, and higher-contrast grid colors.
- **Object Analyzer — cloud/group expand** — expanding a cloud or merge (`grp:`) node no longer clears the entire graph when a secondary link points at a node already on the canvas (e.g. the analysis root). Back-links are skipped during expand and link-picker apply; tree layout and collapse walk descendants with cycle guards so a cyclic edge cannot blow the stack and unmount React Flow.
- **IP Analyzer applet — stuck loading spinner** — closing the popup or invalidating an in-flight analysis no longer leaves the active tab on “Analyzer running…” forever; failed or superseded loads surface `.nsm-ipa-applet-error` with a readable message (timeout, HTTP status, or server error text).
- **IP Analyzer — collapsed root groups template crash** — `_attach_ipa_cell_group_collapse_hints` no longer strips `collapsed_group_count` from the synthetic `collapsed_root_groups` wrapper (cells with many address groups triggered `blocktrans` `TemplateSyntaxError` and a 500 “Analyzer failed.”). The UI API now includes the exception short text in the JSON `error`/`detail` fields when rendering fails.
- **IP Analyzer — collapsed address groups in IPAM tree** — large bench-scale `bench-grp-*` rows that stay collapsed (no member expansion) now resolve a subnet anchor from group members and nest under the matching prefix in the cell/IPAM hierarchy instead of rendering in a separate root-level `collapsed_root_groups` block beside the tree. `_enrich_ipa_collapsed_group_networks_from_members` runs after network merge; the root wrapper fold (`_wrap_collapsed_root_group_nodes`) is no longer applied in the cell-tree pipeline.

### Changed

- **Object Analyzer — mode selector UX** — replaced the All/Security `<select>` with a NetBox-style segmented control (`btn-group` + `btn-check`). The toolbar uses a single grid row (Object search · View · Analyze), mode-specific legend and empty-state text live inside the card, and Security mode shows a concise hint about filtered categories. Backend filter logic is unchanged.
- **Object Report UI — toned-down styling** — summary counters use neutral `bg-body-secondary` boxes (only **Total findings** highlights in warning when &gt; 0); per-check summary pills removed (details live in the checks table); table and sample badges use `bg-*-subtle` instead of saturated `text-bg-*` for better dark-mode readability.
- **Object Report UI** — replaced four separate check cards with a NetBox-style `object-list` table (sortable **Findings** column, expandable sample sub-rows). Summary totals render as neutral counter boxes above the table.
- **Audit Report → Object Report** — renamed the daily report feature throughout the plugin: URL `/plugins/netbox-nsm/object-report/`, Python package `netbox_nsm/object_report/`, menu label **Object Report**, and job class `ObjectReportJob`. Existing `Job` rows named `"NSM Audit Report"` remain readable via legacy name lookup; new runs register as `"NSM Object Report"`.
- **Object Analyzer — faster "+" link picker** — clicking **+** on a graph node no longer fires `1 + N` API requests (one for the node's direct links plus one per direct link to fetch its secondary links). A new batched endpoint `AnalyzerPickerAPIView` (`api/analyzer/picker/`, builder in `analyzer/picker.py`) returns the whole two-level link tree in a single response, resolving child objects in bulk (one `in_bulk` query per content type instead of one `get` per child) and running each `registry.get_edges` resolver at most once. The React-Flow picker (`object_analyzer.html`) now renders the direct links immediately from a fast `depth=1` request and fills in the secondary-link count badges from one follow-up `depth=2` request, so the selection list appears without waiting for every child's relations to be computed. Direct links are grouped by relation category (e.g. *Interface*, *Console Port*, *Cable Termination*) with collapsible section headers instead of one flat list.
- **Object Analyzer — link-picker group selection** — collapsible group headers in the "+" link picker now include a tri-state checkbox (none / partial / all). Checking a group selects every L1 row in that category; unchecking clears them. Partial selection (via individual rows) shows an indeterminate group checkbox. The checkbox uses `stopPropagation` so expand/collapse stays on the header label. Selection helpers live in `analyzer/picker.py` and are covered by unit tests (frontend mirrors the same logic).
- **Object Analyzer — link picker hides existing links** — the "+" link picker no longer lists L1 rows (or embedded L2 counts) when a `parent→target` edge is already on the graph canvas. Filtering uses live React-Flow edge state on the client (`filterPickerTreeForCanvas` / `filter_picker_tree_for_canvas`); group header counts reflect only addable links. A target visible elsewhere via a different parent remains selectable.
- **Object Analyzer — link picker hides parent-linked L2 rows** — depth-2 picker items whose target is already a direct neighbor of the "+" parent (from the analyzer edge resolver, e.g. an interface's parent device resurfacing under a connected peer) are filtered server-side in `build_picker_tree` via `linked_neighbor_ids` / `parent_neighbor_ids`, with the same rule mirrored on the client for canvas-edge dedupe. Structural one-way links (interface→device, IP→assigned object) remain hidden at L1 via `filter_already_linked_picker_edges`.
- **IP Analyzer — prefix containment lookups** — `_IpaContainingPrefixCache` batches `prefix__net_contains` queries for IPA cell-tree walks (`_synthesize_ipa_cell_ipam_parent_prefixes`, gap rows, filler prefixes) instead of one ORM round-trip per host node. Host keys are collected during tree registration; the batch query runs lazily on the first cache resolve.
- **IP Analyzer CSS** — a group row's own pill (`nsm-ipa-cell-pill--self-group`) occupies the primary column; membership group pills remain in the trailing column.
- **IP Analyzer applet UX** — clearer cell/IPAM tree for dense bench rules (`bench-rule-00001`): sticky toolbar + column headers (Network / Cell object / Groups / Info), depth separators, collapsed summaries for 4+ group memberships, alias/dup peers as compact `+N aliases` hints (replacing stacked orange ADDRESS pills). Collapsed address groups nest in the IPAM hierarchy (member subnet anchor) instead of a separate root summary block. Display hints are built in `analysis/ipa_object_tree.py`; templates/CSS render only.
- **IP Analyzer applet — loading/error handling** — analysis fetch uses JSON-aware error parsing (including server `error`/`detail` fields), a 120s timeout, and stale-load recovery when the popup is closed and reopened mid-request; backend UI API returns JSON on unhandled errors instead of an HTML 500 page.

## [0.4.6] - 2026-06-17

### Added

- **Custom Objects related tab** — NSM object detail template (`customobject.html`) loads `custom_object_tab_tags` and renders `{% custom_objects_tab_link object %}` so the related-objects tab from **netbox-custom-objects** (PR 482) appears alongside Journal/Changelog when NSM overrides the tabs block

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
- **IP Analyzer** — CSV copy paths include object names (`all,branch,10.0.0.0/24` on **All**)
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
  no legacy `linkable` or incremental data migrations).
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
- Zone matrix, All Rules grid, IP Analyzer, and Object Analyzer
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
[0.4.8]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.8
[0.4.9]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.9
[0.4.10]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.10
[0.4.11]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.11
[0.4.14]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.14
[0.4.13]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.13
[0.4.12]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.12
[0.4.15]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.15
[0.4.16]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.16
[0.4.17]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.17
[0.4.18]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.18
[0.4.19]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.19
[0.4.20]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.20
[0.4.21]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.21
[0.4.22]: https://github.com/christianbur/netbox-nsm/releases/tag/v0.4.22
