"""Tests for COT metadata menu bucket."""

from types import SimpleNamespace

from netbox_nsm.objects.cot_routes import (
    cot_belongs_to_nsm_objects_menu,
    is_nsm_object_menu_slug,
)
from netbox_nsm.objects.nsm_config import merge_nsm_config_document_into_comments
from netbox_nsm.type_metadata.menus import (
    default_menu_for_slug,
    group_name_for_menu,
    parse_menu_from_comments,
    resolve_menu_for_cot,
)
from utilities.testing import TestCase


class CotMenuMetadataTests(TestCase):
    def test_default_menu_for_policy_slugs(self):
        self.assertEqual(default_menu_for_slug("nsm_zone"), "objects")
        self.assertEqual(default_menu_for_slug("nsm_object_link"), "links")
        self.assertEqual(default_menu_for_slug("nsm_rb_zone_matrix"), "rulebooks")

    def test_menu_segment_round_trip(self):
        yaml_text = merge_nsm_config_document_into_comments(
            "",
            {"menu": "objects", "role": "zone"},
        )
        self.assertTrue(yaml_text.startswith("```\n"))
        self.assertIn("- menu: objects", yaml_text)
        self.assertEqual(parse_menu_from_comments(yaml_text), "objects")

    def test_resolve_menu_from_comments_overrides_slug_default(self):
        cot = SimpleNamespace(
            slug="nsm_zone",
            comments=merge_nsm_config_document_into_comments("", {"menu": "links"}),
        )
        self.assertEqual(resolve_menu_for_cot(cot), "links")

    def test_group_name_for_menu(self):
        self.assertEqual(group_name_for_menu("objects"), "NSM Objects")
        self.assertEqual(group_name_for_menu("rulebooks"), "NSM Rulebooks")

    def test_cot_belongs_to_nsm_objects_menu_uses_metadata(self):
        cot = SimpleNamespace(
            slug="nsm_zone",
            comments=merge_nsm_config_document_into_comments("", {"menu": "objects"}),
        )
        self.assertTrue(cot_belongs_to_nsm_objects_menu(cot))
        cot.comments = merge_nsm_config_document_into_comments("", {"menu": "links"})
        self.assertFalse(cot_belongs_to_nsm_objects_menu(cot))

    def test_is_nsm_object_menu_slug_uses_metadata_not_group_name(self):
        from netbox_custom_objects.models import CustomObjectType

        cot, _created = CustomObjectType.objects.get_or_create(
            slug="nsm_menu_route_test_zone",
            defaults={
                "name": "nsm_menu_route_test_zone",
                "verbose_name": "Menu Route Test Zone",
                "group_name": "Wrong Group",
            },
        )
        cot.group_name = "Wrong Group"
        cot.comments = merge_nsm_config_document_into_comments(
            cot.comments or "",
            {"menu": "objects", "role": "zone"},
        )
        cot.save(update_fields=["group_name", "comments"])
        self.assertTrue(is_nsm_object_menu_slug(cot.slug))

        cot.comments = merge_nsm_config_document_into_comments(
            cot.comments or "",
            {"menu": "links", "role": "object_link"},
        )
        cot.save(update_fields=["comments"])
        self.assertFalse(is_nsm_object_menu_slug(cot.slug))
