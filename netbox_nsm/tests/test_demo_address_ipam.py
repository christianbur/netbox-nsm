"""Tests for demo address IPAM assignment."""

from django.test import SimpleTestCase

from netbox_nsm.bundles.demo_address_ipam import (
    DEMO_ADDR_HOST_NAME_PREFIX,
    _host_cidr,
    _prefix_cidr,
    demo_address_names_from_bundle,
)


class DemoAddressIpamHelperTests(SimpleTestCase):
    def test_host_cidr_is_deterministic(self):
        self.assertEqual(_host_cidr(0), "10.199.0.1/32")
        self.assertEqual(_host_cidr(1), "10.199.1.2/32")

    def test_prefix_cidr_uses_demo_supernet(self):
        import random

        cidr = _prefix_cidr(5, random.Random(42))
        self.assertTrue(cidr.startswith("10.199."))
        self.assertIn("/", cidr)

    def test_demo_address_names_from_bundle(self):
        bundle = {
            "objects": [
                {
                    "type": "nsm_zone",
                    "records": [{"name": "z1"}],
                },
                {
                    "type": "nsm_address",
                    "records": [
                        {"name": f"{DEMO_ADDR_HOST_NAME_PREFIX}001"},
                        {"name": f"{DEMO_ADDR_HOST_NAME_PREFIX}002"},
                    ],
                },
            ]
        }
        self.assertEqual(
            demo_address_names_from_bundle(bundle),
            [
                f"{DEMO_ADDR_HOST_NAME_PREFIX}001",
                f"{DEMO_ADDR_HOST_NAME_PREFIX}002",
            ],
        )

    def test_demo_address_names_ignored_for_non_demo_records(self):
        bundle = {
            "objects": [
                {
                    "type": "nsm_address",
                    "records": [{"name": "trust"}],
                }
            ]
        }
        self.assertEqual(demo_address_names_from_bundle(bundle), [])
