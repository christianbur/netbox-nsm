"""Tests for IPv4 prefix netmask display helpers."""

from django.test import SimpleTestCase

from netbox_nsm.analysis.addr_netmask import (
    ipv4_netmask_for_cidr,
    ipv4_prefix_length_to_netmask,
    prefix_display_labels_for_cidr,
)


class AddrNetmaskTests(SimpleTestCase):
    def test_ipv4_prefix_length_to_netmask_common_lengths(self):
        self.assertEqual(ipv4_prefix_length_to_netmask(24), "255.255.255.0")
        self.assertEqual(ipv4_prefix_length_to_netmask(16), "255.255.0.0")
        self.assertEqual(ipv4_prefix_length_to_netmask(8), "255.0.0.0")
        self.assertEqual(ipv4_prefix_length_to_netmask(0), "0.0.0.0")
        self.assertEqual(ipv4_prefix_length_to_netmask(32), "255.255.255.255")

    def test_ipv4_prefix_length_to_netmask_rejects_out_of_range(self):
        self.assertIsNone(ipv4_prefix_length_to_netmask(-1))
        self.assertIsNone(ipv4_prefix_length_to_netmask(33))

    def test_ipv4_netmask_for_ipv4_cidr(self):
        self.assertEqual(ipv4_netmask_for_cidr("10.0.0.0/24"), "255.255.255.0")
        self.assertEqual(ipv4_netmask_for_cidr("192.168.1.128/25"), "255.255.255.128")

    def test_ipv4_netmask_skips_ipv6(self):
        self.assertIsNone(ipv4_netmask_for_cidr("2001:db8::/32"))

    def test_ipv4_netmask_rejects_invalid_input(self):
        self.assertIsNone(ipv4_netmask_for_cidr(""))
        self.assertIsNone(ipv4_netmask_for_cidr("10.0.0.0"))
        self.assertIsNone(ipv4_netmask_for_cidr("not-a-network/24"))

    def test_prefix_display_labels_for_ipv4_cidr(self):
        self.assertEqual(
            prefix_display_labels_for_cidr("10.0.0.0/24"),
            ("10.0.0.0/24", "10.0.0.0/255.255.255.0"),
        )

    def test_prefix_display_labels_for_host_slash32(self):
        self.assertEqual(
            prefix_display_labels_for_cidr("10.246.2.1/32"),
            ("10.246.2.1/32", "10.246.2.1/255.255.255.255"),
        )

    def test_prefix_display_labels_skips_ipv6(self):
        self.assertIsNone(prefix_display_labels_for_cidr("2001:db8::/32"))
