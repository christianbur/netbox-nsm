"""Tests for Device/VM Security Panel interface analysis."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from dcim.models import Device
from django.test import SimpleTestCase
from virtualization.models import VirtualMachine

from netbox_nsm.security.host_interface_analysis import build_host_interface_analysis


class HostInterfaceAnalysisTests(SimpleTestCase):
    def test_returns_empty_for_non_host(self):
        result = build_host_interface_analysis(
            SimpleNamespace(pk=1),
            request=None,
            panel_url=lambda url: url,
        )
        self.assertEqual(result, [])

    @patch("netbox_nsm.security.host_interface_analysis.build_object_link_rows")
    @patch("netbox_nsm.security.host_interface_analysis._interfaces_for_host")
    def test_skips_interfaces_without_entries(
        self,
        mock_interfaces,
        mock_link_rows,
    ):
        iface_empty = SimpleNamespace(pk=10, name="eth0")
        iface_empty.get_absolute_url = lambda: "/interfaces/10/"
        iface_linked = SimpleNamespace(pk=11, name="eth1")
        iface_linked.get_absolute_url = lambda: "/interfaces/11/"
        mock_interfaces.return_value = [iface_empty, iface_linked]

        mock_link_rows.side_effect = [[], [{"name": "zone-a", "type_label": "Zone"}]]

        result = build_host_interface_analysis(
            MagicMock(spec=Device, pk=1),
            request=SimpleNamespace(path="/dcim/devices/1/", COOKIES={}),
            panel_url=lambda url: url,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "eth1")
        self.assertEqual(result[0]["entry_count"], 1)

    @patch("netbox_nsm.security.host_interface_analysis.build_object_link_rows")
    @patch("netbox_nsm.security.host_interface_analysis._interfaces_for_host")
    def test_includes_link_rows(
        self,
        mock_interfaces,
        mock_link_rows,
    ):
        iface = SimpleNamespace(pk=20, name="ge-0/0/0")
        iface.get_absolute_url = lambda: "/interfaces/20/"
        mock_interfaces.return_value = [iface]

        mock_link_rows.return_value = [
            {"name": "trust", "type_label": "Zone", "url": "/zones/1/"},
        ]

        result = build_host_interface_analysis(
            MagicMock(spec=Device, pk=5),
            request=SimpleNamespace(path="/dcim/devices/5/", COOKIES={}),
            panel_url=lambda url: f"{url}?branch=main",
        )

        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row["name"], "ge-0/0/0")
        self.assertEqual(row["url"], "/interfaces/20/")
        self.assertEqual(row["entry_count"], 1)
        self.assertEqual(len(row["link_rows"]), 1)
        self.assertNotIn("rulebook_groups", row)
        self.assertNotIn("api_url", row)

    @patch("netbox_nsm.security.host_interface_analysis.build_object_link_rows")
    @patch("netbox_nsm.security.host_interface_analysis._interfaces_for_host")
    def test_skips_interfaces_with_only_rulebook_refs(
        self,
        mock_interfaces,
        mock_link_rows,
    ):
        iface = SimpleNamespace(pk=30, name="eth2")
        mock_interfaces.return_value = [iface]
        mock_link_rows.return_value = []

        result = build_host_interface_analysis(
            MagicMock(spec=VirtualMachine, pk=9),
            request=None,
            panel_url=lambda url: url,
        )

        self.assertEqual(result, [])

    @patch("netbox_nsm.security.host_interface_analysis.build_object_link_rows")
    @patch("netbox_nsm.security.host_interface_analysis._interfaces_for_host")
    def test_no_interfaces_returns_empty(
        self,
        mock_interfaces,
        mock_link_rows,
    ):
        mock_interfaces.return_value = []
        result = build_host_interface_analysis(
            MagicMock(spec=Device, pk=1),
            request=None,
            panel_url=lambda url: url,
        )
        self.assertEqual(result, [])
        mock_link_rows.assert_not_called()
