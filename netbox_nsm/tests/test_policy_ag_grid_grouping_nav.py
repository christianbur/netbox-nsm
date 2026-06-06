"""Regression: policy grid grouping should refresh data in-place, not reload the page."""

from pathlib import Path
import unittest

_JS_PATH = (
    Path(__file__).resolve().parents[1] / "plugin_assets" / "js" / "policy_ag_grid.js"
)


class PolicyAgGridGroupingNavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js_source = _JS_PATH.read_text(encoding="utf-8")

    def test_grouping_navigation_prefers_in_place_apply(self):
        self.assertIn("function applyPolicyGroupingLevels(", self.js_source)
        self.assertIn(
            "if (applyPolicyGroupingLevels(levels, NSM_GROUP_NAV_CTX)) {",
            self.js_source,
        )

    def test_grouping_url_sync_uses_history_not_full_reload(self):
        self.assertIn("function syncGroupingUrl(", self.js_source)
        self.assertIn("window.history.pushState", self.js_source)
        self.assertIn(
            "syncGroupingUrl(buildGroupingUrlParams(levels), true)", self.js_source
        )
        navigate_block = self.js_source.split("function navigateGroupingLevels(", 1)[1]
        navigate_fn = navigate_block.split("function readDraggedGroupValue(", 1)[0]
        self.assertIn(
            "applyPolicyGroupingLevels(levels, NSM_GROUP_NAV_CTX)", navigate_fn
        )
        self.assertIn("window.location.search = params.toString();", navigate_fn)

    def test_group_nav_context_registered_from_toolbar(self):
        self.assertIn("NSM_GROUP_NAV_CTX = {", self.js_source)
        self.assertIn("gridApi: gridApi,", self.js_source)

    def test_grouped_column_sync_keeps_columns_visible(self):
        self.assertIn("function syncGroupedColumnVisibility(", self.js_source)
        self.assertIn("function resolveGroupedColIdsOnGrid(", self.js_source)
        self.assertIn("grouped column mapping failed", self.js_source)
        sync_fn = self.js_source.split("function syncGroupedColumnVisibility(", 1)[1]
        sync_fn = sync_fn.split("function scheduleGroupedColumnVisibility(", 1)[0]
        self.assertNotIn("setGridColumnsVisible(gridApi, toHide, false)", sync_fn)
        colvis_block = self.js_source.split(
            "function initColumnVisibilityPersistence(", 1
        )[1]
        colvis_block = colvis_block.split("function buildPolicyDefaultColDef(", 1)[0]
        self.assertNotIn("reapplyingGroupedVisibility", colvis_block)

    def test_grouped_sync_runs_after_column_def_reload(self):
        sync_block = self.js_source.split(
            "function initColumnVisibilityPersistence(", 1
        )[1]
        sync_block = sync_block.split("function buildPolicyDefaultColDef(", 1)[0]
        self.assertIn("applyStoredColumnVisibility(", sync_block)
        self.assertIn(
            "scheduleGroupedColumnVisibility(gridApi, columnDefs, config, profileKey)",
            sync_block,
        )

    def test_grouped_sync_skips_stored_visibility_for_grouped_cols(self):
        stored_block = self.js_source.split("function applyStoredColumnVisibility(", 1)[
            1
        ]
        stored_block = stored_block.split("function buildColumnMainMenuItems(", 1)[0]
        self.assertIn("readGroupedColIdsFromConfig(config)", stored_block)
        self.assertIn("groupedColIds.indexOf(colId) < 0", stored_block)

    def test_grouped_sync_after_reload_and_pill_change(self):
        apply_block = self.js_source.split("function applyPolicyGroupingLevels(", 1)[1]
        apply_block = apply_block.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("scheduleGroupedColumnVisibility(", apply_block)
        reload_block = self.js_source.split("function reloadPolicyGridData(", 1)[1]
        reload_block = reload_block.split("function createPolicyDatasource(", 1)[0]
        self.assertIn("scheduleGroupedColumnVisibility(", reload_block)
        toolbar_block = self.js_source.split("function bindNsmGroupToolbar(", 1)[1]
        toolbar_block = toolbar_block.split("function buildPolicyRulesCacheKey(", 1)[0]
        self.assertIn('gridApi.addEventListener("modelUpdated"', toolbar_block)

    def test_reload_keeps_fetch_path_for_group_changes(self):
        self.assertIn("reloadPolicyGridData(gridApi, config, state", self.js_source)
        self.assertIn("fetchPolicyGridRows(", self.js_source)

    def test_rules_data_cache_ttl_and_storage(self):
        self.assertIn("POLICY_RULES_CACHE_TTL_MS = 10 * 60 * 1000", self.js_source)
        self.assertIn("rulesDataCache: null", self.js_source)
        self.assertIn("function isPolicyRulesRefreshRequested(", self.js_source)
        self.assertIn("function stripPolicyRulesRefreshFromUrl(", self.js_source)
        self.assertIn("function buildPolicyRulesCacheKey(", self.js_source)
        self.assertIn("function storePolicyRulesDataCache(", self.js_source)
        self.assertIn("function maybePersistPolicyRulesDataCache(", self.js_source)
        self.assertIn("function invalidatePolicyRulesDataCache(", self.js_source)
        self.assertIn("function isPolicyRulesDownloadComplete(", self.js_source)
        self.assertIn("function applyPolicyRulesCacheToGrid(", self.js_source)
        self.assertIn("&refresh=1", self.js_source)

    def test_staged_load_uses_exponential_steps(self):
        fn = self.js_source.split("function buildProgressiveLoadSteps(", 1)[1]
        fn = fn.split("function cancelProgressivePolicyLoad(", 1)[0]
        self.assertIn("buildExponentialLoadSteps", fn)
        self.assertIn("gridLoadStepsFine", fn)
        self.assertIn("5, 10, 20, 50, 100, 250", fn)

    def test_client_cache_fast_path_on_initial_load(self):
        fn = self.js_source.split("function loadPolicyClientRows(", 1)[1]
        fn = fn.split("function appendPolicyClientRows(", 1)[0]
        self.assertIn("getPolicyRulesDataCache(state, config)", fn)
        self.assertIn("applyPolicyRulesCacheToGrid(", fn)

    def test_cache_persisted_only_when_download_complete(self):
        fn = self.js_source.split("function maybePersistPolicyRulesDataCache(", 1)[1]
        fn = fn.split("function buildPolicyGridFetchUrl(", 1)[0]
        self.assertIn("isPolicyRulesDownloadComplete(state)", fn)

    def test_ttl_expiry_clears_stale_client_cache(self):
        fn = self.js_source.split("function getPolicyRulesDataCache(", 1)[1]
        fn = fn.split("function invalidatePolicyRulesDataCache(", 1)[0]
        self.assertIn("invalidatePolicyRulesDataCache(state)", fn)

    def test_grouping_reload_uses_cache_fast_path(self):
        self.assertIn("{ groupingOnly: true }", self.js_source)
        self.assertIn("loadAllPolicyClientRows(", self.js_source)
        self.assertIn("{ useCached: true }", self.js_source)
        self.assertIn("&use_cached=1", self.js_source)
        apply_block = self.js_source.split("function applyPolicyGroupingLevels(", 1)[1]
        apply_block = apply_block.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("{ groupingOnly: true }", apply_block)

    def test_cache_key_excludes_group_by_params(self):
        cache_fn = self.js_source.split("function buildPolicyRulesCacheKey(", 1)[1]
        cache_fn = cache_fn.split("function isPolicyRulesCacheFresh(", 1)[0]
        self.assertNotIn("group_by", cache_fn)
        self.assertNotIn("collapsed", cache_fn)
        self.assertNotIn("expanded", cache_fn)

    def test_grouped_fetch_respects_server_last_row(self):
        fn = self.js_source.split("function resolvePolicyLoadEndRow(", 1)[1]
        fn = fn.split("function policyFetchPageExhausted(", 1)[0]
        self.assertNotIn("if (state && state.groupByEnabled)", fn)
        self.assertIn("state.knownTotalRows", fn)

    def test_grouped_initial_load_uses_single_fetch_when_collapsed(self):
        fn = self.js_source.split("function loadPolicyClientRows(", 1)[1]
        fn = fn.split("function appendPolicyClientRows(", 1)[0]
        self.assertIn("state.collapseAllGroups", fn)
        self.assertIn("loadAllPolicyClientRows(", fn)
        self.assertIn("!state.groupByEnabled", fn)

    def test_grouped_progressive_load_stops_on_partial_page(self):
        self.assertIn("function policyFetchPageExhausted(", self.js_source)
        fn = self.js_source.split("function loadPolicyClientRowsProgressive(", 1)[1]
        fn = fn.split("function loadPolicyClientRows(", 1)[0]
        self.assertIn("policyFetchPageExhausted(", fn)
        self.assertIn("if (fetchDone)", fn)

    def test_progressive_load_defers_row_height_recalc(self):
        fn = self.js_source.split("function loadPolicyClientRowsProgressive(", 1)[1]
        fn = fn.split("function isInfinitePolicyGrid(", 1)[0]
        self.assertIn("if (isLast)", fn)
        self.assertIn("resetPolicyRowHeights(api", fn)

    def test_progressive_load_uses_async_transactions(self):
        self.assertIn("function flushPolicyGridAsyncTransactions(", self.js_source)
        set_rows = self.js_source.split("function setPolicyGridRows(", 1)[1]
        set_rows = set_rows.split("function loadAllPolicyClientRows(", 1)[0]
        self.assertIn("applyTransactionAsync", set_rows)
        self.assertIn("flushPolicyGridAsyncTransactions(api)", self.js_source)

    def test_grid_perf_options_tuned_for_large_datasets(self):
        perf_block = self.js_source.split("var POLICY_GRID_PERF_OPTIONS = {", 1)[1]
        perf_block = perf_block.split("};", 1)[0]
        self.assertIn("rowBuffer: POLICY_GRID_ROW_BUFFER", perf_block)
        self.assertIn("suppressRowHoverHighlight: true", perf_block)
        self.assertIn("var POLICY_GRID_ROW_BUFFER = 5;", self.js_source)

    def test_get_row_height_uses_variable_object_cell_height(self):
        fn = self.js_source.split("function createPolicyGetRowHeight(", 1)[1]
        fn = fn.split("function createPolicyGetRowClass(", 1)[0]
        self.assertIn("resolvePolicyRowHeight", fn)
        self.assertIn("computePolicyGroupRowHeight", fn)
        self.assertNotIn("isPolicyRowFullRender", fn)

    def test_object_cell_renderer_always_full(self):
        fn = self.js_source.split("function createPolicyObjectCellRenderer(", 1)[1]
        fn = fn.split("function createPolicyGetRowHeight(", 1)[0]
        self.assertIn("buildObjectCellDom", fn)
        self.assertNotIn("buildObjectCellLiteDom", fn)
        self.assertNotIn("isPolicyRowFullRender", fn)

    def test_load_more_helpers_present(self):
        self.assertIn("function loadMorePolicyRows(", self.js_source)
        self.assertIn("function bindPolicyLoadMoreButton(", self.js_source)
        self.assertIn("function buildObjectCellDom(", self.js_source)
        self.assertIn("function enablePolicyFloatingFilters(", self.js_source)
        self.assertIn("function scheduleEnablePolicyFloatingFilters(", self.js_source)

    def test_floating_filters_deferred_for_policy_and_all_rules(self):
        policy_block = self.js_source.split("function initPolicyAgGrid(", 1)[1]
        policy_block = policy_block.split("function initNsmRulesAgGrid(", 1)[0]
        all_rules_block = self.js_source.split("function initNsmRulesAgGrid(", 1)[1]
        all_rules_block = all_rules_block.split("function applyNetBoxColorMode(", 1)[0]
        self.assertIn("enableFloatingFilters: false", policy_block)
        self.assertIn("enableColumnFilters: true", policy_block)
        self.assertIn("enablePolicyFloatingFilters(params.api)", policy_block)
        self.assertNotIn(
            "scheduleEnablePolicyFloatingFilters(params.api)", policy_block
        )
        self.assertIn("enableFloatingFilters: false", all_rules_block)
        self.assertIn("enableColumnFilters: true", all_rules_block)
        self.assertIn("enablePolicyFloatingFilters(params.api)", all_rules_block)
        self.assertIn(
            "scheduleEnablePolicyFloatingFilters(params.api)", all_rules_block
        )
        self.assertNotIn(
            "filter: false,\n        floatingFilter: false", all_rules_block
        )
        self.assertNotIn(
            "_nsmDefaultColDefExtra = { filter: false, floatingFilter: false }",
            all_rules_block,
        )

    def test_enable_floating_filters_updates_column_defs(self):
        fn = self.js_source.split("function enablePolicyFloatingFilters(", 1)[1]
        fn = fn.split("function scheduleEnablePolicyFloatingFilters(", 1)[0]
        self.assertIn("enableFloatingFilters: true", fn)
        self.assertIn('api.setGridOption("columnDefs"', fn)
        self.assertIn('api.setGridOption("floatingFiltersHeight"', fn)
        self.assertIn("POLICY_FLOATING_FILTERS_HEIGHT", fn)
        self.assertIn("_nsmDefaultColDefExtra = { floatingFilter: true }", fn)

    def test_object_cell_renders_all_items(self):
        fn = self.js_source.split("function buildObjectCellDom(", 1)[1]
        fn = fn.split("function buildObjectCellItem(", 1)[0]
        self.assertIn("items.length", fn)
        self.assertNotIn("nsm-ag-cell-more", fn)
        self.assertNotIn("maxPills", fn)
        self.assertNotIn("visibleCount", fn)

    def test_resolve_group_value_helpers_present(self):
        self.assertIn("function buildColIdToGroupValueMap(", self.js_source)
        self.assertIn("function buildGroupValueAliases(", self.js_source)
        self.assertIn("function normalizeGroupValue(", self.js_source)
        self.assertIn("function normalizeGroupLevelsInConfig(", self.js_source)

    def test_resolve_group_value_for_col_id_uses_col_map(self):
        fn = self.js_source.split(
            "function resolveGroupValueForColId(colId, config)", 1
        )[1]
        fn = fn.split("function readGroupLevelsFromConfig(config)", 1)[0]
        self.assertIn("buildColIdToGroupValueMap(config)", fn)
        self.assertIn("normalizeGroupValue(colValue, config)", fn)

    def test_resolve_group_value_aliases_from_option_labels(self):
        aliases = self.js_source.split("function buildGroupValueAliases(config)", 1)[1]
        aliases = aliases.split("function normalizeGroupValue(", 1)[0]
        self.assertIn('aliases["col:" + area + "::" + colLabel] = value', aliases)

    def test_apply_policy_grouping_normalizes_levels(self):
        fn = self.js_source.split("function applyPolicyGroupingLevels(levels, ctx)", 1)[
            1
        ]
        fn = fn.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("normalizeGroupValue(value, config)", fn)

    def test_column_reorder_suppressed_in_policy_and_all_rules(self):
        policy_block = self.js_source.split("function initPolicyAgGrid(", 1)[1]
        policy_block = policy_block.split("function initNsmRulesAgGrid(", 1)[0]
        all_rules_block = self.js_source.split("function initNsmRulesAgGrid(", 1)[1]
        all_rules_block = all_rules_block.split("function applyNetBoxColorMode(", 1)[0]
        self.assertIn("suppressMovableColumns: true", policy_block)
        self.assertIn("suppressDragLeaveHidesColumns: true", policy_block)
        self.assertIn("suppressMoveWhenColumnDragging: true", policy_block)
        self.assertIn("enforceNonMovableColumnDefs(", policy_block)
        self.assertIn("suppressMovableColumns: true", all_rules_block)
        self.assertIn("suppressDragLeaveHidesColumns: true", all_rules_block)
        self.assertIn("suppressMoveWhenColumnDragging: true", all_rules_block)
        self.assertIn("enforceNonMovableColumnDefs(", all_rules_block)
        default_col_def = self.js_source.split(
            "function buildPolicyDefaultColDef(profileKey, groupByEnabled, extra)", 1
        )[1].split("function buildPolicyGroupColumnDef(", 1)[0]
        self.assertIn("suppressMovable: true", default_col_def)

    def test_column_menu_omits_reorder_related_items(self):
        fn = self.js_source.split("function buildColumnMainMenuItems(", 1)[1]
        fn = fn.split("function initColumnVisibilityPersistence(", 1)[0]
        self.assertIn("function filterColumnMenuItems(", self.js_source)
        self.assertIn("pinSubMenu: true", self.js_source)
        self.assertIn("resetColumns: true", self.js_source)
        self.assertIn("filterColumnMenuItems(params.defaultItems", fn)

    def test_groupable_header_drag_helpers_intact(self):
        self.assertIn("function attachGroupableHeaderDrag(", self.js_source)
        self.assertIn('cell.setAttribute("draggable", "true")', self.js_source)
        self.assertIn("beginGroupHeaderPointerDrag(", self.js_source)
        self.assertIn("startGroupHeaderHtml5Drag(", self.js_source)
        self.assertIn("nsm-ag-groupable-header", self.js_source)

    def test_all_rules_rulebook_keeps_suppress_movable_and_lock_position(self):
        fn = self.js_source.split("function normalizeAllRulesGroupableColumnDefs(", 1)[
            1
        ]
        fn = fn.split("function initNsmRulesAgGrid(", 1)[0]
        self.assertIn("suppressMovable: true", fn)
        self.assertIn('next.lockPosition = "left"', fn)
        self.assertNotIn("delete next.suppressMovable", fn)

    def test_group_column_is_locked_and_non_movable(self):
        fn = self.js_source.split("function buildPolicyGroupColumnDef(", 1)[1]
        fn = fn.split("function prependPolicyGroupColumn(", 1)[0]
        self.assertIn('lockPosition: "left"', fn)
        self.assertIn("suppressMovable: true", fn)

    def test_object_cells_auto_size_columns_on_load(self):
        self.assertIn("function autoSizePolicyContentColumns(", self.js_source)
        self.assertIn(
            "api.autoSizeColumns({ colIds: colIds, skipHeader: false })", self.js_source
        )
        self.assertIn(
            "scheduleAutoSizePolicyContentColumns(api, state)", self.js_source
        )

    def test_object_cell_list_does_not_force_full_width(self):
        fn = self.js_source.split("function buildObjectCellDom(", 1)[1]
        fn = fn.split("function buildObjectCellItem(", 1)[0]
        self.assertIn('wrap.className = "nsm-ag-cell-list"', fn)
        self.assertNotIn("w-100", fn)


if __name__ == "__main__":
    unittest.main()
