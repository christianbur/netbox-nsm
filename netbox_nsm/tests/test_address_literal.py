"""Tests for literal address objects (nsm_config.network in comments)."""

from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from netbox_nsm.addresses.address_literal import (
    ALLOWED_NETWORK_LITERALS,
    attach_literal_prefix_display,
    format_network_nsm_config_comments,
    get_network_literal,
    is_literal_address,
    merge_network_into_instance_comments,
    parse_network_from_instance_comments,
    validate_address_fields,
)
from netbox_nsm.objects.builtin_types import BUILTIN_CUSTOM_TYPES


def _literal_comments(cidr: str = "0.0.0.0/0") -> str:
    return format_network_nsm_config_comments(cidr).rstrip()


class AddressLiteralValidationTests(SimpleTestCase):
    def _addr(self, **kwargs):
        obj = MagicMock()
        obj.comments = kwargs.get("comments")
        with_ipam = kwargs.get("with_ipam", False)
        if with_ipam:
            obj.address_content_type_id = 1
            obj.address_object_id = 2
            obj.prefix_id = None
            obj.ip_address_id = None
            obj.range_id = None
        else:
            obj.address_content_type_id = None
            obj.address_object_id = None
            obj.prefix_id = None
            obj.ip_address_id = None
            obj.range_id = None
        obj.network_literal = kwargs.get("network_literal")
        return obj

    def test_allowed_literal_includes_any(self):
        self.assertIn("0.0.0.0/0", ALLOWED_NETWORK_LITERALS)

    def test_parse_network_from_instance_comments(self):
        yaml_text = _literal_comments()
        self.assertEqual(parse_network_from_instance_comments(yaml_text), "0.0.0.0/0")

    def test_merge_network_into_instance_comments(self):
        merged = merge_network_into_instance_comments("", "0.0.0.0/0")
        self.assertIn("network: 0.0.0.0/0", merged)
        self.assertIn("nsm_config:", merged)

    def test_validate_accepts_literal_only_any(self):
        validate_address_fields(self._addr(comments=_literal_comments()))

    def test_validate_rejects_missing_both_sources(self):
        with self.assertRaises(ValidationError):
            validate_address_fields(self._addr())

    def test_validate_rejects_literal_and_ipam(self):
        with patch(
            "netbox_nsm.addresses.address_literal.has_address_ipam_link",
            return_value=True,
        ):
            with self.assertRaises(ValidationError):
                validate_address_fields(
                    self._addr(comments=_literal_comments(), with_ipam=True)
                )

    def test_validate_rejects_unsupported_literal(self):
        with self.assertRaises(ValidationError):
            validate_address_fields(
                self._addr(comments=_literal_comments("10.0.0.0/8"))
            )

    def test_attach_literal_prefix_display_sets_cidr(self):
        obj = self._addr(comments=_literal_comments())
        node = {"name": "all-ipv4", "children": []}
        attach_literal_prefix_display(node, obj)
        self.assertEqual(node["prefix_display_cidr"], "0.0.0.0/0")
        self.assertEqual(node["prefix_display_netmask"], "0.0.0.0/0.0.0.0")

    def test_is_literal_address_from_comments(self):
        self.assertTrue(is_literal_address(self._addr(comments=_literal_comments())))
        self.assertFalse(is_literal_address(self._addr()))
        self.assertEqual(
            get_network_literal(self._addr(comments=_literal_comments(" 0.0.0.0/0 "))),
            "0.0.0.0/0",
        )

    def test_legacy_network_literal_field_fallback(self):
        self.assertEqual(
            get_network_literal(self._addr(network_literal="0.0.0.0/0")),
            "0.0.0.0/0",
        )

    def test_legacy_plain_cidr_comments_fallback(self):
        self.assertEqual(
            get_network_literal(self._addr(comments="0.0.0.0/0")),
            "0.0.0.0/0",
        )

    def test_invalid_yaml_comments_are_ignored(self):
        tufin_like = (
            "network-3.65.246.96-29 | TufinType: subnet | TufinID: 1684006"
        )
        self.assertIsNone(parse_network_from_instance_comments(tufin_like))
        self.assertIsNone(get_network_literal(self._addr(comments=tufin_like)))
        self.assertFalse(is_literal_address(self._addr(comments=tufin_like)))


class BuiltinAddressDefaultObjectTests(SimpleTestCase):
    def test_address_type_has_no_default_objects(self):
        address_type = next(
            t for t in BUILTIN_CUSTOM_TYPES if t.get("name") == "Address"
        )
        self.assertEqual(address_type.get("default_objects") or [], [])

    def test_address_type_has_no_network_literal_field(self):
        address_type = next(
            t for t in BUILTIN_CUSTOM_TYPES if t.get("name") == "Address"
        )
        field_names = [f["name"] for f in address_type.get("field_definitions") or []]
        self.assertNotIn("network_literal", field_names)
