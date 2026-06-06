"""Regression: rules grid grouping should refresh data in-place, not reload the page."""

from pathlib import Path
import unittest

_JS_PATH = (
    Path(__file__).resolve().parents[1] / "plugin_assets" / "js" / "rulebook_rules_grid.js"
)


class RulebookRulesGridNavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js_source = _JS_PATH.read_text(encoding="utf-8")

    def test_grouping_navigation_prefers_in_place_apply(self):
        self.assertIn("function applyRulesGroupingLevels(", self.js_source)
        self.assertIn(
            "if (applyRulesGroupingLevels(levels, NSM_GROUP_NAV_CTX)) {",
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
            "applyRulesGroupingLevels(levels, NSM_GROUP_NAV_CTX)", navigate_fn
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
        colvis_block = colvis_block.split("function buildRulesDefaultColDef(", 1)[0]
        self.assertNotIn("reapplyingGroupedVisibility", colvis_block)

    def test_grouped_sync_runs_after_column_def_reload(self):
        sync_block = self.js_source.split(
            "function initColumnVisibilityPersistence(", 1
        )[1]
        sync_block = sync_block.split("function buildRulesDefaultColDef(", 1)[0]
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
        apply_block = self.js_source.split("function applyRulesGroupingLevels(", 1)[1]
        apply_block = apply_block.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("scheduleGroupedColumnVisibility(", apply_block)
        reload_block = self.js_source.split("function reloadRulesGridData(", 1)[1]
        reload_block = reload_block.split("function createRulesDatasource(", 1)[0]
        self.assertIn("scheduleGroupedColumnVisibility(", reload_block)
        toolbar_block = self.js_source.split("function bindNsmGroupToolbar(", 1)[1]
        toolbar_block = toolbar_block.split("function buildRulesGridCacheKey(", 1)[0]
        self.assertIn('gridApi.addEventListener("modelUpdated"', toolbar_block)

    def test_reload_keeps_fetch_path_for_group_changes(self):
        self.assertIn("reloadRulesGridData(gridApi, config, state", self.js_source)
        self.assertIn("fetchRulesGridRows(", self.js_source)

    def test_rules_data_cache_ttl_and_storage(self):
        self.assertIn("RULES_TAB_CACHE_TTL_MS = 10 * 60 * 1000", self.js_source)
        self.assertIn("rulesDataCache: null", self.js_source)
        self.assertIn("function isRulesTabRefreshRequested(", self.js_source)
        self.assertIn("function stripRulesTabRefreshFromUrl(", self.js_source)
        self.assertIn("function buildRulesGridCacheKey(", self.js_source)
        self.assertIn("function storeRulesTabDataCache(", self.js_source)
        self.assertIn("function maybePersistRulesTabDataCache(", self.js_source)
        self.assertIn("function invalidateRulesTabDataCache(", self.js_source)
        self.assertIn("function isRulesTabDownloadComplete(", self.js_source)
        self.assertIn("function applyRulesTabCacheToGrid(", self.js_source)
        self.assertIn("&refresh=1", self.js_source)

    def test_staged_load_uses_exponential_steps(self):
        fn = self.js_source.split("function buildProgressiveLoadSteps(", 1)[1]
        fn = fn.split("function cancelProgressiveRulesLoad(", 1)[0]
        self.assertIn("buildExponentialLoadSteps", fn)
        self.assertIn("gridLoadStepsFine", fn)
        self.assertIn("5, 10, 20, 50, 100, 250", fn)

    def test_client_cache_fast_path_on_initial_load(self):
        fn = self.js_source.split("function loadRulesClientRows(", 1)[1]
        fn = fn.split("function appendRulesClientRows(", 1)[0]
        self.assertIn("getRulesTabDataCache(state, config)", fn)
        self.assertIn("applyRulesTabCacheToGrid(", fn)

    def test_cache_persisted_only_when_download_complete(self):
        fn = self.js_source.split("function maybePersistRulesTabDataCache(", 1)[1]
        fn = fn.split("function buildRulesGridFetchUrl(", 1)[0]
        self.assertIn("isRulesTabDownloadComplete(state)", fn)

    def test_ttl_expiry_clears_stale_client_cache(self):
        fn = self.js_source.split("function getRulesTabDataCache(", 1)[1]
        fn = fn.split("function invalidateRulesTabDataCache(", 1)[0]
        self.assertIn("invalidateRulesTabDataCache(state)", fn)

    def test_grouping_reload_uses_cache_fast_path(self):
        self.assertIn("{ groupingOnly: true }", self.js_source)
        self.assertIn("loadAllRulesClientRows(", self.js_source)
        self.assertIn("{ useCached: true }", self.js_source)
        self.assertIn("&use_cached=1", self.js_source)
        apply_block = self.js_source.split("function applyRulesGroupingLevels(", 1)[1]
        apply_block = apply_block.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("{ groupingOnly: true }", apply_block)

    def test_cache_key_excludes_group_by_params(self):
        cache_fn = self.js_source.split("function buildRulesGridCacheKey(", 1)[1]
        cache_fn = cache_fn.split("function isRulesTabCacheFresh(", 1)[0]
        self.assertNotIn("group_by", cache_fn)
        self.assertNotIn("collapsed", cache_fn)
        self.assertNotIn("expanded", cache_fn)

    def test_grouped_fetch_respects_server_last_row(self):
        fn = self.js_source.split("function resolveRulesLoadEndRow(", 1)[1]
        fn = fn.split("function rulesFetchPageExhausted(", 1)[0]
        self.assertNotIn("if (state && state.groupByEnabled)", fn)
        self.assertIn("state.knownTotalRows", fn)

    def test_grouped_initial_load_uses_single_fetch_when_collapsed(self):
        fn = self.js_source.split("function loadRulesClientRows(", 1)[1]
        fn = fn.split("function appendRulesClientRows(", 1)[0]
        self.assertIn("state.collapseAllGroups", fn)
        self.assertIn("loadAllRulesClientRows(", fn)
        self.assertIn("!state.groupByEnabled", fn)

    def test_grouped_progressive_load_stops_on_partial_page(self):
        self.assertIn("function rulesFetchPageExhausted(", self.js_source)
        fn = self.js_source.split("function loadRulesClientRowsProgressive(", 1)[1]
        fn = fn.split("function loadRulesClientRows(", 1)[0]
        self.assertIn("rulesFetchPageExhausted(", fn)
        self.assertIn("if (fetchDone)", fn)

    def test_progressive_load_defers_row_height_recalc(self):
        fn = self.js_source.split("function loadRulesClientRowsProgressive(", 1)[1]
        fn = fn.split("function isInfiniteRulesGrid(", 1)[0]
        self.assertIn("if (isLast)", fn)
        self.assertIn("resetRulesRowHeights(api", fn)

    def test_progressive_load_uses_async_transactions(self):
        self.assertIn("function flushRulesGridAsyncTransactions(", self.js_source)
        set_rows = self.js_source.split("function setRulesGridRows(", 1)[1]
        set_rows = set_rows.split("function loadAllRulesClientRows(", 1)[0]
        self.assertIn("applyTransactionAsync", set_rows)
        self.assertIn("flushRulesGridAsyncTransactions(api)", self.js_source)

    def test_grid_perf_options_tuned_for_large_datasets(self):
        perf_block = self.js_source.split("var RULES_GRID_PERF_OPTIONS = {", 1)[1]
        perf_block = perf_block.split("};", 1)[0]
        self.assertIn("rowBuffer: RULES_GRID_ROW_BUFFER", perf_block)
        self.assertIn("suppressRowHoverHighlight: true", perf_block)
        self.assertIn("var RULES_GRID_ROW_BUFFER = 5;", self.js_source)

    def test_get_row_height_uses_variable_object_cell_height(self):
        fn = self.js_source.split("function createRulesGetRowHeight(", 1)[1]
        fn = fn.split("function createRulesGetRowClass(", 1)[0]
        self.assertIn("resolveRulesRowHeight", fn)
        self.assertIn("computeRulesGroupRowHeight", fn)
        self.assertNotIn("isPolicyRowFullRender", fn)

    def test_object_cell_renderer_always_full(self):
        fn = self.js_source.split("function createRulesObjectCellRenderer(", 1)[1]
        fn = fn.split("function createRulesGetRowHeight(", 1)[0]
        self.assertIn("buildObjectCellDom", fn)
        self.assertNotIn("buildObjectCellLiteDom", fn)
        self.assertNotIn("isPolicyRowFullRender", fn)

    def test_load_more_helpers_present(self):
        self.assertIn("function loadMoreRulesRows(", self.js_source)
        self.assertIn("function bindRulesLoadMoreButton(", self.js_source)
        self.assertIn("function buildObjectCellDom(", self.js_source)
        self.assertIn("function enableRulesFloatingFilters(", self.js_source)
        self.assertIn("function scheduleEnableRulesFloatingFilters(", self.js_source)

    def test_floating_filters_deferred_for_rules_and_all_rules(self):
        rules_block = self.js_source.split("function initRulebookRulesAgGrid(", 1)[1]
        rules_block = rules_block.split("function initAllRulesAgGrid(", 1)[0]
        all_rules_block = self.js_source.split("function initAllRulesAgGrid(", 1)[1]
        all_rules_block = all_rules_block.split("function applyNetBoxColorMode(", 1)[0]
        self.assertIn("enableFloatingFilters: false", rules_block)
        self.assertIn("enableColumnFilters: true", rules_block)
        self.assertIn("enableRulesFloatingFilters(params.api)", rules_block)
        self.assertNotIn(
            "scheduleEnableRulesFloatingFilters(params.api)", rules_block
        )
        self.assertIn("enableFloatingFilters: false", all_rules_block)
        self.assertIn("enableColumnFilters: true", all_rules_block)
        self.assertIn("enableRulesFloatingFilters(params.api)", all_rules_block)
        self.assertIn(
            "scheduleEnableRulesFloatingFilters(params.api)", all_rules_block
        )
        self.assertNotIn(
            "filter: false,\n        floatingFilter: false", all_rules_block
        )
        self.assertNotIn(
            "_nsmDefaultColDefExtra = { filter: false, floatingFilter: false }",
            all_rules_block,
        )

    def test_enable_floating_filters_updates_column_defs(self):
        fn = self.js_source.split("function enableRulesFloatingFilters(", 1)[1]
        fn = fn.split("function scheduleEnableRulesFloatingFilters(", 1)[0]
        self.assertIn("enableFloatingFilters: true", fn)
        self.assertIn('api.setGridOption("columnDefs"', fn)
        self.assertIn('api.setGridOption("floatingFiltersHeight"', fn)
        self.assertIn("RULES_FLOATING_FILTERS_HEIGHT", fn)
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

    def test_apply_rules_grouping_normalizes_levels(self):
        fn = self.js_source.split("function applyRulesGroupingLevels(levels, ctx)", 1)[
            1
        ]
        fn = fn.split("function navigateGroupingLevels(", 1)[0]
        self.assertIn("normalizeGroupValue(value, config)", fn)

    def test_column_reorder_suppressed_in_rules_and_all_rules(self):
        rules_block = self.js_source.split("function initRulebookRulesAgGrid(", 1)[1]
        rules_block = rules_block.split("function initAllRulesAgGrid(", 1)[0]
        all_rules_block = self.js_source.split("function initAllRulesAgGrid(", 1)[1]
        all_rules_block = all_rules_block.split("function applyNetBoxColorMode(", 1)[0]
        self.assertIn("suppressMovableColumns: true", rules_block)
        self.assertIn("suppressDragLeaveHidesColumns: true", rules_block)
        self.assertIn("suppressMoveWhenColumnDragging: true", rules_block)
        self.assertIn("enforceNonMovableColumnDefs(", rules_block)
        self.assertIn("suppressMovableColumns: true", all_rules_block)
        self.assertIn("suppressDragLeaveHidesColumns: true", all_rules_block)
        self.assertIn("suppressMoveWhenColumnDragging: true", all_rules_block)
        self.assertIn("enforceNonMovableColumnDefs(", all_rules_block)
        default_col_def = self.js_source.split(
            "function buildRulesDefaultColDef(profileKey, groupByEnabled, extra)", 1
        )[1].split("function buildRulesGroupColumnDef(", 1)[0]
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
        fn = fn.split("function initAllRulesAgGrid(", 1)[0]
        self.assertIn("suppressMovable: true", fn)
        self.assertIn('next.lockPosition = "left"', fn)
        self.assertNotIn("delete next.suppressMovable", fn)

    def test_group_column_is_locked_and_non_movable(self):
        fn = self.js_source.split("function buildRulesGroupColumnDef(", 1)[1]
        fn = fn.split("function prependRulesGroupColumn(", 1)[0]
        self.assertIn('lockPosition: "left"', fn)
        self.assertIn("suppressMovable: true", fn)

    def test_object_cells_auto_size_columns_on_load(self):
        self.assertIn("function autoSizeRulesContentColumns(", self.js_source)
        self.assertIn(
            "api.autoSizeColumns({ colIds: colIds, skipHeader: false })", self.js_source
        )
        self.assertIn(
            "scheduleAutoSizeRulesContentColumns(api, state)", self.js_source
        )

    def test_object_cell_list_does_not_force_full_width(self):
        fn = self.js_source.split("function buildObjectCellDom(", 1)[1]
        fn = fn.split("function buildObjectCellItem(", 1)[0]
        self.assertIn('wrap.className = "nsm-ag-cell-list"', fn)
        self.assertNotIn("w-100", fn)


if __name__ == "__main__":
    unittest.main()
