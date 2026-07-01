"""Shared helpers for IP Analyzer applet tests."""
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = _PLUGIN_ROOT


def ipa_js_bundle() -> str:
    """Concatenated IPA applet scripts (util → cell → core load order)."""
    names = ("nsm_ipa_util.js", "nsm_ipa_cell.js", "nsm_ip_analyzer_applet.js")
    return "\n".join(
        (_PLUGIN_ROOT / "plugin_assets/js" / name).read_text(encoding="utf-8")
        for name in names
    )


def ipa_cell_js() -> str:
    return (_PLUGIN_ROOT / "plugin_assets/js/nsm_ipa_cell.js").read_text(encoding="utf-8")
