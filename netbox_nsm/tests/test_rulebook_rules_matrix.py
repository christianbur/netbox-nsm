"""Regression: rules grid matrix dropzone and CSV export."""

from pathlib import Path
import unittest

_JS_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugin_assets"
    / "js"
    / "rulebook_rules_grid.js"
)


class RulebookRulesMatrixUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.js_source = _JS_PATH.read_text(encoding="utf-8")

    def test_mode_selector_toolbar_layout(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_ag_group_by.html"
        ).read_text(encoding="utf-8")
        chrome = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_ag_chrome_bar.html"
        ).read_text(encoding="utf-8")
        head = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_rules_grid_head.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="nsm-ag-view-mode-selector"', template)
        self.assertIn('data-view-mode="table"', template)
        self.assertIn('data-view-mode="group"', template)
        self.assertIn('data-view-mode="matrix"', template)
        self.assertIn('id="nsm-ag-toolbar-action-rail"', template)
        self.assertNotIn("nsm-ag-toolbar-grid", template)
        self.assertNotIn('id="nsm-ag-toolbar-reserved-slot"', template)
        self.assertNotIn('{% trans "Coming soon" %}', template)
        self.assertIn(
            'class="nsm-ag-group-panel-bar d-flex align-items-stretch"', template
        )
        self.assertIn('class="nsm-ag-view-mode-selector flex-shrink-0"', template)
        self.assertIn('id="nsm-ag-mode-panel-table"', template)
        self.assertIn('id="nsm-ag-mode-panel-group"', template)
        self.assertIn('id="nsm-ag-mode-panel-matrix"', template)
        self.assertIn('id="nsm-ag-matrix-dropzone"', template)
        self.assertIn('id="nsm-ag-group-dropzone"', template)
        self.assertIn('id="nsm-ag-group-expand-wrap"', template)
        self.assertIn('id="nsm-ag-matrix-mode-wrap"', template)
        self.assertIn("mdi-unfold-more", template)
        self.assertIn("mdi-unfold-less", template)
        self.assertNotIn("mdi-unfold-more-horizontal", template)
        self.assertNotIn("nsm-ag-zone-split", template)
        self.assertNotIn('{% trans "Grouping" %}', template)
        self.assertIn('{% trans "Group" %}', template)
        self.assertIn('{% trans "Table" %}', template)
        rules_page = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/rulebook_rules.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn('id="nsm-matrix-grid-mode-wrap"', rules_page)
        self.assertIn('id="nsm-rules-matrix-ag-grid"', rules_page)
        self.assertIn('id="nsm-ag-toolbar-help"', template)
        self.assertIn('id="nsm-ag-toolbar-help-toggle"', template)
        self.assertIn('class="nsm-ag-toolbar-help-details"', template)
        self.assertIn('{% trans "Learn more" %}', template)
        self.assertIn("Show rules view toolbar help", template)
        self.assertIn('aria-controls="nsm-ag-toolbar-help"', template)
        self.assertIn("mdi-help-circle-outline", template)
        self.assertIn("mutually exclusive", template)
        self.assertIn("Quick start: grouping", template)
        self.assertIn("Quick start: matrix", template)
        self.assertIn('{% trans "Export CSV" %}', chrome)
        self.assertNotIn("CSV exportieren", chrome)
        self.assertIn("?v=202606126", head)
        self.assertIn("action rail", template)
        self.assertIn("bindMatrixDropZone", self.js_source)
        self.assertIn("renderMatrixPills", self.js_source)
        self.assertIn("bindMatrixModeToolbar", self.js_source)
        self.assertIn("bindToolbarViewModeSelector", self.js_source)
        self.assertIn("bindToolbarHelpToggle", self.js_source)
        self.assertIn("syncToolbarHelpVisibility", self.js_source)
        self.assertIn("NSM_TOOLBAR_HELP_VISIBLE", self.js_source)
        self.assertNotIn("NSM_TOOLBAR_HELP_DISMISS_KEY", self.js_source)
        self.assertNotIn("isToolbarHelpDismissed", self.js_source)

    def test_matrix_validation_helpers(self):
        self.assertIn("function validateMatrixPair(", self.js_source)
        self.assertIn("function isMatrixCompatibleValue(", self.js_source)
        self.assertIn("contentTypeId", self.js_source)

    def test_toolbar_view_mode_enum(self):
        self.assertIn(
            'var NSM_TOOLBAR_VIEW_MODES = ["table", "group", "matrix"]', self.js_source
        )
        self.assertIn("function resolveToolbarViewMode(", self.js_source)
        self.assertIn("function applyToolbarViewMode(", self.js_source)
        self.assertIn("function syncToolbarViewModeSelector(", self.js_source)
        self.assertIn("nsm-ag-view-mode-matrix", self.js_source)
        self.assertIn("enterMatrixMode", self.js_source)
        self.assertIn("exitMatrixMode", self.js_source)

    def test_matrix_mode_chrome_shrinks_to_content(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "plugin_assets/css/rulebook_rules_grid.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".nsm-ag-view-mode-matrix .nsm-ag-grid-chrome", css)
        self.assertIn(".nsm-ag-view-mode-matrix .nsm-rules-matrix-wrap", css)
        matrix_block = css.split(".nsm-ag-view-mode-matrix .nsm-rules-matrix-wrap", 1)[
            1
        ]
        matrix_block = matrix_block.split(".nsm-ag-group-dropzone", 1)[0]
        self.assertIn("width: fit-content", matrix_block)
        self.assertIn("height: fit-content", matrix_block)
        self.assertIn(".nsm-ag-view-mode-matrix .nsm-ag-mode-panel-group", css)
        self.assertIn(
            ".nsm-rules-matrix-wrap .nsm-matrix-ag-grid .ag-body-horizontal-scroll", css
        )

    def test_csv_export_button_wired(self):
        self.assertIn("bindCsvExportButton", self.js_source)
        self.assertIn("exportRulesGridCsv", self.js_source)
        self.assertIn("buildCsvFilename", self.js_source)

    def test_rules_csv_export_resolves_column_fields(self):
        self.assertIn("function rulesGridColumnField(", self.js_source)
        self.assertIn("function rulesGridCellCsvValue(", self.js_source)
        fn = self.js_source.split("function rulesGridCellCsvValue(", 1)[1]
        fn = fn.split("function buildRulesGridCsv(", 1)[0]
        self.assertIn("rulesGridColumnField(col)", fn)
        self.assertIn('field + "__filter"', fn)
        self.assertIn('colId === "status"', fn)
        build_fn = self.js_source.split("function buildRulesGridCsv(", 1)[1]
        build_fn = build_fn.split("function normalizeToolbarViewMode(", 1)[0]
        self.assertIn("rulesGridCellCsvValue(node.data, col, config)", build_fn)
        self.assertNotIn("node.data[colId]", build_fn)

    def test_grouping_clears_matrix_and_vice_versa(self):
        self.assertIn("clearMatrixForGrouping", self.js_source)
        self.assertIn("clearGroupingForMatrix", self.js_source)

    def test_matrix_header_drop_uses_explicit_drag_value(self):
        """Header matrix drops must not rely on NSM_GROUP_DRAG_VALUE cleared by dragend."""
        self.assertIn("function resolveMatrixDropRejectReason(", self.js_source)
        self.assertIn("dragValue", self.js_source)
        resolve_fn = self.js_source.split("function resolveMatrixDropRejectReason(", 1)[
            1
        ].split("function isMatrixDropRejected(", 1)[0]
        self.assertIn("dragValue != null", resolve_fn)
        apply_fn = self.js_source.split("function applyMatrixHeaderDrop(", 1)[1]
        apply_fn = apply_fn.split("function bindMatrixDropZone(", 1)[0]
        self.assertIn("groupValue", apply_fn)
        self.assertIn("resolveMatrixDropRejectReason(", apply_fn)
        self.assertIn("inferMatrixTargetSlotFromPoint(", apply_fn)
        bind_fn = self.js_source.split("function bindMatrixDropZone(", 1)[1]
        bind_fn = bind_fn.split("function bindCsvExportButton(", 1)[0]
        self.assertIn('addEventListener(\n      "drop"', bind_fn)
        self.assertIn("true\n    )", bind_fn)
        self.assertIn("resolveMatrixToolbarConfig(", bind_fn)
        dragend_block = self.js_source.split('cell.addEventListener("dragend"', 1)[1]
        dragend_block = dragend_block.split("cell.addEventListener(", 1)[0]
        self.assertIn("setMatrixDropzoneState(", dragend_block)

    def test_update_config_persists_partial_matrix_levels(self):
        """First matrix drop must persist row/column config before the pair is complete."""
        fn = self.js_source.split("function updateConfigFromMatrixLevels(", 1)[1]
        fn = fn.split("function buildMatrixUrlParams(", 1)[0]
        self.assertIn("function matrixLevelValue(", self.js_source)
        self.assertIn("config.matrixRow = rowValue", fn)
        self.assertIn("config.matrixCol = colValue", fn)
        self.assertNotRegex(
            fn,
            r"if \(!matrixLevelsComplete\(levels\)\) \{\s*return;\s*\}\s*var rowValue",
        )

    def test_matrix_empty_slots_hide_row_column_placeholders(self):
        """Empty matrix dropzone shows hint only — no Row/Column slot placeholders."""
        render_fn = self.js_source.split("function renderMatrixPills(", 1)[1]
        render_fn = render_fn.split("function matrixLevelValue(", 1)[0]
        self.assertNotIn("nsm-ag-matrix-pill-slot", render_fn)
        self.assertNotIn("matrixRowSlotLabel(config)", render_fn)
        self.assertNotIn("matrixColSlotLabel(config)", render_fn)
        pill_fn = self.js_source.split("function buildMatrixPillElement(", 1)[1]
        pill_fn = pill_fn.split("function renderMatrixPills(", 1)[0]
        self.assertNotIn("nsm-ag-matrix-pill-slot-label", pill_fn)

    def test_dropzone_pills_show_functional_role_labels(self):
        """Assigned grouping/matrix pills prefix column names with role labels."""
        self.assertIn("function buildPillLabelWithRole(", self.js_source)
        self.assertIn("function groupLevelRoleLabel(", self.js_source)
        self.assertIn("function matrixSlotRoleLabel(", self.js_source)
        self.assertIn("nsm-ag-group-pill-role", self.js_source)
        group_pill_fn = self.js_source.split("function buildGroupPillElement(", 1)[1]
        group_pill_fn = group_pill_fn.split("function renderGroupPills(", 1)[0]
        self.assertIn("groupLevelRoleLabel(config, level)", group_pill_fn)
        self.assertIn("buildPillLabelWithRole(", group_pill_fn)
        matrix_pill_fn = self.js_source.split("function buildMatrixPillElement(", 1)[1]
        matrix_pill_fn = matrix_pill_fn.split("function renderMatrixPills(", 1)[0]
        self.assertIn("matrixSlotRoleLabel(config, slot)", matrix_pill_fn)
        self.assertIn("buildPillLabelWithRole(", matrix_pill_fn)
        de_po = (
            Path(__file__).resolve().parents[1] / "locale/de/LC_MESSAGES/django.po"
        ).read_text(encoding="utf-8")
        self.assertIn('msgid "Main group"', de_po)
        self.assertIn('msgstr "Hauptgruppenobjekt"', de_po)
        self.assertIn('msgid "Subgroup"', de_po)
        self.assertIn('msgstr "Untergruppenobjekt"', de_po)
        self.assertIn('msgid "Row"', de_po)
        self.assertIn('msgstr "Zeile"', de_po)
        self.assertIn('msgid "Column"', de_po)
        self.assertIn('msgstr "Spalte"', de_po)

    def test_matrix_session_persists_partial_draft(self):
        persist_fn = self.js_source.split("function persistMatrixSession(", 1)[1]
        persist_fn = persist_fn.split("function restoreMatrixSession(", 1)[0]
        self.assertIn("draft: !config.matrixEnabled", persist_fn)
        restore_fn = self.js_source.split("function restoreMatrixSession(", 1)[1]
        restore_fn = restore_fn.split("function clearGroupingForMatrix(", 1)[0]
        self.assertIn("isMatrixCompatibleValue(rowValue, config)", restore_fn)
        self.assertIn("isMatrixCompatibleValue(colValue, config)", restore_fn)

    def test_filter_view_directive_parser(self):
        self.assertIn("function parseViewDirective(", self.js_source)
        self.assertIn("function countViewDirectives(", self.js_source)
        self.assertIn("function normalizeFilterQueryView(", self.js_source)
        self.assertIn("function applyFilterViewDirective(", self.js_source)
        self.assertIn("function appendViewDirective(", self.js_source)
        self.assertIn("NSM_VIEW_DIRECTIVE_MULTIPLE_ERROR", self.js_source)
        self.assertIn("function applyMatrixAxisFiltersFromModel(", self.js_source)
        self.assertIn("function syncMatrixFilterToUrl(", self.js_source)
        self.assertIn("function extractMatrixAxisQueries(", self.js_source)
        self.assertIn("NSM_FILTER_VIEW_MATRIX_NOT_READY_FALLBACK", self.js_source)
        group_by = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_ag_group_by.html"
        ).read_text(encoding="utf-8")
        self.assertIn("Filter query view()", group_by)
        filter_query = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_ag_filter_query.html"
        ).read_text(encoding="utf-8")
        self.assertIn("view(matrix)", filter_query)
        self.assertIn("view(table)", filter_query)

    def test_filter_query_syncs_with_toolbar_view_mode(self):
        self.assertIn("function syncFilterQueryViewDirective(", self.js_source)
        fn = self.js_source.split("function syncFilterQueryViewDirective(", 1)[1]
        fn = fn.split("function applyToolbarViewMode(", 1)[0]
        self.assertIn("appendViewDirective(", fn)
        self.assertIn("parseViewDirective(currentQuery)", fn)
        self.assertIn("resolveToolbarViewMode(config)", fn)
        resolve_fn = self.js_source.split("function resolveFilterQueryText(", 1)[1]
        resolve_fn = resolve_fn.split("function primeFilterQueryInput(", 1)[0]
        self.assertIn("parseViewDirective(query)", resolve_fn)
        self.assertNotIn(
            "appendViewDirective(query, config.activeFilterView)", resolve_fn
        )

    def test_apply_rules_matrix_levels_skips_matrix_mode_when_clearing(self):
        fn = self.js_source.split("function applyRulesMatrixLevels(", 1)[1]
        fn = fn.split("function navigateMatrixLevels(", 1)[0]
        self.assertIn("if (normalized.length > 0)", fn)
        matrix_set = fn.split("if (normalized.length > 0)", 1)[1]
        self.assertIn('setToolbarViewMode(config, "matrix")', matrix_set)
        self.assertNotIn(
            'clearGroupingForMatrix(config, ctx);\n    setToolbarViewMode(config, "matrix");',
            fn,
        )

    def test_table_view_directive_reasserts_toolbar_mode_after_matrix_clear(self):
        fn = self.js_source.split("function applyFilterViewDirective(", 1)[1]
        table_fn = fn.split('if (mode === "group")', 1)[0]
        self.assertIn("applyRulesMatrixLevels([], ctx || NSM_MATRIX_CTX)", table_fn)
        self.assertIn('setToolbarViewMode(config, "table")', table_fn)
        matrix_clear_idx = table_fn.index(
            "applyRulesMatrixLevels([], ctx || NSM_MATRIX_CTX)"
        )
        table_reassert_idx = table_fn.rindex('setToolbarViewMode(config, "table")')
        self.assertGreater(table_reassert_idx, matrix_clear_idx)

    def test_build_matrix_url_params_clears_mode_when_incomplete(self):
        fn = self.js_source.split("function buildMatrixUrlParams(", 1)[1]
        fn = fn.split("function syncMatrixUrl(", 1)[0]
        self.assertIn("if (!matrixLevelsComplete(levels))", fn)
        incomplete = fn.split("if (!matrixLevelsComplete(levels))", 1)[1]
        self.assertIn('params.delete("mode")', incomplete)


class RulebookRulesMatrixModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = Path(__file__).resolve().parents[1] / "plugin_assets" / "js"
        cls.matrix_js = (base / "matrix_ag_grid.js").read_text(encoding="utf-8")
        cls.js_source = (base / "rulebook_rules_grid.js").read_text(encoding="utf-8")

    def test_matrix_grid_height_fits_row_count(self):
        self.assertIn("function fitMatrixGridHeight(", self.matrix_js)
        self.assertIn("function syncMatrixGridHeight(", self.matrix_js)
        self.assertIn("suppressHorizontalScroll: true", self.matrix_js)
        self.assertIn(
            "syncMatrixGridHeight(datasourceState, headerHeight, rowHeight)",
            self.matrix_js,
        )
        self.assertIn('gridEl.closest(".nsm-rules-matrix-wrap")', self.matrix_js)

    def test_matrix_module_exports_embedded_api(self):
        self.assertIn("window.NSM_MATRIX_AG", self.matrix_js)
        self.assertIn("createEmbeddedMatrixAgGrid", self.matrix_js)
        self.assertIn("exportMatrixCsv", self.matrix_js)

        self.assertIn("applyMatrixAxisFilters", self.matrix_js)
        self.assertIn("readMatrixAxisFiltersFromUrl", self.matrix_js)
        self.assertIn("clearMatrixAxisFilters", self.matrix_js)

    def test_matrix_csv_export_uses_grid_rows_and_dst_fields(self):
        self.assertIn("function buildMatrixGridFetchUrl(", self.matrix_js)
        self.assertIn("function resolveMatrixDstColumns(", self.matrix_js)
        self.assertIn("function collectMatrixRowsFromGridApi(", self.matrix_js)
        fetch_fn = self.matrix_js.split("function fetchAllMatrixRows(", 1)[1]
        fetch_fn = fetch_fn.split("function matrixCellCsvValue(", 1)[0]
        self.assertIn("buildMatrixGridFetchUrl(config, 0, total)", fetch_fn)
        export_fn = self.matrix_js.split("function exportMatrixCsv(", 1)[1]
        export_fn = export_fn.split("function downloadCsvBlob(", 1)[0]
        self.assertIn("collectMatrixRowsFromGridApi(gridApi)", export_fn)
        self.assertIn("resolveMatrixDstColumns(state, gridApi)", export_fn)
        cell_fn = self.matrix_js.split("function matrixCellCsvValue(", 1)[1]
        cell_fn = cell_fn.split("function buildMatrixCsv(", 1)[0]
        self.assertIn("cellValue.bg", cell_fn)
        self.assertIn("directedLines", cell_fn)
        build_fn = self.matrix_js.split("function buildMatrixCsv(", 1)[1]
        build_fn = build_fn.split("function csvEscapeField(", 1)[0]
        self.assertIn("matrixDstField(col)", build_fn)

    def test_matrix_diagonal_cells_orange_self_border(self):
        self.assertIn("function matrixCellIsSelf(", self.matrix_js)
        self.assertIn('"nsm-matrix-self": matrixCellIsSelf', self.matrix_js)
        is_self_fn = self.matrix_js.split("function matrixCellIsSelf(", 1)[1]
        is_self_fn = is_self_fn.split("function matrixCellIsEmpty(", 1)[0]
        self.assertIn("v.isSelf", is_self_fn)
        self.assertIn("dstPk === srcPk", is_self_fn)
        style_fn = self.matrix_js.split("function matrixCellStyle(", 1)[1]
        style_fn = style_fn.split("function applyMatrixZoneAccent(", 1)[0]
        self.assertIn("v.isSelf", style_fn)
        self.assertIn("--nsm-matrix-self-border", style_fn)
        self.assertIn("253, 126, 20", style_fn)
        matrix_css = (
            Path(__file__).resolve().parents[1] / "plugin_assets/css/matrix_ag_grid.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".nsm-matrix-self", matrix_css)
        self.assertIn("--nsm-matrix-self-border", matrix_css)
        self.assertIn("253, 126, 20", matrix_css)
        self.assertIn(
            '.ag-cell[col-id^="dst_"].nsm-matrix-empty.nsm-matrix-self',
            matrix_css,
        )
        self.assertIn(
            '.ag-cell[col-id^="dst_"].nsm-matrix-self:not(.nsm-matrix-empty)',
            matrix_css,
        )
        matrix_head = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_matrix_ag_grid_head.html"
        ).read_text(encoding="utf-8")
        self.assertIn("?v=202606126", matrix_head)

    def test_matrix_empty_cells_stay_light_not_zone_accent(self):
        self.assertIn("function matrixCellIsEmpty(", self.matrix_js)
        self.assertIn('"nsm-matrix-empty": matrixCellIsEmpty', self.matrix_js)
        self.assertIn("nsm-matrix-cell-empty", self.matrix_js)
        self.assertIn("--nsm-matrix-empty-bg", self.matrix_js)
        style_fn = self.matrix_js.split("function matrixCellStyle(", 1)[1]
        style_fn = style_fn.split("function applyMatrixZoneAccent(", 1)[0]
        self.assertIn("--nsm-matrix-empty-bg", style_fn)
        self.assertNotIn('backgroundColor = "transparent"', style_fn)
        matrix_css = (
            Path(__file__).resolve().parents[1] / "plugin_assets/css/matrix_ag_grid.css"
        ).read_text(encoding="utf-8")
        self.assertIn('.ag-cell[col-id^="dst_"].nsm-matrix-empty', matrix_css)
        self.assertIn("--nsm-matrix-empty-bg", matrix_css)
        zone_base = matrix_css.split(".nsm-matrix-zone-accent {", 1)[1].split("}", 1)[0]
        self.assertNotIn("background:", zone_base)
        self.assertIn(".nsm-matrix-dst-header-inner.nsm-matrix-zone-accent", matrix_css)
        self.assertIn("inset 0 -3px 0 var(--nsm-matrix-zone-accent-border)", matrix_css)
        self.assertNotIn(
            ".nsm-matrix-cell-inner.nsm-matrix-zone-accent",
            matrix_css,
        )

    def test_matrix_mode_toggle_in_action_rail(self):
        self.assertIn("bindMatrixModeToolbar", self.js_source)
        self.assertIn("nsm-ag-matrix-mode-wrap", self.js_source)
        self.assertNotIn("nsm-matrix-corner-mode-toggle", self.matrix_js)
        self.assertNotIn("showMatrixModeToggle", self.js_source)
        self.assertNotIn("nsm-matrix-corner-mode-btn", self.matrix_js)
        matrix_css = (
            Path(__file__).resolve().parents[1] / "plugin_assets/css/matrix_ag_grid.css"
        ).read_text(encoding="utf-8")
        self.assertNotIn("nsm-matrix-corner-mode-toggle", matrix_css)
        self.assertNotIn(
            'id="nsm-matrix-grid-mode-wrap"',
            (
                Path(__file__).resolve().parents[1]
                / "templates/netbox_nsm/rulebook_rules.html"
            ).read_text(encoding="utf-8"),
        )

    def test_matrix_mode_toolbar_visible_in_matrix_view_mode(self):
        fn = self.js_source.split("function syncMatrixModeToolbarVisibility(", 1)[1]
        fn = fn.split("function syncToolbarActionRailVisibility(", 1)[0]
        self.assertIn('getElementById("nsm-ag-matrix-mode-wrap")', fn)
        self.assertIn("matrixActionRailControlVisible", fn)
        self.assertNotIn("useEmbeddedMatrixModeToggle", fn)
        self.assertNotIn("useCornerToggle", fn)
        helper = self.js_source.split("function matrixActionRailControlVisible(", 1)[1]
        helper = helper.split("function syncMatrixModeToolbarVisibility(", 1)[0]
        self.assertIn('toolbarMode === "matrix"', helper)
        self.assertIn("config.matrixEnabled", helper)

    def test_toolbar_horizontal_layout_css(self):
        css = (
            Path(__file__).resolve().parents[1]
            / "plugin_assets/css/rulebook_rules_grid.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".nsm-ag-group-panel-bar {\n  display: flex;", css)
        self.assertNotIn(".nsm-ag-toolbar-grid", css)
        self.assertNotIn(".nsm-ag-toolbar-reserved-slot", css)
        self.assertIn(".nsm-ag-view-mode-selector", css)
        self.assertIn(
            "margin-left: auto", css.split(".nsm-ag-toolbar-action-rail", 1)[1]
        )

    def test_action_rail_visibility_by_view_mode(self):
        group_fn = self.js_source.split("function syncGroupToolbarVisibility(", 1)[1]
        group_fn = group_fn.split("function bindToolbarHelpToggle(", 1)[0]
        self.assertIn("groupActionRailControlVisible", group_fn)
        self.assertIn('getElementById("nsm-ag-group-expand-wrap")', group_fn)
        self.assertIn("syncMatrixModeToolbarVisibility(config, toolbarMode)", group_fn)
        self.assertIn("syncToolbarActionRailVisibility(config, toolbarMode)", group_fn)
        self.assertNotIn("syncToolbarSecondaryCell", group_fn)

        matrix_fn = self.js_source.split(
            "function syncMatrixModeToolbarVisibility(", 1
        )[1]
        matrix_fn = matrix_fn.split("function syncToolbarActionRailVisibility(", 1)[0]
        self.assertIn("matrixActionRailControlVisible", matrix_fn)
        self.assertNotIn("useEmbeddedMatrixModeToggle", matrix_fn)

        helper = self.js_source.split("function matrixActionRailControlVisible(", 1)[1]
        helper = helper.split("function syncMatrixModeToolbarVisibility(", 1)[0]
        self.assertIn('toolbarMode === "matrix"', helper)
        self.assertIn("config.matrixEnabled", helper)

        rail_fn = self.js_source.split("function syncToolbarActionRailVisibility(", 1)[
            1
        ]
        rail_fn = rail_fn.split("function syncGroupToolbarVisibility(", 1)[0]
        self.assertIn('getElementById("nsm-ag-toolbar-action-rail")', rail_fn)
        self.assertIn("groupActionRailControlVisible", rail_fn)
        self.assertIn("matrixActionRailControlVisible", rail_fn)

    def test_resolve_toolbar_view_mode_prefers_group_over_matrix(self):
        fn = self.js_source.split("function resolveToolbarViewMode(", 1)[1]
        fn = fn.split("function syncToolbarViewModeSelector(", 1)[0]
        group_idx = fn.index("readGroupLevelsFromConfig(config)")
        matrix_idx = fn.index("config.matrixEnabled")
        self.assertLess(group_idx, matrix_idx)

    def test_restore_matrix_session_skips_when_grouping_active(self):
        fn = self.js_source.split("function restoreMatrixSession(", 1)[1]
        fn = fn.split("function clearGroupingForMatrix(", 1)[0]
        self.assertIn("readGroupLevelsFromConfig(config).length > 0", fn)
        self.assertIn("config.groupBy", fn)

    def test_clear_grouping_does_not_force_group_view_mode(self):
        fn = self.js_source.split("function applyRulesGroupingLevels(", 1)[1]
        fn = fn.split("function renderGroupPills(", 1)[0]
        self.assertIn("if (levels.length > 0)", fn)
        self.assertIn('setToolbarViewMode(config, "group")', fn)

    def test_dropzones_respect_toolbar_view_mode(self):
        self.assertIn("function isGroupDropzoneEnabled(", self.js_source)
        self.assertIn("function isMatrixDropzoneEnabled(", self.js_source)
        self.assertIn("function syncDropzoneEnabledState(", self.js_source)
        self.assertIn("tableDragDisabledMessage", self.js_source)
        group_resolve = self.js_source.split(
            "function resolveGroupDropRejectReason(", 1
        )[1].split("function isGroupDropRejected(", 1)[0]
        self.assertIn("isGroupDropzoneEnabled(config)", group_resolve)
        self.assertIn('"view_mode"', group_resolve)
        matrix_resolve = self.js_source.split(
            "function resolveMatrixDropRejectReason(", 1
        )[1].split("function isMatrixDropRejected(", 1)[0]
        self.assertIn("isMatrixDropzoneEnabled(config)", matrix_resolve)
        self.assertIn('"view_mode"', matrix_resolve)
        group_hits = self.js_source.split("function pointerHitsGroupDropzone(", 1)[1]
        group_hits = group_hits.split("function pointerHitsMatrixDropzone(", 1)[0]
        self.assertIn("isGroupDropzoneEnabled(config)", group_hits)
        matrix_hits = self.js_source.split("function pointerHitsMatrixDropzone(", 1)[1]
        matrix_hits = matrix_hits.split("function createGroupHeaderDragGhost(", 1)[0]
        self.assertIn("isMatrixDropzoneEnabled(config)", matrix_hits)
        sync_fn = self.js_source.split("function syncGroupToolbarVisibility(", 1)[1]
        sync_fn = sync_fn.split("function bindToolbarHelpToggle(", 1)[0]
        self.assertIn("syncDropzoneEnabledState(config)", sync_fn)
        table_fn = self.js_source.split("function applyFilterViewDirective(", 1)[1]
        table_fn = table_fn.split('if (mode === "group")', 1)[0]
        self.assertIn("syncGroupToolbarVisibility(config)", table_fn)
        bind_group = self.js_source.split("function bindGroupDropZone(", 1)[1]
        bind_group = bind_group.split("function matrixColumnMeta(", 1)[0]
        self.assertIn("isGroupDropzoneEnabled(config)", bind_group)
        bind_matrix = self.js_source.split("function bindMatrixDropZone(", 1)[1]
        bind_matrix = bind_matrix.split("function bindCsvExportButton(", 1)[0]
        self.assertIn("isMatrixDropzoneEnabled(activeConfig)", bind_matrix)

    def test_table_mode_panel_shows_drag_disabled_hint(self):
        template = (
            Path(__file__).resolve().parents[1]
            / "templates/netbox_nsm/inc/rulebook_ag_group_by.html"
        ).read_text(encoding="utf-8")
        self.assertIn('id="nsm-ag-mode-panel-table-hint"', template)
        self.assertIn("drag-and-drop is disabled", template)
        css = (
            Path(__file__).resolve().parents[1]
            / "plugin_assets/css/rulebook_rules_grid.css"
        ).read_text(encoding="utf-8")
        self.assertIn(".nsm-ag-group-dropzone.nsm-ag-dropzone-disabled", css)

    def test_table_drag_disabled_message_in_grid_config(self):
        grouping_py = (
            Path(__file__).resolve().parents[1] / "rulebook_rules_grouping.py"
        ).read_text(encoding="utf-8")
        rules_tab_py = (
            Path(__file__).resolve().parents[1] / "rulebook_rules_tab.py"
        ).read_text(encoding="utf-8")
        all_rules_py = (
            Path(__file__).resolve().parents[1] / "all_rules_grid_service.py"
        ).read_text(encoding="utf-8")
        self.assertIn("TABLE_DRAG_DISABLED_MESSAGE", grouping_py)
        self.assertIn("organize rules by drag-and-drop", grouping_py)
        self.assertIn('"tableDragDisabledMessage"', rules_tab_py)
        self.assertIn('"tableDragDisabledMessage"', all_rules_py)


if __name__ == "__main__":
    unittest.main()
