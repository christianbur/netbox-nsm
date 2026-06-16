"""Tests for segmented nsm_config parse/format."""

import yaml

from netbox_nsm.objects.nsm_config import (
    config_dict_from_spec,
    extract_nsm_config_from_type_comments,
    format_nsm_config_comment_yaml,
    normalize_nsm_config_list,
    parse_nsm_config_from_comments,
    resolve_object_builder_config_for_cot,
)
from netbox_nsm.objects.type_config_specs import TYPECONFIG_SPEC_BY_SLUG
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

    def test_panel_block_in_yaml_is_parsed(self):
        legacy = [
            {"rule_view": {"sort_order": 10, "display_template": "{name}"}},
            {
                "panel": {
                    "panel_linkable": True,
                    "inherit_links": True,
                    "inherit_stop_on_own": True,
                    "panel_linkable_types": ["ipam.prefix"],
                }
            },
        ]
        config = normalize_nsm_config_list(legacy)
        self.assertEqual(config["sort_order"], 10)
        self.assertEqual(config["panel"]["inherit_links"], True)

    def test_nsm_address_spec_has_no_object_builder_default(self):
        spec = TYPECONFIG_SPEC_BY_SLUG["nsm_address"]
        config = config_dict_from_spec(spec)
        self.assertNotIn("object_builder", config)
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertNotIn("object_builder:", yaml_text)

    def test_resolve_object_builder_config_without_comments(self):
        from types import SimpleNamespace

        cot = SimpleNamespace(slug="nsm_address", comments="")
        self.assertIsNone(resolve_object_builder_config_for_cot(cot))
