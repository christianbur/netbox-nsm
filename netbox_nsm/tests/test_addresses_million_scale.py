"""Helpers for bench million-address scale script (not Setup)."""

from unittest.mock import patch

from django.test import SimpleTestCase
from ipam.models import IPAddress, Prefix

from netbox_nsm.demos.addresses_million_scale import (
    DEFAULT_LEAF_COUNT,
    DEFAULT_RULE_COUNT,
    HOSTS_PER_SUBNET,
    SCALE_DEMO_50K_LEAF_COUNT,
    SCALE_DEMO_50K_RULE_COUNT,
    SUBNET_COUNT,
    _address_polymorphic_kwargs,
    _host_cidr,
    _leaf_indices,
    _leaf_name,
    _subnet_prefix_cidr,
)


class AddressesMillionScaleHelperTests(SimpleTestCase):
    def test_subnet_cidr_range(self):
        self.assertEqual(_subnet_prefix_cidr(0), "10.128.0.0/24")
        self.assertEqual(_subnet_prefix_cidr(255), "10.128.255.0/24")
        self.assertEqual(_subnet_prefix_cidr(256), "10.129.0.0/24")

    def test_host_cidr_in_subnet(self):
        self.assertEqual(_host_cidr(0, 0), "10.128.0.1/32")
        self.assertEqual(_host_cidr(0, 99), "10.128.0.100/32")

    def test_leaf_index_mapping(self):
        self.assertEqual(_leaf_indices(0), (0, 0))
        self.assertEqual(_leaf_indices(99), (0, 99))
        self.assertEqual(_leaf_indices(100), (1, 0))
        self.assertEqual(
            _leaf_indices(SUBNET_COUNT * HOSTS_PER_SUBNET - 1)[0], SUBNET_COUNT - 1
        )

    def test_leaf_name_padding(self):
        self.assertEqual(_leaf_name(0), "bench-ip-0000000")
        self.assertEqual(_leaf_name(199999), "bench-ip-0199999")

    def test_scale_demo_50k_constants(self):
        self.assertEqual(SCALE_DEMO_50K_LEAF_COUNT, 50_000)
        self.assertEqual(
            SCALE_DEMO_50K_RULE_COUNT,
            round(DEFAULT_RULE_COUNT * 50_000 / DEFAULT_LEAF_COUNT),
        )

    @patch("netbox_nsm.demos.addresses_million_scale._PREFIX_CT_ID", 20)
    @patch("netbox_nsm.demos.addresses_million_scale._IP_CT_ID", 10)
    def test_address_polymorphic_kwargs_maps_ipam_models(self):
        with self.assertRaises(TypeError):
            _address_polymorphic_kwargs(object())

        ip_kwargs = _address_polymorphic_kwargs(IPAddress(pk=7))
        self.assertEqual(ip_kwargs["address_content_type_id"], 10)
        self.assertEqual(ip_kwargs["address_object_id"], 7)

        prefix_kwargs = _address_polymorphic_kwargs(Prefix(pk=9))
        self.assertEqual(prefix_kwargs["address_content_type_id"], 20)
        self.assertEqual(prefix_kwargs["address_object_id"], 9)
