"""Shared POST payloads for UI form tests."""

from utilities.testing.utils import post_data

RULEBOOK_FORM_DEFAULTS = {
    "rulebook_type": "security_rules",
    "status": "active",
    "matrix_tab_enabled": "1",
    "description": "",
    "comments": "",
}


def rulebook_post_data(**overrides):
    """Minimal valid Rulebook add/edit POST body (includes required status)."""
    payload = {**RULEBOOK_FORM_DEFAULTS, **overrides}
    return post_data(payload)
