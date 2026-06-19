"""Static checks for rules panel scroll container layout."""

from pathlib import Path

from django.test import SimpleTestCase

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class RulebookRulesScrollLayoutTests(SimpleTestCase):
    def test_rules_body_is_flex_scroll_container(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/rulebook_rules.css").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            css,
            r"#rules \.nsm-rules-body\s*\{[^}]*display:\s*flex;[^}]*flex-direction:\s*column;[^}]*overflow:\s*hidden;",
        )
        self.assertRegex(
            css,
            r"#rules \.htmx-container\.nsm-rules-table-scroll\s*\{[^}]*overflow:\s*auto;",
        )
        self.assertRegex(
            css,
            r"#rules \.nsm-rules-body\.nsm-rules-body--with-side-tabs \.nsm-rules-table-scroll\s*\{[^}]*min-height:\s*0;",
        )
        self.assertRegex(
            css,
            r"#rules \.nsm-rules-body\.nsm-rules-body--with-side-tabs\s*\{[^}]*flex-direction:\s*row;",
        )
        self.assertRegex(
            css,
            r"#rules\.card\s*\{[^}]*overflow:\s*hidden;",
        )

    def test_sidebar_height_sync_uses_viewport_not_table_content(self):
        js = (
            _PLUGIN_ROOT / "plugin_assets/js/rulebook_rules_row_group.js"
        ).read_text(encoding="utf-8")
        self.assertIn("var height = body.clientHeight;", js)
        self.assertNotIn("tableScroll.offsetHeight", js)
        self.assertIn("observer.observe(body);", js)

    def test_rules_templates_bump_scroll_asset_cache(self):
        for template_name in (
            "rulebook_cot_rules.html",
            "rulebook_all_rules_rules.html",
        ):
            html = (
                _PLUGIN_ROOT / "templates/netbox_nsm" / template_name
            ).read_text(encoding="utf-8")
            self.assertRegex(
                html,
                r"css/rulebook_rules\.css' %\}\?v=20260617e",
            )
            self.assertRegex(
                html,
                r"js/rulebook_rules_row_group\.js' %\}\?v=20260617e",
            )
