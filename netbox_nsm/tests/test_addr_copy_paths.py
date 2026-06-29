"""CSV copy paths and navigation refs for address analysis trees."""

from unittest.mock import MagicMock, patch

from utilities.testing import TestCase

from netbox_nsm.analysis.addr_analysis_utils import (
    _addr_navigation_refs,
    _addr_path_line,
    _addr_path_parts_for_leaf,
    _attach_addr_navigation_refs,
    _enrich_addr_tree_copy_lines,
    _flatten_addr_tree_paths,
    _prefix_addr_copy_lines,
)


class AddrCopyPathTests(TestCase):
    def test_leaf_path_includes_object_name_and_ip(self):
        node = {
            "name": "branch-ip-demo",
            "kind": "leaf",
            "ip_ref": {"str": "10.129.129.0/24", "url": "/ipam/prefixes/1/"},
            "children": [],
        }
        line = _addr_path_line(_addr_path_parts_for_leaf(node, []))
        self.assertEqual(line, "branch-ip-demo,10.129.129.0/24")

    def test_leaf_path_excludes_navigation_refs(self):
        node = {
            "name": "host-01",
            "kind": "leaf",
            "ip_ref": {"str": "10.0.0.1/32", "url": "/ipam/ip-addresses/1/"},
            "related_refs": [
                {"label": "Interface", "name": "eth0", "url": "/dcim/interfaces/1/"},
                {"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"},
            ],
            "children": [],
        }
        line = _addr_path_line(_addr_path_parts_for_leaf(node, []))
        self.assertEqual(line, "host-01,10.0.0.1/32")

    def test_leaf_path_skips_duplicate_name_when_same_as_ip(self):
        node = {
            "name": "10.129.129.0/24",
            "kind": "leaf",
            "ip_ref": {"str": "10.129.129.0/24", "url": "/ipam/prefixes/1/"},
            "children": [],
        }
        line = _addr_path_line(_addr_path_parts_for_leaf(node, []))
        self.assertEqual(line, "10.129.129.0/24")

    def test_group_tree_path_includes_hierarchy(self):
        tree = {
            "name": "branch-ip-demo",
            "kind": "group",
            "children": [
                {
                    "name": "addr-001",
                    "kind": "leaf",
                    "ip_ref": {"str": "10.129.147.0/24", "url": "/ipam/prefixes/2/"},
                    "children": [],
                }
            ],
        }
        _enrich_addr_tree_copy_lines(tree)
        lines = _flatten_addr_tree_paths([tree])
        self.assertEqual(lines, ["branch-ip-demo,addr-001,10.129.147.0/24"])

    def test_prefix_all_for_summary_copy_lines(self):
        lines = _prefix_addr_copy_lines(
            ["branch-ip-demo,10.129.129.0/24", "branch-ip-demo,10.129.147.0/24"],
            "all",
        )
        self.assertEqual(
            lines,
            [
                "all,branch-ip-demo,10.129.129.0/24",
                "all,branch-ip-demo,10.129.147.0/24",
            ],
        )


