"""Tests for manual ``nsm_address_custom`` objects (IPv4/IPv6 + prefix length)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from netbox_nsm.addresses.address_custom import (
    NSM_ADDRESS_CUSTOM_SLUG,
    get_custom_address_cidr,
    is_nsm_address_custom_object,
    validate_custom_address_fields,
)
from netbox_nsm.addresses.address_ipam_fk import (
    POLICY_ADDRESS_COT_SLUGS,
    is_policy_address_object,
)
from netbox_nsm.addresses.address_literal import (
    attach_literal_prefix_display,
    get_policy_address_cidr,
    is_literal_address,
)
from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES


def _custom_obj(**kwargs):
    obj = MagicMock()
    cot = SimpleNamespace(slug=NSM_ADDRESS_CUSTOM_SLUG)
    obj.custom_object_type = cot
    obj._meta = SimpleNamespace(model_name=NSM_ADDRESS_CUSTOM_SLUG)
    obj.ipv4 = kwargs.get("ipv4")
    obj.ipv6 = kwargs.get("ipv6")
    obj.subnet = kwargs.get("subnet")
    obj.comments = kwargs.get("comments")
    return obj


class AddressCustomObjectTests(SimpleTestCase):
    def test_is_nsm_address_custom_object_by_cot_slug(self):
        self.assertTrue(is_nsm_address_custom_object(_custom_obj(ipv4="1.1.1.1", subnet=32)))

    def test_is_nsm_address_custom_object_by_model_name(self):
        obj = MagicMock()
        obj.custom_object_type = None
        obj._meta = SimpleNamespace(model_name=NSM_ADDRESS_CUSTOM_SLUG)
        self.assertTrue(is_nsm_address_custom_object(obj))

    def test_get_custom_address_cidr_ipv4(self):
        cidr = get_custom_address_cidr(_custom_obj(ipv4="10.0.0.0", subnet=8))
        self.assertEqual(cidr, "10.0.0.0/8")

    def test_get_custom_address_cidr_ipv6(self):
        cidr = get_custom_address_cidr(
            _custom_obj(ipv6="2001:db8::", subnet=32)
        )
        self.assertEqual(cidr, "2001:db8::/32")

    def test_get_custom_address_cidr_any(self):
        cidr = get_custom_address_cidr(_custom_obj(ipv4="0.0.0.0", subnet=0))
        self.assertEqual(cidr, "0.0.0.0/0")

    def test_validate_accepts_ipv4_any(self):
        validate_custom_address_fields(_custom_obj(ipv4="0.0.0.0", subnet=0))

    def test_validate_rejects_both_ip_versions(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(
                _custom_obj(ipv4="1.1.1.1", ipv6="::1", subnet=32)
            )

    def test_validate_rejects_missing_ip(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(_custom_obj(subnet=0))

    def test_validate_rejects_missing_subnet(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(_custom_obj(ipv4="1.1.1.1"))

    def test_validate_rejects_invalid_ipv4(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(_custom_obj(ipv4="999.1.1.1", subnet=24))

    def test_validate_rejects_prefix_too_long_for_ipv4(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(_custom_obj(ipv4="1.1.1.1", subnet=33))

    def test_validate_rejects_prefix_too_long_for_ipv6(self):
        with self.assertRaises(ValidationError):
            validate_custom_address_fields(_custom_obj(ipv6="::1", subnet=129))


class PolicyAddressCidrTests(SimpleTestCase):
    def test_get_policy_address_cidr_prefers_custom_fields(self):
        obj = _custom_obj(ipv4="192.168.1.0", subnet=24)
        self.assertEqual(get_policy_address_cidr(obj), "192.168.1.0/24")

    def test_is_literal_address_true_for_custom(self):
        self.assertTrue(
            is_literal_address(_custom_obj(ipv4="0.0.0.0", subnet=0))
        )

    def test_attach_literal_prefix_display_for_custom(self):
        obj = _custom_obj(ipv4="0.0.0.0", subnet=0)
        node = {"name": "ANY", "children": []}
        attach_literal_prefix_display(node, obj)
        self.assertEqual(node["prefix_display_cidr"], "0.0.0.0/0")


class PolicyAddressSlugTests(SimpleTestCase):
    def test_policy_address_slugs_include_custom(self):
        self.assertIn(NSM_ADDRESS_CUSTOM_SLUG, POLICY_ADDRESS_COT_SLUGS)

    def test_is_policy_address_object_recognizes_custom(self):
        self.assertTrue(is_policy_address_object(_custom_obj(ipv4="1.1.1.1", subnet=32)))


class BuiltinAddressCustomTypeTests(SimpleTestCase):
    def test_address_custom_type_in_catalog(self):
        typedef = next(
            t for t in BUILTIN_CUSTOM_TYPES if t.get("name") == "Address Custom"
        )
        field_names = [f["name"] for f in typedef.get("field_definitions") or []]
        self.assertEqual(field_names, ["ipv4", "ipv6", "subnet"])

    def test_address_custom_default_any_object(self):
        typedef = next(
            t for t in BUILTIN_CUSTOM_TYPES if t.get("name") == "Address Custom"
        )
        defaults = typedef.get("default_objects") or []
        self.assertEqual(len(defaults), 1)
        self.assertEqual(defaults[0]["name"], "ANY")
        self.assertEqual(defaults[0]["field_data"]["ipv4"], "0.0.0.0")
        self.assertEqual(defaults[0]["field_data"]["subnet"], 0)

    def test_address_group_allows_custom_members(self):
        typedef = next(
            t for t in BUILTIN_CUSTOM_TYPES if t.get("name") == "Address Group"
        )
        group_field = next(
            f for f in typedef.get("field_definitions") or [] if f.get("name") == "group"
        )
        self.assertIn("custom-objects.nsm_address_custom", group_field["model"])
