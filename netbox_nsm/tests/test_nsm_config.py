"""Tests for segmented nsm_config parse/format."""

import yaml

from netbox_nsm.type_metadata.config import (
    config_dict_from_spec,
    extract_nsm_config_from_type_comments,
    format_nsm_config_comment_yaml,
    normalize_nsm_config_list,
    parse_nsm_config_from_comments,
)
from netbox_nsm.type_metadata.specs import TYPECONFIG_SPEC_BY_SLUG
from utilities.testing import TestCase


class NsmConfigFormatTests(TestCase):
    def test_format_and_parse_rule_view_block(self):
        config = {
            "sort_order": 10,
            "display_template": "{{ name }}",
        }
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertIn("rule_view:", yaml_text)
        self.assertNotIn("- panel:", yaml_text)
        parsed = parse_nsm_config_from_comments(yaml_text)
        self.assertEqual(parsed["sort_order"], 10)
        self.assertEqual(parsed["display_template"], "{{ name }}")

    def test_extract_from_setup_type_comments(self):
        type_def = {
            "slug": "nsm_zone",
            "comments": [
                {
                    "nsm_config": [
                        {"rule_view": {"sort_order": 10, "display_template": "{{ name }}"}},
                    ]
                }
            ],
        }
        config = extract_nsm_config_from_type_comments(type_def)
        self.assertEqual(config["sort_order"], 10)

    def test_normalize_legacy_flat_list_entry(self):
        legacy = [{"sort_order": 11, "display_template": "{{ name }}"}]
        config = normalize_nsm_config_list(legacy)
        self.assertEqual(config["sort_order"], 11)

    def test_normalize_link_table_segment(self):
        raw = [{"link_table": True}]
        config = normalize_nsm_config_list(raw)
        self.assertTrue(config["link_table"])

    def test_merge_link_table_into_comments(self):
        from netbox_nsm.type_metadata.config import merge_nsm_config_document_into_comments

        comments = merge_nsm_config_document_into_comments("", {"link_table": True})
        parsed = parse_nsm_config_from_comments(comments)
        self.assertTrue(parsed["link_table"])

    def test_legacy_links_block_is_ignored(self):
        legacy = [
            {"rule_view": {"sort_order": 10, "display_template": "{{ name }}"}},
            {
                "links": {
                    "linkable": True,
                    "inherit_links": True,
                    "inherit_stop_on_own": True,
                }
            },
        ]
        config = normalize_nsm_config_list(legacy)
        self.assertEqual(config["sort_order"], 10)
        self.assertNotIn("links", config)

    def test_nsm_address_spec_has_no_links_block(self):
        spec = TYPECONFIG_SPEC_BY_SLUG["nsm_address"]
        config = config_dict_from_spec(spec)
        self.assertNotIn("links", config)
        self.assertNotIn("object_builder", config)
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertNotIn("object_builder:", yaml_text)
        self.assertNotIn("- links:", yaml_text)

    def test_formatted_output_uses_markdown_fences(self):
        config = {
            "sort_order": 22,
            "display_template": "{{ name }}",
            "areas": ["srcdst"],
            "role": "app_network",
        }
        yaml_text = format_nsm_config_comment_yaml(config)
        self.assertTrue(yaml_text.startswith("```\n"))
        self.assertTrue(yaml_text.endswith("```\n"))
        self.assertNotIn("```yaml", yaml_text)
        self.assertIn("nsm_config:", yaml_text)
        self.assertIn("- role: app_network", yaml_text)

    def test_parse_fenced_and_unfenced_comments(self):
        config = {
            "sort_order": 10,
            "display_template": "{{ name }}",
        }
        fenced = format_nsm_config_comment_yaml(config)
        unfenced = (
            yaml.dump(
                {"nsm_config": [{"rule_view": {"sort_order": 10, "display_template": "{{ name }}"}}]},
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ).rstrip()
            + "\n"
        )
        for text in (fenced, unfenced):
            parsed = parse_nsm_config_from_comments(text)
            self.assertEqual(parsed["sort_order"], 10)
            self.assertEqual(parsed["display_template"], "{{ name }}")

    def test_format_includes_menu_when_present(self):
        yaml_text = format_nsm_config_comment_yaml(
            {
                "sort_order": 0,
                "display_template": "{{ name }}",
                "menu": "objects",
            }
        )
        self.assertIn("- menu: objects", yaml_text)
        parsed = parse_nsm_config_from_comments(yaml_text)
        self.assertIsNone(parsed.get("menu"))
        from netbox_nsm.type_metadata.menus import parse_menu_from_comments

        self.assertEqual(parse_menu_from_comments(yaml_text), "objects")
