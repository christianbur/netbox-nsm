"""Shared COT demo helper tests."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.demos.cot_demo_common import resolve_rulebook_address_field_names


class CotDemoCommonTests(SimpleTestCase):
    def test_resolve_rulebook_address_field_names_default(self):
        cot = MagicMock()
        cot.fields.values_list.return_value = [
            "index",
            "name",
            "source",
            "destination",
            "actions",
        ]
        self.assertEqual(
            resolve_rulebook_address_field_names(cot),
            ("source", "destination"),
        )

    def test_resolve_rulebook_address_field_names_split_columns(self):
        cot = MagicMock()
        cot.fields.values_list.return_value = [
            "index",
            "name",
            "source_addresses",
            "destination_addresses",
            "actions",
        ]
        self.assertEqual(
            resolve_rulebook_address_field_names(cot),
            ("source_addresses", "destination_addresses"),
        )
