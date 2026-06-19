"""Static asset checks for the rulebook rules-table TOML export (CSV → TOML).

Scale-safe: reads the shipped template/JS files only, no DB or HTTP. Guards the
CSV→TOML migration of the visible-rules export button and writer so the button
id, MIME type, document format marker, and ``.toml`` filename do not silently
regress back to CSV.
"""

from pathlib import Path

from django.test import SimpleTestCase

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _chrome_bar_template() -> str:
    return (
        _PLUGIN_ROOT
        / "templates/netbox_nsm/inc/rulebook_rules_chrome_bar.html"
    ).read_text(encoding="utf-8")


def _chrome_js() -> str:
    return (
        _PLUGIN_ROOT / "plugin_assets/js/rulebook_rules_chrome.js"
    ).read_text(encoding="utf-8")


class RulesTomlExportTemplateTests(SimpleTestCase):
    def test_chrome_bar_offers_toml_export_button(self):
        html = _chrome_bar_template()
        self.assertIn('id="nsm-ag-toml-export"', html)
        self.assertIn("Export TOML", html)
        self.assertIn("Export visible data as TOML", html)

    def test_chrome_bar_has_no_csv_export(self):
        html = _chrome_bar_template()
        self.assertNotIn("Export CSV", html)
        self.assertNotIn("nsm-ag-csv-export", html)


class RulesTomlExportJsTests(SimpleTestCase):
    def test_js_exports_toml_writer(self):
        js = _chrome_js()
        self.assertIn("function exportRulesToml", js)
        self.assertIn('getElementById("nsm-ag-toml-export")', js)
        self.assertIn("application/toml", js)
        self.assertIn('"netbox-nsm-rules-visible-v1"', js)
        self.assertIn('".toml"', js)

    def test_js_has_no_csv_export_remnants(self):
        js = _chrome_js()
        self.assertNotIn("exportRulesCsv", js)
        self.assertNotIn("text/csv", js)
