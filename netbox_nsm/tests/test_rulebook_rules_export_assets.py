"""Static asset checks for the rulebook Rules export button."""

from pathlib import Path
from unittest import TestCase


_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class RulebookRulesExportAssetTests(TestCase):
    def test_rules_export_uses_toml(self):
        js = (
            _PLUGIN_ROOT / "plugin_assets/js/rulebook_rules_chrome.js"
        ).read_text(encoding="utf-8")
        template = (
            _PLUGIN_ROOT
            / "templates/netbox_nsm/inc/rulebook_rules_chrome_bar.html"
        ).read_text(encoding="utf-8")

        self.assertIn("nsm-ag-toml-export", template)
        self.assertIn("Export TOML", template)
        self.assertIn("exportRulesToml", js)
        self.assertIn("application/toml", js)
        self.assertIn(".toml", js)
        self.assertIn("[[rows]]", js)
        self.assertNotIn("nsm-ag-csv-export", template)
