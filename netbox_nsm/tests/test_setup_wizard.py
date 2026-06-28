"""Tests for Setup wizard action wiring."""

from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.bundles.dispatch import (
    BUNDLE_FORMAT_JSON,
    BUNDLE_FORMAT_PYTHON,
    list_setup_bundles,
    organize_bundles_tree,
)


class SetupWizardActionTests(SimpleTestCase):
    @patch("netbox_nsm.bundles.dispatch.get_bundle_status", return_value="missing")
    def test_python_bundles_use_run_bundle_action(self, _mock_status):
        bundles = list_setup_bundles()
        python_bundles = [
            b for b in bundles if b["format"] == BUNDLE_FORMAT_PYTHON
        ]
        self.assertTrue(python_bundles)
        for bundle in python_bundles:
            with self.subTest(slug=bundle["slug"]):
                self.assertEqual(bundle["action"], "run_bundle")


class SetupBundleTreeTests(SimpleTestCase):
    def test_organize_bundles_tree_indents_requires_under_parent(self):
        bundles = [
            {"slug": "nsm_schema", "requires": []},
            {"slug": "nsm_demo_zone_matrix", "requires": ["nsm_schema"], "format": BUNDLE_FORMAT_PYTHON},
        ]
        ordered = organize_bundles_tree(bundles)
        self.assertEqual([b["slug"] for b in ordered], [
            "nsm_schema",
            "nsm_demo_zone_matrix",
        ])
        self.assertEqual([b["depth"] for b in ordered], [0, 1])

    @patch("netbox_nsm.bundles.dispatch.get_bundle_status", return_value="missing")
    def test_list_setup_bundles_includes_json_and_python_formats(self, _mock_status):
        bundles = list_setup_bundles()
        formats = {b["slug"]: b["format"] for b in bundles}
        self.assertEqual(formats["nsm_schema"], BUNDLE_FORMAT_JSON)
        self.assertEqual(formats["nsm_demo_zone_matrix"], BUNDLE_FORMAT_PYTHON)
        self.assertEqual(formats["nsm_demo_zone_address_adressgroup"], BUNDLE_FORMAT_PYTHON)
        self.assertNotIn("demo_starter", formats)
        self.assertNotIn("nsm_demo_starter", formats)
        self.assertNotIn("nsm_demo_matrix", formats)
        self.assertNotIn("demo_scale_50k", formats)
        self.assertNotIn("nsm_demo_scale_50k", formats)
        self.assertNotIn("nsm_rulebook_templates", formats)
        demo_starter = next(b for b in bundles if b["slug"] == "nsm_demo_zone_matrix")
        self.assertEqual(demo_starter["requires"], ["nsm_schema"])
        self.assertEqual(demo_starter["action"], "run_bundle")
