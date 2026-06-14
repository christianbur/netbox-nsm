"""Tests for IP Analyzer front-end asset wiring."""

import re
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.tests.analysis._ipa_helpers import PLUGIN_ROOT, ipa_cell_js, ipa_js_bundle

_PLUGIN_ROOT = PLUGIN_ROOT


class IpAnalyzerMergeAssetsTests(SimpleTestCase):
    """Static checks for multi-tab Merge/Diff in the floating applet."""

    def test_applet_js_exposes_merge_ui(self):
        js = ipa_js_bundle()
        self.assertIn("nsm-ipa-applet-merge", js)
        self.assertIn("mergeTabs", js)
        self.assertIn("collectObjectsFromTabs", js)
        self.assertIn("collectRawObjects", js)
        self.assertIn("rawObjects", js)
        self.assertIn("Merged (", js)
        self.assertIn("scheduleBodyScale", js)
        self.assertIn("_observeBodyScaleInner", js)
        self.assertIn("host.style.width", js)
        self.assertIn("overflowX", js)
        self.assertIn("nsm-ipa-applet-body-scale", js)
        self.assertIn("loupeCellContainer", js)
        self.assertIn("collectRulesCellContext", js)
        self.assertIn("rulesCellTabTitle", js)
        self.assertIn("rulesCellContextLabel", js)
        self.assertIn("rulesCellPositionTag", js)
        self.assertIn("setRuleBadge", js)
        self.assertIn("nsm-ipa-applet-rule-badge", js)
        self.assertIn('ipaTf("Rule %(index)s/%(total)s"', js)
        self.assertIn("diffTabContextLabel", js)
        self.assertIn("contextLabel: diffTabContextLabel(sourceTabs)", js)
        self.assertIn("rulesCellDiffSideLabel", js)
        self.assertIn("diffSideLabel", js)
        self.assertIn("diffLabel", js)
        self.assertIn('ipaTf("Rule', js)

    def test_collect_cell_objects_skips_probes_when_visible_items_exist(self):
        js = ipa_cell_js()
        self.assertIn(":not(.nsm-ag-cell-item--probe)", js)
        self.assertIn("nsm-ag-cell-item--probe[data-addr-analyzable", js)

    def test_collect_cell_objects_prefers_probes_for_merged_type_groups(self):
        js = ipa_cell_js()
        self.assertIn('cell.classList.contains("nsm-ag-cell-merged")', js)
        self.assertIn("Polymorphic merged cells", js)

    def test_cell_js_reads_rules_page_totals(self):
        js = ipa_cell_js()
        self.assertIn("readRulesPageTotals", js)
        self.assertIn('getElementById("rules")', js)
        self.assertIn("data-rules-total-rules", js)
        self.assertIn("data-rules-unfiltered-total", js)
        self.assertIn("enrichRulesCellContext", js)

    def test_util_exposes_rule_position_tag(self):
        js = ipa_js_bundle()
        self.assertIn("rulesCellTotalRules", js)
        self.assertIn("rulesUnfilteredTotal", js)
        self.assertIn('ipaTf("Rule %(index)s/%(total)s"', js)

    def test_applet_css_styles_rule_badge_in_header(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ipa-applet-rule-badge", css)

    def test_applet_js_exposes_diff_ui(self):
        js = ipa_js_bundle()
        self.assertIn("nsm-ipa-applet-diff", js)
        self.assertIn("diffTabs", js)
        self.assertIn("buildDiffQuery", js)
        self.assertIn("diffTabTitleFromTabs", js)
        self.assertIn("diffRulesSideShortLabel", js)
        self.assertIn('Diff %(a)s - %(b)s', js)
        self.assertIn("ruleIndex + \"/\" + colPosition", js)
        self.assertIn("formatDiffSummary", js)
        self.assertIn("tab.sides", js)
        self.assertIn('mode", "diff"', js)
        self.assertIn("Diff (", js)
        self.assertIn('return tab.mode !== "diff"', js)
        self.assertIn("this.tabs.push(diffTab)", js)
        self.assertNotIn("this.tabs = [diffTab]", js)
        self.assertIn('ipaT("Diff (at least 2 tabs required)")', js)
        self.assertNotIn("var canDiff = this.tabs.length === 2", js)
        self.assertIn("Fund:", js)
        self.assertIn("nsm-ipa-applet-toolbar", js)
        self.assertIn("nsm-ipa-applet-toolbar-actions", js)
        self.assertIn("nsm-ipa-applet-add-object", js)
        self.assertIn('ipaT("Add object")', js)
        self.assertIn("_pickAddObject", js)
        self.assertIn("addObjectTypesApiUrl", js)
        self.assertIn('ipaT("Enter search term…")', js)
        self.assertNotIn("_loadAllAddObjectType", js)
        self.assertNotIn("_fetchAllAddObjectType", js)
        self.assertNotIn("nsm-ipa-applet-add-load-all", js)
        self.assertNotIn('ipaTf("Load all %(type)s"', js)

    def test_applet_js_exposes_yaml_export_ui(self):
        js = ipa_js_bundle()
        self.assertIn("nsm-ipa-applet-export", js)
        self.assertIn("exportYaml", js)
        self.assertIn("buildExportQuery", js)
        self.assertIn("triggerBlobDownload", js)
        self.assertIn('ipaT("Export YAML")', js)
        self.assertIn('ipaT("YAML export failed.")', js)
        self.assertIn("_exporting", js)
        self.assertIn("nsm-ipa-applet-add-modal", js)

    def test_applet_css_integrates_object_tree_in_addr_children(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ipa-applet .nsm-addr-children .nsm-ipa-object-tree-rows", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-subnet-contained", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-subnet-contained\s*\{[^}]*font-size:\s*inherit",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-pill-link--inactive", css)
        self.assertIn(".nsm-ipa-applet .nsm-object-status-icon--deprecated", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill:has\(\.nsm-object-status-icon--deprecated\)\s*\{"
            r"[^}]*border:\s*1px solid #dc3545",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node--subnet-warning", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node--doppelt-warning", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-expanded-warnings", css)
        self.assertIn("display: none !important", css)
        self.assertIn('content: "▶"', css)
        self.assertIn("details[open] > .nsm-addr-summary::before", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-children\s*\{[^}]*border-left:",
        )
        self.assertNotIn(".nsm-ipa-applet .nsm-ipa-tree-dots", css)
        self.assertNotIn(".nsm-ipa-object-tree-title", css)
        self.assertNotIn(".nsm-ipa-object-tree {", css)
        self.assertNotIn(".nsm-ipa-object-tree-dots", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-pill", css)
        self.assertIn("--nsm-ipa-cell-pill-bg", css)
        self.assertIn("--nsm-ipa-cell-pill-text", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*background:\s*var\(--nsm-ipa-cell-pill-bg\)",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-ipa-cell-pill-link\s*\{[^}]*color:\s*var\(--nsm-ipa-cell-pill-text\)",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-diff-name-pill .nsm-ipa-diff-name-a", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-diff-name-pill .nsm-ipa-diff-name-b", css)
        self.assertIn("var(--nsm-ipa-accent)", css)
        self.assertNotIn("border-left: 3px solid var(--nsm-ipa-accent)", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-addr-drilldown .nsm-addr-summary", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-object-row", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-drilldown-meta--info", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-pill--parent", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill--parent \.nsm-ipa-cell-pill-link,\s*"
            r"[^}]*color:\s*var\(--bs-warning",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-drilldown-meta-info-stat", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet summary\.nsm-ipa-drilldown-source-summary\s*\{[^}]*align-items:\s*flex-start",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-addr-leaf-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node > \.nsm-addr-summary\s*\{[^}]*padding:\s*1px 0",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node", css)
        self.assertIn("gap: 0", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-addr-leaf-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node > \.nsm-addr-summary\s*\{[^}]*line-height:\s*1\.2;",
        )
        self.assertIn(
            ".nsm-ipa-applet .nsm-addr-children .nsm-ipa-object-tree-rows > details.nsm-ipa-object-node + details.nsm-ipa-object-node",
            css,
        )
        self.assertIn("margin-top: 2px", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*display:\s*inline-flex",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*padding:\s*0\.12rem 0\.38rem 0\.14rem",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*flex-direction:\s*column",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-pill-body--stack", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-object-row-main", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-object-row-main > \.nsm-ipa-cell-pill--group\s*\{[^}]*grid-column:\s*3",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-object-row-main > \.nsm-ipa-cell-pill--parent\s*\{[^}]*grid-column:\s*4",
        )
        self.assertIn(
            ".nsm-ipa-applet .nsm-addr-leaf:has(> .nsm-ipa-cell-object-row-main)",
            css,
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary::before,\s*"
            r"\.nsm-ipa-applet \.nsm-addr-leaf-summary::before\s*\{[^}]*align-self:\s*center",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary:has\(\.nsm-ipa-cell-pill-body--stack\)[^}]*align-items:\s*center",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*align-self:\s*stretch",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-addr-link,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-addr-obj-link,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-ipa-cell-pill-link\s*\{[^}]*margin:\s*0",
        )

    def test_address_and_group_pill_links_truncate_with_ellipsis(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill--address \.nsm-ipa-cell-pill-link,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill--group \.nsm-ipa-cell-pill-link\s*\{"
            r"[^}]*text-overflow:\s*ellipsis",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-object-row-main > \.nsm-ipa-cell-pill--address,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-cell-object-row-main > \.nsm-ipa-cell-pill--group\s*\{"
            r"[^}]*min-width:\s*0",
        )

    def test_subnet_warning_pill_uses_warning_text_and_border(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill--address\.nsm-ipa-cell-pill--multi\s*\{"
            r"[^}]*border:\s*1px solid var\(--bs-warning,\s*var\(--tblr-warning,\s*#f59f0a\)\) !important",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill--group\.nsm-ipa-cell-pill--multi\s*\{"
            r"[^}]*border:\s*1px solid var\(--bs-warning,\s*var\(--tblr-warning,\s*#f59f0a\)\) !important",
        )
        self.assertNotIn(
            ".nsm-ipa-applet .nsm-ipa-object-node--subnet-warning .nsm-ipa-cell-pill {",
            css,
        )
        self.assertNotIn(
            ".nsm-ipa-object-node--subnet-warning .nsm-ipa-cell-pill .nsm-ipa-cell-pill-link",
            css,
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-addr-ip",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-addr-prefix-text",
        )

    def test_diff_status_badges_use_solid_contrast(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_assets.html"
        ).read_text(encoding="utf-8")
        for source in (css, assets):
            self.assertRegex(
                source,
                r"\.nsm-addr-diff--only_a[^}]*background-color:\s*var\(--bs-primary",
            )
            self.assertRegex(
                source,
                r"\.nsm-addr-diff--only_b[^}]*background-color:\s*var\(--bs-success",
            )
            self.assertIn("color: #fff", source)
            self.assertIn("--bs-badge-color: #fff", source)

    def test_applet_css_toolbar_above_tabs(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ipa-applet-toolbar", css)
        self.assertIn(".nsm-ipa-applet-toolbar-actions", css)
        self.assertIn(".nsm-ipa-applet-add-object", css)
        self.assertIn(".nsm-ipa-applet-add-modal", css)
        self.assertNotIn(".nsm-ipa-applet-add-type-actions", css)
        self.assertNotIn(".nsm-ipa-applet-add-load-all", css)
        self.assertIn(".nsm-ipa-applet--has-toolbar", css)

    @patch("netbox_nsm.analysis.ipa_add_object_types.get_api_url_for_content_type")
    @patch("netbox_nsm.analysis.ipa_add_object_types.ContentType")
    def test_build_ipa_add_object_categories_includes_ipam_and_cot(
        self, content_type_cls, api_url_fn
    ):
        from netbox_nsm.analysis.ipa_add_object_types import build_ipa_add_object_categories

        prefix_ct = MagicMock(pk=11)
        addr_ct = MagicMock(pk=22)
        group_ct = MagicMock(pk=33)

        def get_ct(app_label, model):
            ct = MagicMock()
            if (app_label, model) == ("ipam", "prefix"):
                ct.pk = 11
            elif (app_label, model) == ("ipam", "ipaddress"):
                ct.pk = 12
            elif (app_label, model) == ("ipam", "iprange"):
                ct.pk = 13
            elif app_label == "netbox_custom_objects" and model == "table7model":
                ct.pk = 22
            elif app_label == "netbox_custom_objects" and model == "table8model":
                ct.pk = 33
            else:
                raise content_type_cls.DoesNotExist
            return ct

        content_type_cls.objects.get.side_effect = get_ct
        content_type_cls.DoesNotExist = Exception
        api_url_fn.side_effect = lambda ct: f"/api/example/{ct.pk}/"

        cot_address = MagicMock(pk=7, slug="nsm_address")
        cot_group = MagicMock(pk=8, slug="nsm_address_group")

        with patch(
            "netbox_custom_objects.models.CustomObjectType.objects.filter"
        ) as cot_filter:
            cot_filter.return_value.only.return_value.first.side_effect = [
                cot_address,
                cot_group,
            ]
            categories = build_ipa_add_object_categories()

        self.assertEqual([cat["id"] for cat in categories], ["ipam", "nsm_address", "nsm_address_group"])
        self.assertEqual(len(categories[0]["types"]), 3)
        self.assertEqual(categories[1]["types"][0]["ct_id"], 22)
        self.assertEqual(categories[2]["types"][0]["ct_id"], 33)

    def test_rules_templates_expose_total_rules_data_attrs(self):
        for name in ("rulebook_cot_rules.html", "rulebook_all_rules_rules.html"):
            html = (
                _PLUGIN_ROOT / "templates/netbox_nsm" / name
            ).read_text(encoding="utf-8")
            self.assertIn('id="rules"', html)
            self.assertIn("data-rules-total-rules=", html)
            self.assertIn("data-rules-unfiltered-total=", html)
            self.assertIn("{{ rules_total_rules }}", html)
            self.assertIn("{{ rules_unfiltered_total }}", html)

    def test_applet_body_enables_ipa_cell_pills_for_diff(self):
        body = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_applet_body.html"
        ).read_text(encoding="utf-8")
        self.assertIn("ipa_cell_pill=True", body)
        self.assertIn('prefix="ipa"', body)

    def test_applet_assets_cache_bust_bumped(self):
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/nsm_ip_analyzer_applet_assets.html"
        ).read_text(encoding="utf-8")
        self.assertIn("nsm_ip_analyzer_applet.js", assets)
        self.assertIn("nsm_ipa_util.js", assets)
        self.assertIn("nsm_ipa_cell.js", assets)
        self.assertIn("?v=202606200", assets)
        self.assertIn("NSM_IP_ANALYSIS_ADD_OBJECT_TYPES_API", assets)

    def test_merged_cell_loupe_corner_hover_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/rulebook_rules.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ag-cell-merged--has-loupe > .nsm-ipa-cell-loupe", css)
        self.assertIn("left: auto", css)
        self.assertIn(
            ".nsm-ag-cell-merged--has-loupe:hover > .nsm-ipa-cell-loupe", css
        )

    def test_expanded_cell_loupe_corner_hover_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/rulebook_rules.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ag-cell-list--has-loupe > .nsm-ipa-cell-loupe", css)
        self.assertIn(
            "td.nsm-rules-td--object:has(.nsm-ag-cell-list--has-loupe)",
            css,
        )
        self.assertIn(
            ".nsm-ag-cell-list--has-loupe:hover > .nsm-ipa-cell-loupe", css
        )
        self.assertIn(
            "tbody td.nsm-rules-td--object:hover .nsm-ag-cell-list--has-loupe > .nsm-ipa-cell-loupe",
            css,
        )

    def test_rules_filter_loupe_corner_hover_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/rulebook_rules.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            ".nsm-rules-filter-target--has-loupe > .nsm-rules-filter-loupe", css
        )
        self.assertIn(
            ".nsm-rules-filter-target--has-loupe:hover > .nsm-rules-filter-loupe",
            css,
        )
        self.assertIn(
            "tbody td:hover .nsm-rules-filter-target--has-loupe > .nsm-rules-filter-loupe",
            css,
        )
        self.assertIn(
            ":has(.nsm-rules-filter-loupe:hover) > .nsm-rules-filter-loupe",
            css,
        )
        self.assertIn(".nsm-rules-filter-loupe .mdi", css)
        self.assertNotIn("grid-template-columns: minmax(0, max-content) 0", css)

    def test_rules_filter_target_html_has_loupe_class(self):
        from netbox_nsm.rulebooks.cell_html import rules_filter_target_html

        html = rules_filter_target_html("Example", "Example")
        self.assertIn("nsm-rules-filter-target--has-loupe", html)
        self.assertIn("nsm-rules-filter-loupe", html)

    def test_cell_loupe_list_position_scoped_in_applet_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ag-cell-list--has-loupe > .nsm-ipa-cell-loupe", css)
        self.assertNotRegex(
            css,
            r"(?<!\.)nsm-ipa-cell-loupe\s*\{[^}]*position:\s*absolute",
        )

    def test_fetch_object_drilldown_hides_empty_html_container(self):
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_assets.html"
        ).read_text(encoding="utf-8")
        self.assertIn("function fetchObjectDrilldown", assets)
        self.assertIn("container.hidden = true", assets)
        self.assertRegex(
            assets,
            r"var html = String\(data\.html \|\| ''\)\.trim\(\);\s*if \(!html\)",
        )

    def test_applet_css_includes_diff_fund_row_styles(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_assets.html"
        ).read_text(encoding="utf-8")
        for source in (css, assets):
            self.assertIn(".nsm-addr-diff-fund-row", source)
            self.assertIn(".nsm-addr-diff-fund-network", source)

