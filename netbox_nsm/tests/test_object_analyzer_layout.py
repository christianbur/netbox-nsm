"""Static checks for Object Analyzer full-height graph layout."""

from pathlib import Path

from django.test import SimpleTestCase

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class ObjectAnalyzerLayoutTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = (
            _PLUGIN_ROOT / "templates/netbox_nsm/object_analyzer.html"
        ).read_text(encoding="utf-8")

    def test_graph_fills_viewport_via_flex_chain(self):
        html = self.html
        self.assertIn("nsm-oa-layout", html)
        self.assertRegex(
            html,
            r"\.page-wrapper:has\(#nsm-oa-graph\)\s*\{[^}]*min-height:\s*100dvh;",
        )
        self.assertRegex(
            html,
            r"#nsm-oa-graph\s*\{[^}]*flex:\s*1\s+1\s+auto;[^}]*min-height:\s*0|"
            r"#nsm-oa-graph\s*\{[^}]*flex:\s*1\s+1\s+auto;[^}]*min-height:\s*12rem;",
        )
        self.assertNotRegex(html, r"#nsm-oa-graph\s*\{[^}]*height:\s*700px;")
        self.assertRegex(
            html,
            r"\.nsm-oa-graph-wrap \.react-flow\s*\{[^}]*height:\s*100%;",
        )
        self.assertRegex(
            html,
            r"\.nsm-oa-graph-wrap\s*\{[^}]*position:\s*absolute;[^}]*inset:\s*0;",
        )
        self.assertIn("BackgroundVariant.Dots", html)
        self.assertIn("colorMode: oaThemeMode", html)
        self.assertIn("bgColor: oaCanvas.bg", html)

    def test_cloud_expand_skips_nodes_already_on_canvas(self):
        html = self.html
        self.assertIn("function rebuildCloudData(", html)
        self.assertIn("nodeId.startsWith('cloud:')", html)
        self.assertRegex(
            html,
            r"if \(canvasIds\.has\(cid\)\) return;",
        )
        self.assertRegex(
            html,
            r"if \(canvasIds\.has\(tgt\)\) return;",
        )

    def test_link_picker_hides_existing_parent_edges(self):
        html = self.html
        self.assertIn("function filterPickerChildrenForCanvas(", html)
        self.assertIn("function filterPickerTreeForCanvas(", html)
        self.assertIn("filterPickerTreeForCanvas(d1raw, nodeId, edgeKeys)", html)
        self.assertIn("linked_neighbor_ids", html)
        self.assertIn("linked.has(l2c.node.id)", html)
        self.assertRegex(
            html,
            r"pickerEdgeKey\(targetId, parentId\)",
        )

    def test_mode_selector_and_api_param(self):
        html = self.html
        self.assertIn('id="nsm-oa-mode-group"', html)
        self.assertIn('class="btn-group btn-group-sm nsm-oa-mode-selector', html)
        self.assertIn('name="mode"', html)
        self.assertIn('id="nsm-oa-mode-all"', html)
        self.assertIn('id="nsm-oa-mode-security"', html)
        self.assertIn('data-mode="{{ sel_mode }}"', html)
        self.assertIn("&mode=${encodeURIComponent(mode || 'all')}", html)
        self.assertIn("nsm_oa_mode", html)
        self.assertIn("formEl.submit()", html)

    def test_mode_specific_ui_copy(self):
        html = self.html
        self.assertIn("{{ search_placeholder }}", html)
        self.assertIn("{{ empty_title }}", html)
        self.assertIn("{{ empty_subtitle }}", html)
        self.assertIn("{% if mode_hint %}", html)
        self.assertIn("nsm-oa-mode-hint", html)
        self.assertNotIn("Select object · + opens link tree", html)
        self.assertNotIn('id="nsm-oa-mode"', html)
        self.assertNotIn("<select", html)

    def test_tree_layout_guards_against_cycles(self):
        html = self.html
        self.assertRegex(
            html,
            r"function subtreeH\(id, visiting\)",
        )
        self.assertRegex(
            html,
            r"if \(visiting\.has\(id\)\) return NODE_H;",
        )
        self.assertRegex(
            html,
            r"function getAllDescendants\(id, visited\)",
        )
        self.assertRegex(
            html,
            r"if \(visited\.has\(id\)\) return \[\];",
        )