class AddrNavigationRefTests(TestCase):
    def test_nav_append_dedupes_by_url(self):
        from netbox_nsm.analysis.addr_navigation import _addr_nav_append

        refs = []
        seen = set()
        ref = {"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"}
        _addr_nav_append(refs, seen, ref)
        _addr_nav_append(refs, seen, ref)
        self.assertEqual(len(refs), 1)

    @patch("netbox_nsm.analysis.addr_navigation._host_ref_chain")
    def test_assigned_interface_adds_iface_and_device_chain(self, host_chain):
        from netbox_nsm.analysis.addr_navigation import _addr_nav_from_assigned

        host_chain.return_value = [
            {"label": "Interface", "name": "eth0", "url": "/dcim/interfaces/1/"},
            {"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"},
        ]
        refs = []
        seen = set()
        with patch("netbox_nsm.analysis._lazy_api.isinstance", return_value=True):
            _addr_nav_from_assigned(MagicMock(), refs, seen)
        self.assertEqual(
            [r["url"] for r in refs],
            ["/dcim/interfaces/1/", "/dcim/devices/1/"],
        )

    @patch("netbox_nsm.analysis.addr_navigation._addr_nav_assigned_ips_in_prefix")
    @patch("netbox_nsm.analysis.addr_navigation._addr_nav_object_link_hosts")
    def test_prefix_collects_object_links_and_assigned_ips(
        self, link_hosts_fn, assigned_ips_fn
    ):
        def _add_device(obj, refs, seen, **kw):
            refs.append(
                {"label": "Device", "name": "srv-01", "url": "/dcim/devices/2/"}
            )

        def _add_iface(obj, refs, seen, **kw):
            refs.append(
                {"label": "Interface", "name": "eth1", "url": "/dcim/interfaces/2/"}
            )

        link_hosts_fn.side_effect = _add_device
        assigned_ips_fn.side_effect = _add_iface

        FakePrefix = type("Prefix", (), {})
        with patch("ipam.models.Prefix", FakePrefix):
            prefix = FakePrefix()
            prefix.prefix = "10.0.0.0/24"
            refs = _addr_navigation_refs(prefix)

        link_hosts_fn.assert_called_once()
        assigned_ips_fn.assert_called_once()
        self.assertEqual(len(refs), 2)

    @patch("netbox_nsm.analysis.addr_navigation._host_ref_chain")
    @patch("netbox_nsm.security.links.object_link_service.iter_links_for_object")
    @patch("django.contrib.contenttypes.models.ContentType.objects")
    def test_object_link_host_refs_from_both_directions(
        self, ct_objects, iter_links_fn, host_chain
    ):
        from netbox_nsm.analysis.addr_navigation import _addr_nav_object_link_hosts

        device = MagicMock()
        host_chain.return_value = [
            {"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"}
        ]
        ct_objects.get_for_model.return_value = MagicMock(pk=99)

        fwd_link = MagicMock()
        fwd_link.policy_object = device
        rev_link = MagicMock()
        rev_link.netbox_object = device
        iter_links_fn.return_value = [(fwd_link, "fwd"), (rev_link, "rev")]

        obj = MagicMock(pk=1)
        refs = []
        seen = set()
        with patch("netbox_nsm.analysis._lazy_api.isinstance", return_value=True):
            _addr_nav_object_link_hosts(obj, refs, seen)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["url"], "/dcim/devices/1/")

    @patch("netbox_nsm.addresses.address_ipam_fk.is_nsm_address_object", return_value=True)
    @patch("netbox_nsm.analysis.addr_navigation._addr_navigation_refs")
    def test_attach_merges_nsm_address_and_ipam_fk_refs(
        self, nav_refs_fn, _is_addr
    ):
        ipam_prefix = MagicMock()
        ipam_prefix.get_absolute_url.return_value = "/ipam/prefixes/1/"

        addr = MagicMock()
        addr.prefix = ipam_prefix
        addr.get_absolute_url.return_value = "/custom-objects/addr/1/"

        nav_refs_fn.side_effect = [
            [{"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"}],
            [{"label": "Interface", "name": "eth0", "url": "/dcim/interfaces/1/"}],
        ]

        node = {}
        _attach_addr_navigation_refs(node, obj=addr)
        urls = [r["url"] for r in node["related_refs"]]
        self.assertEqual(
            urls,
            ["/dcim/devices/1/", "/dcim/interfaces/1/"],
        )
        self.assertEqual(nav_refs_fn.call_count, 2)

    @patch("netbox_nsm.addresses.address_ipam_fk.is_nsm_address_object", return_value=True)
    @patch("netbox_nsm.analysis.addr_navigation._addr_navigation_refs")
    def test_attach_dedupes_merged_refs_by_url(self, nav_refs_fn, _is_addr):
        dup = {"label": "Device", "name": "fw-01", "url": "/dcim/devices/1/"}
        nav_refs_fn.side_effect = [[dup], [dup]]

        node = {}
        _attach_addr_navigation_refs(node, obj=MagicMock())
        self.assertEqual(len(node["related_refs"]), 1)
