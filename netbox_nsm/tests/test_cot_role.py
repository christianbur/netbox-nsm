"""Tests for COT metadata role."""

from types import SimpleNamespace

from netbox_nsm.objects.nsm_config import (
    format_nsm_config_comment_yaml,
    merge_nsm_config_document_into_comments,
    parse_nsm_config_document_from_comments,
)
from netbox_nsm.rulebooks.registry import is_deployed_rulebook_cot, iter_deployed_cot_rulebooks
from netbox_nsm.type_metadata.roles import (
    default_role_for_slug,
    parse_role_from_comments,
    resolve_role_for_cot,
)
from utilities.testing import TestCase


class CotRoleMetadataTests(TestCase):
    def test_default_role_for_policy_slugs(self):
        self.assertEqual(default_role_for_slug("nsm_zone"), "zone")
        self.assertEqual(default_role_for_slug("nsm_address"), "address")
        self.assertEqual(default_role_for_slug("nsm_rb_demo"), "rulebook")

    def test_role_segment_round_trip(self):
        yaml_text = merge_nsm_config_document_into_comments(
            "",
            {
                "role": "rulebook",
                "rule_view": {"sort_order": 0, "display_template": "{{ name }}"},
            },
        )
        self.assertIn("- role: rulebook", yaml_text)
        self.assertEqual(parse_role_from_comments(yaml_text), "rulebook")
        doc = parse_nsm_config_document_from_comments(yaml_text)
        self.assertEqual(doc.get("role"), "rulebook")

    def test_format_policy_config_includes_role(self):
        yaml_text = format_nsm_config_comment_yaml(
            {
                "sort_order": 10,
                "display_template": "{{ name }}",
                "role": "zone",
                "links": {"linkable": True},
            }
        )
        self.assertIn("- role: zone", yaml_text)
        self.assertEqual(parse_role_from_comments(yaml_text), "zone")

    def test_resolve_role_from_comments_overrides_slug_default(self):
        cot = SimpleNamespace(
            slug="nsm_zone",
            comments=merge_nsm_config_document_into_comments("", {"role": "label"}),
        )
        self.assertEqual(resolve_role_for_cot(cot), "label")

    def test_is_deployed_rulebook_cot_uses_role(self):
        cot = SimpleNamespace(slug="custom_rb_prod", comments="")
        self.assertFalse(is_deployed_rulebook_cot(cot))
        cot.comments = merge_nsm_config_document_into_comments("", {"role": "rulebook"})
        self.assertTrue(is_deployed_rulebook_cot(cot))

    def test_iter_deployed_rulebooks_is_query_safe(self):
        list(iter_deployed_cot_rulebooks())
