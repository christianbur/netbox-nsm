"""Bundle apply: reconcile portable types with existing COT rows."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.bundles.dispatch import _reconcile_portable_types_with_existing_cots


class BundleTypeReconcileTests(SimpleTestCase):
    @patch("netbox_custom_objects.models.CustomObjectType")
    def test_reconcile_aligns_slug_when_name_already_deployed(self, mock_cot_model):
        existing = MagicMock(slug="legacy_zone_addresses")

        def filter_side_effect(**kwargs):
            qs = MagicMock()
            if "slug" in kwargs:
                qs.exists.return_value = False
            elif "name" in kwargs:
                qs.first.return_value = existing
            return qs

        mock_cot_model.objects.filter.side_effect = filter_side_effect

        document = {
            "types": [
                {
                    "slug": "nsm_rb_demo_zone_addresses",
                    "name": "nsm_rb_demo_zone_addresses",
                    "fields": [],
                }
            ]
        }
        _reconcile_portable_types_with_existing_cots(document)
        self.assertEqual(document["types"][0]["slug"], "legacy_zone_addresses")

    @patch("netbox_custom_objects.models.CustomObjectType")
    def test_reconcile_leaves_slug_when_cot_already_matches(self, mock_cot_model):
        mock_cot_model.objects.filter.return_value.exists.return_value = True

        document = {
            "types": [
                {
                    "slug": "nsm_rb_demo_zone_addresses",
                    "name": "nsm_rb_demo_zone_addresses",
                    "fields": [],
                }
            ]
        }
        _reconcile_portable_types_with_existing_cots(document)
        self.assertEqual(document["types"][0]["slug"], "nsm_rb_demo_zone_addresses")
