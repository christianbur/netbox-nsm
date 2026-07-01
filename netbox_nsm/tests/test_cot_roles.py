"""Unit tests for the structural cot_roles inference contract (Phase B)."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.objects import cot_roles


class CotRolesUniversalAddressTests(SimpleTestCase):
    def test_is_universal_address_ipv4_any(self):
        obj = SimpleNamespace(comments="nsm_config:\n  - network: 0.0.0.0/0\n")
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_literal_network",
            return_value="0.0.0.0/0",
        ):
            self.assertTrue(cot_roles.is_universal_address(obj))

    def test_is_universal_address_ipv6_any(self):
        obj = SimpleNamespace(comments="")
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_literal_network",
            return_value="::/0",
        ):
            self.assertTrue(cot_roles.is_universal_address(obj))

    def test_non_universal_literal_is_false(self):
        obj = SimpleNamespace(comments="")
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_literal_network",
            return_value="10.0.0.0/8",
        ):
            self.assertFalse(cot_roles.is_universal_address(obj))

    def test_no_literal_is_false(self):
        obj = SimpleNamespace(comments="")
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_literal_network",
            return_value=None,
        ):
            self.assertFalse(cot_roles.is_universal_address(obj))


class CotRolesIpamFieldNameTests(SimpleTestCase):
    def test_ipam_field_name_falls_back_to_address(self):
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_ipam_field", return_value=None
        ):
            cot = SimpleNamespace(slug="corp_addresses")
            self.assertEqual(cot_roles.resolve_ipam_field_name(cot), "address")
            self.assertEqual(
                cot_roles.ipam_gfk_attrs(cot),
                ("address_content_type_id", "address_object_id"),
            )

    def test_ipam_field_name_uses_resolved_field(self):
        field = SimpleNamespace(name="ipam_ref")
        with patch(
            "netbox_nsm.objects.cot_roles.resolve_ipam_field", return_value=field
        ):
            cot = SimpleNamespace(slug="corp_addresses")
            self.assertEqual(cot_roles.resolve_ipam_field_name(cot), "ipam_ref")
            self.assertEqual(
                cot_roles.ipam_gfk_attrs(cot),
                ("ipam_ref_content_type_id", "ipam_ref_object_id"),
            )
