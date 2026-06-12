"""Tests for segmented nsm_config parse/format."""

import yaml

from netbox_nsm.objects.nsm_config import (
    extract_nsm_config_from_type_comments,
    format_nsm_config_comment_yaml,
    normalize_nsm_config_list,
    parse_nsm_config_from_comments,
)
from utilities.testing import TestCase


class NsmConfigFormatTests(TestCase):
    def test_format_and_parse_rule_view_block(self):
        config = {
            "sort_order": 10,
            "display_template": "{name}",
        }
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertIn("rule_view:", yaml_text)
        self.assertNotIn("panel:", yaml_text)
        parsed = parse_nsm_config_from_comments(yaml_text)
        self.assertEqual(parsed["sort_order"], 10)
        self.assertEqual(parsed["display_template"], "{name}")

    def test_extract_from_setup_type_comments(self):
        type_def = {
            "slug": "nsm_zone",
            "comments": [
                {
                    "nsm_config": [
                        {"rule_view": {"sort_order": 10, "display_template": "{name}"}},
                    ]
                }
            ],
        }
        config = extract_nsm_config_from_type_comments(type_def)
        self.assertEqual(config["sort_order"], 10)

    def test_normalize_legacy_flat_list_entry(self):
        legacy = [{"sort_order": 11, "display_template": "{name}"}]
        config = normalize_nsm_config_list(legacy)
        self.assertEqual(config["sort_order"], 11)

    def test_panel_block_in_legacy_yaml_is_ignored(self):
        legacy = [
            {"rule_view": {"sort_order": 10, "display_template": "{name}"}},
            {
                "panel": {
                    "allow_virtual_groups": True,
                    "inherit_links": True,
                    "inherit_stop_on_own": True,
                    "panel_linkable_types": ["ipam.prefix"],
                }
            },
        ]
        config = normalize_nsm_config_list(legacy)
        self.assertEqual(config, {"sort_order": 10, "display_template": "{name}"})
