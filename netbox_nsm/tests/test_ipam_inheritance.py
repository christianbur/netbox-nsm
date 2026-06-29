"""Tests for IPAM prefix ancestor lookup (ipam_inheritance)."""

import inspect
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase


class IpamInheritanceTests(SimpleTestCase):
    def test_module_imports_without_syntax_error(self):
        import netbox_nsm.addresses.ipam_inheritance as mod

        self.assertTrue(callable(mod.ancestor_prefixes_for_ipam))
        self.assertTrue(callable(mod.nsm_address_q_for_ancestor))

    def test_iprange_uses_chained_net_contains_filters(self):
        """IPRange must filter start and end with separate .filter() calls."""
        source = inspect.getsource(
            __import__(
                "netbox_nsm.addresses.ipam_inheritance",
                fromlist=["ancestor_prefixes_for_ipam"],
            ).ancestor_prefixes_for_ipam
        )
        self.assertIn(
            ".filter(prefix__net_contains=start_str)\n"
            "            .filter(prefix__net_contains=end_str)",
            source,
        )

    @patch("ipam.models.Prefix.objects")
    def test_iprange_calls_prefix_filter_for_both_endpoints(self, prefix_objects):
        from ipam.models import IPRange

        from netbox_nsm.addresses.ipam_inheritance import ancestor_prefixes_for_ipam

        obj = IPRange(start_address="10.0.0.1/32", end_address="10.0.0.50/32")

        qs = MagicMock()
        prefix_objects.filter.return_value = qs
        qs.filter.return_value = qs
        qs.order_by.return_value = []

        result = ancestor_prefixes_for_ipam(obj)

        prefix_objects.filter.assert_called_once_with(prefix__net_contains="10.0.0.1")
        qs.filter.assert_called_once_with(prefix__net_contains="10.0.0.50")
        qs.order_by.assert_called_once()
        self.assertEqual(result, [])
