"""Tests for Setup wizard action wiring."""

from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.bundles.dispatch import (
    BUNDLE_FORMAT_JSON,
    list_setup_bundles,
    organize_bundles_tree,
)


class SetupBundleTreeTests(SimpleTestCase):
    def test_organize_bundles_tree_indents_requires_under_parent(self):
        bundles = [
            {"slug": "nsm_schema", "requires": []},
            {"slug": "nsm_demo_zone_matrix", "requires": ["nsm_schema"], "format": BUNDLE_FORMAT_JSON},
        ]
        ordered = organize_bundles_tree(bundles)
        self.assertEqual([b["slug"] for b in ordered], [
            "nsm_schema",
            "nsm_demo_zone_matrix",
        ])
        self.assertEqual([b["depth"] for b in ordered], [0, 1])

    @patch("netbox_nsm.bundles.dispatch.get_bundle_status", return_value="missing")
    def test_list_setup_bundles_are_json_schema_only(self, _mock_status):
        bundles = list_setup_bundles()
        formats = {b["slug"]: b["format"] for b in bundles}
        self.assertEqual(formats["nsm_schema"], BUNDLE_FORMAT_JSON)
        self.assertEqual(formats["nsm_demo_zone_matrix"], BUNDLE_FORMAT_JSON)
        self.assertEqual(formats["nsm_demo_zone_address_adressgroup"], BUNDLE_FORMAT_JSON)
        demo_matrix = next(b for b in bundles if b["slug"] == "nsm_demo_zone_matrix")
        self.assertEqual(demo_matrix["requires"], ["nsm_schema"])
        self.assertEqual(demo_matrix["action"], "")
