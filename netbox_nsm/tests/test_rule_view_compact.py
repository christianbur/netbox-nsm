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
        self.assertNotIn("display_template", zone)
        self.assertEqual(zone["areas"], [])
        self.assertEqual(zone["columns"], [])

    def test_compact_drops_default_entries(self):
        types_map = {
            "nsm_zone": {
                "rule_view": {
                    "sort_order": 10,
                    "areas": [],
                }
            },
            "nsm_service": {
                "rule_view": {
                    "sort_order": 20,
                    "areas": [],
                }
            },
        }
        self.assertEqual(compact_rulebook_types_map(types_map), {})

    def test_compact_keeps_non_default_entry(self):
        types_map = {
            "nsm_zone": {
                "rule_view": {
                    "sort_order": 99,
                    "areas": [],
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
                {"sort_order": 99},
                slug="nsm_label",
            )
        )

    def test_compact_rule_view_block_returns_none_for_default(self):
        default = default_rule_view_for_slug("nsm_action")
        self.assertIsNone(compact_rule_view_block(default, slug="nsm_action"))
