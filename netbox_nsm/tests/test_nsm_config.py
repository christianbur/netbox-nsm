"""Tests for segmented nsm_config parse/format."""

from types import SimpleNamespace

import yaml

from netbox_nsm.security.tab.cot_metadata import cot_link_table_flag
from netbox_nsm.type_metadata.config import (
    _parse_nsm_config_yaml,
    config_dict_from_metadata_block,
    extract_nsm_config_from_type_comments,
    format_nsm_config_comment_yaml,
    has_nsm_config_in_comments,
    metadata_block_for_cot_slug,
    normalize_nsm_config_list,
    parse_nsm_config_from_cot,
    resolve_nsm_config_dict_for_cot,
)
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
        parsed = _parse_nsm_config_yaml(yaml_text)
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
        parsed = _parse_nsm_config_yaml(comments)
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

    def test_bundle_address_metadata_has_no_links_block(self):
        block = metadata_block_for_cot_slug("nsm_address")
        self.assertIsNotNone(block)
        config = config_dict_from_metadata_block(block)
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
            parsed = _parse_nsm_config_yaml(text)
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
        parsed = _parse_nsm_config_yaml(yaml_text)
        self.assertIsNone(parsed.get("menu"))
        from netbox_nsm.type_metadata.menus import parse_menu_from_comments

        self.assertEqual(parse_menu_from_comments(yaml_text), "objects")

    def test_parse_nsm_config_ignores_invalid_yaml_comments(self):
        tufin_like = (
            "xyp4.eurexchmge.com | TufinType: host | TufinID: 1353 | AppID: 999"
        )
        self.assertIsNone(_parse_nsm_config_yaml(tufin_like))
        self.assertFalse(has_nsm_config_in_comments(tufin_like))

    def test_parse_nsm_config_from_cot_type_works(self):
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.create(
            name="nsm_test_type",
            slug="nsm_test_type",
            verbose_name="Test Type",
            description="",
            comments=format_nsm_config_comment_yaml(
                {
                    "sort_order": 42,
                    "display_template": "{{ name }}",
                }
            ),
        )
        parsed = parse_nsm_config_from_cot(cot)
        self.assertEqual(parsed["sort_order"], 42)
        self.assertEqual(parsed["display_template"], "{{ name }}")

    def test_parse_nsm_config_from_custom_object_instance_is_skipped(self):
        from netbox_nsm.addresses.address_cot_schema import object_builder_in_nsm_config

        tufin_like = (
            "xyp4.eurexchmge.com | TufinType: host | TufinID: 1353 | AppID: 999"
        )
        instance = SimpleNamespace(
            comments=tufin_like,
            slug="nsm_address",
            custom_object_type=SimpleNamespace(slug="nsm_address"),
        )
        self.assertIsNone(parse_nsm_config_from_cot(instance))
        self.assertIsNone(resolve_nsm_config_dict_for_cot(instance))
        self.assertFalse(object_builder_in_nsm_config(instance))
        self.assertFalse(cot_link_table_flag(instance))

    def test_parse_nsm_config_skips_ipam_object_comments(self):
        from ipam.models import Prefix

        tufin_like = (
            "network-3.65.246.96-29 | TufinType: subnet | TufinID: 1684006"
        )
        prefix = Prefix(prefix="3.65.246.96/29", status="active", comments=tufin_like)
        self.assertIsNone(parse_nsm_config_from_cot(prefix))
        self.assertIsNone(resolve_nsm_config_dict_for_cot(prefix))

    def test_resolve_menu_for_cot_ignores_instance_comments(self):
        from netbox_nsm.type_metadata.menus import resolve_menu_for_cot

        tufin_like = (
            "network-3.65.246.96-29 | TufinType: subnet | TufinID: 1684006"
        )
        instance = SimpleNamespace(
            comments=tufin_like,
            slug="nsm_address",
            custom_object_type=SimpleNamespace(slug="nsm_address"),
        )
        self.assertIsNone(resolve_menu_for_cot(instance))
