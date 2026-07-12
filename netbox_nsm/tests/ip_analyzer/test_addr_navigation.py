from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.addr_navigation import _addr_navigation_refs


class AddrNavigationRefsTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_navigation._addr_nav_from_assigned")
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_navigation._hub.isinstance")
    def test_addr_navigation_refs_only_evaluates_ip_addresses(
        self, isinstance_fn, nav_from_assigned
    ):
        obj = MagicMock()

        def _isinstance(value, klass):
            return getattr(klass, "__name__", "") == "IPAddress"

        isinstance_fn.side_effect = _isinstance

        _addr_navigation_refs(obj)

        nav_from_assigned.assert_called_once_with(
            getattr(obj, "assigned_object", None),
            [],
            set(),
            limit=15,
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_navigation._addr_nav_from_assigned")
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_navigation._hub.isinstance")
    def test_addr_navigation_refs_skips_prefix_and_range_objects(
        self, isinstance_fn, nav_from_assigned
    ):
        prefix_obj = MagicMock()

        isinstance_fn.return_value = False

        refs = _addr_navigation_refs(prefix_obj)

        self.assertEqual(refs, [])
        nav_from_assigned.assert_not_called()
