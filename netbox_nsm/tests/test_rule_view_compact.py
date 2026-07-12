"""Tests for rulebook rule_view default compaction in nsm_config."""

from django.test import SimpleTestCase

from netbox_nsm.type_metadata.rule_view import (
    compact_rulebook_types_map,
    compact_rule_view_block,
    default_rule_view_for_slug,
    is_default_rule_view_config,
)


class RuleViewCompactTests(SimpleTestCase):
    def test_default_rule_view_matches_spec(self):
        zone = default_rule_view_for_slug("nsm_zone")
        self.assertEqual(zone["sort_order"], 10)
        self.assertEqual(zone["display_template"], "{{ name }}")
        self.assertEqual(zone["areas"], ["srcdst"])
        self.assertEqual(zone["columns"], [])

    def test_compact_drops_default_entries(self):
        types_map = {
            "nsm_zone": {
                "rule_view": {
                    "sort_order": 10,
                    "display_template": "{{ name }}",
                    "areas": ["srcdst"],
                }
            },
            "nsm_service": {
                "rule_view": {
                    "sort_order": 20,
                    "display_template": "{{ name }} ({{ protocol }}/{{ port }})",
                    "areas": ["services"],
                }
            },
        }
        self.assertEqual(compact_rulebook_types_map(types_map), {})

    def test_compact_keeps_non_default_entry(self):
        types_map = {
            "nsm_zone": {
                "rule_view": {
                    "sort_order": 99,
                    "display_template": "{{ name }}",
                    "areas": ["srcdst"],
                }
            }
        }
        self.assertEqual(
            compact_rulebook_types_map(types_map),
            {"nsm_zone": {"rule_view": {"sort_order": 99}}},
        )

    def test_is_default_rule_view_config(self):
        default = default_rule_view_for_slug("nsm_label")
        self.assertTrue(is_default_rule_view_config(default, slug="nsm_label"))
        self.assertFalse(
            is_default_rule_view_config(
                {"display_template": "{{ name }}"},
                slug="nsm_label",
            )
        )

    def test_compact_rule_view_block_returns_none_for_default(self):
        default = default_rule_view_for_slug("nsm_action")
        self.assertIsNone(compact_rule_view_block(default, slug="nsm_action"))
