"""Tests for prefix display labels on address analysis tree nodes."""

from pathlib import Path
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.views.rulebook import (
    _attach_addr_node_prefix_display,
    _build_addr_tree_node,
)

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class AddrTreePrefixDisplayTests(SimpleTestCase):
    def test_attach_display_labels_for_prefix_ip_ref(self):
        node = {"name": "LAN", "kind": "leaf", "children": []}
        ip_ref = {"str": "10.0.0.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"}
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
        self.assertEqual(node["prefix_display_cidr"], "10.0.0.0/24")
        self.assertEqual(node["prefix_display_netmask"], "10.0.0.0/255.255.255.0")

    def test_attach_display_labels_for_ipam_prefix_object(self):
        prefix = MagicMock()
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.prefix = "172.16.0.0/12"
        prefix.__str__ = lambda self: "172.16.0.0/12"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/2/"

        node = _build_addr_tree_node(prefix)
        self.assertEqual(node["prefix_display_cidr"], "172.16.0.0/12")
        self.assertEqual(node["prefix_display_netmask"], "172.16.0.0/255.240.0.0")

    def test_no_display_labels_for_ipv6_prefix(self):
        node = {"name": "v6", "kind": "leaf", "children": []}
        ip_ref = {
            "str": "2001:db8::/32",
            "url": "/ipam/prefixes/3/",
            "type": "Prefix",
        }
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
        self.assertNotIn("prefix_display_cidr", node)

    def test_display_labels_for_host_ip_ref(self):
        node = {"name": "demo-addr-0002", "kind": "leaf", "children": []}
        ip_ref = {
            "str": "10.246.2.1/32",
            "url": "/ipam/ip-addresses/2/",
            "type": "IP Address",
        }
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
        self.assertEqual(node["prefix_display_cidr"], "10.246.2.1/32")
        self.assertEqual(node["prefix_display_netmask"], "10.246.2.1/255.255.255.255")

    def test_display_labels_for_ipam_ipaddress_object(self):
        ip = MagicMock()
        ip._meta.app_label = "ipam"
        ip._meta.model_name = "ipaddress"
        ip.address = "10.246.2.1/32"
        ip.prefix = None
        ip.ip_address = None
        ip.range = None
        ip.__str__ = lambda self: "10.246.2.1/32"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/2/"

        node = _build_addr_tree_node(ip)
        self.assertEqual(node["prefix_display_cidr"], "10.246.2.1/32")
        self.assertEqual(node["prefix_display_netmask"], "10.246.2.1/255.255.255.255")

    def test_no_display_labels_for_ipv6_ip_address(self):
        node = {"name": "v6-host", "kind": "leaf", "children": []}
        ip_ref = {
            "str": "2001:db8::1/128",
            "url": "/ipam/ip-addresses/9/",
            "type": "IP Address",
        }
        _attach_addr_node_prefix_display(node, ip_ref=ip_ref)
        self.assertNotIn("prefix_display_cidr", node)


class AddrCopyPrefixFormatTests(SimpleTestCase):
    """Copy buttons should respect the active CIDR/Mask toggle."""

    def test_copy_assets_apply_prefix_format_on_copy(self):
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_assets.html"
        ).read_text(encoding="utf-8")
        self.assertIn("window.nsmFormatAddrCopyLines", assets)
        self.assertIn("applyPrefixFormatToCopyLines", assets)
        self.assertIn("buildPrefixFormatMap", assets)
        self.assertIn("nsm-addr-prefix-format", assets)
        self.assertIn("window.nsmFormatAddrCopyLines(text, btn)", assets)
        self.assertIn("btn.closest('.nsm-addr-top')", assets)
