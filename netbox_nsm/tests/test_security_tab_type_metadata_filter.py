"""Tests for Type-Metadata filtering on Security tab CO references."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.security.tab.combined import _cot_is_type_metadata_reference


class CotTypeMetadataReferenceTests(SimpleTestCase):
    def test_junction_cot_always_allowed(self):
        cot = SimpleNamespace(slug="nsm_object_link")
        with patch(
            "netbox_nsm.security.tab.combined.cot_link_table_flag",
            return_value=True,
        ):
            self.assertTrue(_cot_is_type_metadata_reference(cot))

    def test_non_junction_requires_type_metadata(self):
        cot = SimpleNamespace(slug="nsm_demo_misc")
        with patch(
            "netbox_nsm.security.tab.combined.cot_link_table_flag",
            return_value=False,
        ), patch(
            "netbox_nsm.type_metadata.config.resolve_nsm_config_for_cot",
            return_value=None,
        ):
            self.assertFalse(_cot_is_type_metadata_reference(cot))

    def test_non_junction_with_metadata_allowed(self):
        cot = SimpleNamespace(slug="nsm_zone")
        with patch(
            "netbox_nsm.security.tab.combined.cot_link_table_flag",
            return_value=False,
        ), patch(
            "netbox_nsm.type_metadata.config.resolve_nsm_config_for_cot",
            return_value={"slug": "nsm_zone"},
        ):
            self.assertTrue(_cot_is_type_metadata_reference(cot))
