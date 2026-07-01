"""Rules tab nav badge: filtered/total when filters are active."""

from types import SimpleNamespace

from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebooks.rules_tab import (
    format_rules_tab_badge,
    rules_tab_badge_for_object,
)
from netbox_nsm.rulebooks.virtual_cot_tabs import build_virtual_cot_rulebook_tabs


class FormatRulesTabBadgeTests(SimpleTestCase):
    def test_no_filter_shows_total_only(self):
        self.assertEqual(
            format_rules_tab_badge(62500, 62500, filter_active=False),
            62500,
        )

    def test_filter_active_shows_filtered_over_total(self):
        self.assertEqual(
            format_rules_tab_badge(120, 62500, filter_active=True),
            "120/62500",
        )

    def test_filter_active_with_zero_matches(self):
        self.assertEqual(
            format_rules_tab_badge(0, 62500, filter_active=True),
            "0/62500",
        )

    def test_filter_active_when_all_match_still_shows_ratio(self):
        self.assertEqual(
            format_rules_tab_badge(62500, 62500, filter_active=True),
            "62500/62500",
        )


class RulesTabBadgeForObjectTests(SimpleTestCase):
    def test_prefers_rules_tab_badge_over_rule_count(self):
        obj = SimpleNamespace(rules_tab_badge="12/62500", rule_count=62500)
        self.assertEqual(rules_tab_badge_for_object(obj), "12/62500")

    def test_falls_back_to_rule_count(self):
        obj = SimpleNamespace(rule_count=62500)
        self.assertEqual(rules_tab_badge_for_object(obj), 62500)

    def test_empty_rules_tab_badge_falls_back_to_rule_count(self):
        obj = SimpleNamespace(rules_tab_badge="", rule_count=42)
        self.assertEqual(rules_tab_badge_for_object(obj), 42)


class VirtualCotRulesTabBadgeTests(SimpleTestCase):
    @patch("netbox_nsm.rulebooks.virtual_cot_tabs.can_view_rulebook", return_value=True)
    def test_tabs_render_rules_tab_badge_from_instance(self, _mock_view):
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(has_perm=lambda perm: False)
        instance = SimpleNamespace(
            slug="nsm_rb_zone_matrix",
            cot=SimpleNamespace(),
            rules_tab_badge="120/62500",
            rule_count=62500,
        )
        tabs = build_virtual_cot_rulebook_tabs(
            request,
            instance,
            active_key="rules",
        )
        rules_tab = next(tab for tab in tabs if tab["key"] == "rules")
        self.assertEqual(rules_tab["badge"], "120/62500")
