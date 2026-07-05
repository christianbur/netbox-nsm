"""Tests for rulebook metadata in COT ``comments``."""

import yaml

from netbox_nsm.type_metadata.config import (
    _parse_nsm_config_yaml,
    format_nsm_config_comment_yaml,
)
from netbox_nsm.type_metadata.rulebook import (
    DEFAULT_RULEBOOK_CONFIG,
    format_rulebook_config_yaml,
    is_default_rulebook_config,
    merge_rulebook_config_into_comments,
    normalize_rulebook_config,
    parse_rulebook_config_from_comments,
    resolve_rulebook_config_for_cot,
    save_rulebook_config_for_cot,
)
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from utilities.testing import TestCase


class RulebookConfigFormatTests(TestCase):
    def test_defaults_when_comments_empty(self):
        config = parse_rulebook_config_from_comments("")
        self.assertEqual(config, DEFAULT_RULEBOOK_CONFIG)

    def test_is_default_rulebook_config(self):
        self.assertTrue(is_default_rulebook_config({}))
        self.assertTrue(is_default_rulebook_config(DEFAULT_RULEBOOK_CONFIG))
        self.assertFalse(
            is_default_rulebook_config({"parent_slug": "nsm_rb_global"})
        )

    def test_format_and_parse_round_trip(self):
        config = {
            "parent_slug": "nsm_rb_global",
            "matrix_tab_enabled": True,
            "row_group_by_col_id": "destination_zones::ct_2",
        }
        yaml_text = format_rulebook_config_yaml(config)
        self.assertIn("nsm_config:", yaml_text)
        self.assertIn("rulebook:", yaml_text)
        self.assertIn("parent_slug: nsm_rb_global", yaml_text)
        parsed = parse_rulebook_config_from_comments(yaml_text)
        self.assertEqual(parsed, normalize_rulebook_config(config))

    def test_format_default_returns_empty(self):
        self.assertEqual(format_rulebook_config_yaml({}), "")

    def test_normalize_applies_defaults(self):
        config = normalize_rulebook_config({"matrix_tab_enabled": False})
        self.assertEqual(config["parent_slug"], "")
        self.assertFalse(config["matrix_tab_enabled"])
        self.assertEqual(config["row_group_by_col_id"], "")

    def test_merge_rulebook_into_comments(self):
        existing = format_nsm_config_comment_yaml(
            {"sort_order": 5, "display_template": "{{ name }}"}
        )
        merged = merge_rulebook_config_into_comments(
            existing,
            {"parent_slug": "nsm_rb_parent", "matrix_tab_enabled": False},
        )
        self.assertIn("rulebook:", merged)
        parsed = parse_rulebook_config_from_comments(merged)
        self.assertEqual(parsed["parent_slug"], "nsm_rb_parent")
        self.assertFalse(parsed["matrix_tab_enabled"])
        rule_view = _parse_nsm_config_yaml(merged)
        self.assertEqual(rule_view["sort_order"], 5)

    def test_save_and_resolve_for_cot(self):
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.create(
            name="nsm_rb_cfg_test",
            slug="nsm_rb_cfg_test",
            verbose_name="Config Test",
            description="",
            group_name=RULEBOOK_GROUP,
        )
        save_rulebook_config_for_cot(
            cot,
            {
                "matrix_tab_enabled": False,
                "row_group_by_col_id": "name",
            },
        )
        resolved = resolve_rulebook_config_for_cot(cot)
        self.assertFalse(resolved["matrix_tab_enabled"])
        self.assertEqual(resolved["row_group_by_col_id"], "name")
