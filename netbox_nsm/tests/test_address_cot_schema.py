"""Tests for structural IPAM address / address-group COT discovery."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.addresses.address_cot_schema import (
    cot_address_group_flag,
    cot_ipam_address_flag,
    object_builder_in_nsm_config,
)


class AddressCotSchemaTests(SimpleTestCase):
    def test_cot_ipam_address_flag_from_model_gfk_fields(self):
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                get_fields=lambda: [
                    SimpleNamespace(name="address_content_type_id"),
                    SimpleNamespace(name="address_object_id"),
                    SimpleNamespace(name="name"),
                ]
            )
        )
        cot = SimpleNamespace(get_model=lambda: model, comments="")
        self.assertTrue(cot_ipam_address_flag(cot))

    def test_cot_ipam_address_flag_rejects_custom_address_model(self):
        model = SimpleNamespace(
            _meta=SimpleNamespace(
                get_fields=lambda: [
                    SimpleNamespace(name="ipv4"),
                    SimpleNamespace(name="ipv6"),
                    SimpleNamespace(name="subnet"),
                ]
            )
        )
        cot = SimpleNamespace(get_model=lambda: model, comments="")
        self.assertFalse(cot_ipam_address_flag(cot))

    @patch("netbox_nsm.type_metadata.config.parse_nsm_config_from_cot")
    @patch("netbox_nsm.type_metadata.config._is_custom_object_type", return_value=True)
    def test_object_builder_in_nsm_config(self, _is_cot, parse_cot):
        parse_cot.return_value = {"object_builder": {"enabled": True}}
        cot = SimpleNamespace(comments="nsm_config: ...", get_model=lambda: None)
        self.assertTrue(object_builder_in_nsm_config(cot))

    @patch("netbox_nsm.objects.cot_roles.resolve_members_field")
    def test_cot_address_group_flag_from_group_field(self, resolve_members):
        resolve_members.return_value = SimpleNamespace(name="group")
        cot = SimpleNamespace(slug="my_address_groups", comments="")
        self.assertTrue(cot_address_group_flag(cot))

    @patch("netbox_nsm.objects.cot_roles.resolve_members_field")
    @patch("netbox_nsm.type_metadata.roles.resolve_role_for_cot")
    def test_cot_address_group_flag_from_role_metadata(
        self, resolve_role, resolve_members
    ):
        resolve_members.return_value = None
        resolve_role.return_value = "address_group"
        cot = SimpleNamespace(slug="anything", comments="- role: address_group")
        self.assertTrue(cot_address_group_flag(cot))

    @patch("netbox_nsm.addresses.address_ipam_fk.cot_ipam_address_flag", return_value=True)
    @patch("netbox_nsm.addresses.address_ipam_fk.get_nsm_address_model")
    def test_is_nsm_address_object_uses_structural_cot_flag(self, get_model, _flag):
        from netbox_nsm.addresses.address_ipam_fk import is_nsm_address_object

        get_model.return_value = type("FreshTable3Model", (), {})
        ipam_cot = SimpleNamespace(pk=3, slug="corp_addresses")
        addr = SimpleNamespace(custom_object_type=ipam_cot)
        self.assertTrue(is_nsm_address_object(addr))

        with patch(
            "netbox_nsm.addresses.address_ipam_fk.cot_ipam_address_flag",
            return_value=False,
        ):
            other = SimpleNamespace(
                custom_object_type=SimpleNamespace(pk=99, slug="nsm_zones"),
            )
            self.assertFalse(is_nsm_address_object(other))
