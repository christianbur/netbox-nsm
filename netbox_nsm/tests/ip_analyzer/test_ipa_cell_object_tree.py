"""Tests for IPA cell object tree builders."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import (
    _build_ipa_cell_object_tree,
    _count_ipa_object_tree_duplicates,
    _count_ipa_object_tree_group_duplicates,
    _flatten_ipa_object_tree_copy_lines,
    _ipa_cell_object_tree_visible,
    _ipa_object_tree_type_counts,
    _resolve_summary_type_counts,
)
from netbox_nsm.addresses.address_literal import format_network_nsm_config_comments
from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import (
    IPA_NODE_ROLE_GROUP,
    IPA_NODE_ROLE_HOST,
    IPA_NODE_ROLE_PREFIX,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
    IPA_IPAM_CHILD_IP_ENUM_MAX,
    _attach_ipa_cell_address_fields,
    _attach_ipa_cell_ipam_object_refs,
    _ipa_cell_object_tree_type_counts,
    _ipa_ipam_ip_keys_for_object,
    _ipa_ipam_object_display_ref,
    _ipa_cell_tree_ipam_object_for_node,
    _attach_ipa_explain_fields,
    _attach_ipa_drilldown_meta,
    _build_ipa_group_coverage,
    _ensure_ipa_cell_tree_network_links,
    _ipa_cell_tree_extended_summary_counts,
    _ipa_resolve_group_anchor_member,
    _mark_ipa_cell_pill_roles,
    _build_ipa_ipam_filler_prefix_node,
    _build_ipa_synthesized_parent_prefix_node,
    _enrich_ipa_object_tree_cidr_from_names,
    _insert_ipa_host_gap_info_rows,
    _insert_ipam_filler_prefixes,
    _collapse_consecutive_ipa_info_gap_nodes,
    _ipa_info_gap_display_label,
    _ipa_info_gap_row_is_visible,
    _prune_empty_ipa_info_gap_nodes,
    _ipa_cell_tree_has_visible_address_children,
    _ipa_intermediate_ipam_prefix_chain,
    _ipa_cidr_from_object_name,
    _ipa_format_gap_label,
    _ipa_object_tree_sort_key,
    _ipa_subnet_containment_display_net,
    _collapse_ipa_cell_siblings_by_network,
    _mark_ipa_object_addr_drilldown_flags,
    _mark_ipa_subnet_containment_warnings,
    _merge_ipa_cell_nodes_by_network,
    _prune_ipa_object_tree_duplicate_nodes,
    _sort_ipa_object_tree_siblings,
    _synthesize_ipa_cell_ipam_parent_prefixes,
    IPA_TREE_NODE_CELL_SELECTED,
    IPA_TREE_NODE_INFO_GAP,
    IPA_TREE_NODE_IPAM_FILLER,
)


class IpaCidrFromNameTests(SimpleTestCase):
    def test_dm_addr_name_parses_to_cidr(self):
        self.assertEqual(
            _ipa_cidr_from_object_name("dm-addr-10-112-148-0-28"),
            "10.112.148.0/28",
        )
        self.assertEqual(
            _ipa_cidr_from_object_name("dm-addr-10.112.160.0-28"),
            "10.112.160.0/28",
        )
        self.assertEqual(
            _ipa_cidr_from_object_name("dm-addr-10-112-157-0-24"),
            "10.112.157.0/24",
        )
        self.assertEqual(
            _ipa_cidr_from_object_name("diff-test-10-112-134-0-24"),
            "10.112.134.0/24",
        )
        self.assertEqual(
            _ipa_cidr_from_object_name("h-10.112.134.44"),
            "10.112.134.44/32",
        )


class IpaSubnetContainmentMetaTests(SimpleTestCase):
    def test_subnet_containment_display_net_strips_host_mask(self):
        node = {
            "prefix_display_cidr": "10.112.134.44/32",
            "ip_ref": {"str": "10.112.134.44/32"},
        }
        self.assertEqual(
            _ipa_subnet_containment_display_net(node),
            "10.112.134.44",
        )

    def test_mark_subnet_containment_sets_display_and_parent_url(self):
        nodes = [
            {
                "name": "dm-addr-10-112-134-0-24",
                "url": "/a/13/",
                "prefix_display_cidr": "10.112.134.0/24",
                "children": [
                    {
                        "name": "h-10.112.134.44",
                        "prefix_display_cidr": "10.112.134.44/32",
                        "children": [],
                    }
                ],
            }
        ]
        _mark_ipa_subnet_containment_warnings(nodes)
        child = nodes[0]["children"][0]
        self.assertEqual(child["subnet_contained_in"], "10.112.134.0/24")
        self.assertEqual(child["subnet_contained_in_name"], "dm-addr-10-112-134-0-24")
        self.assertEqual(child["subnet_contained_in_url"], "/a/13/")
        self.assertEqual(child["subnet_containment_display_net"], "10.112.134.44")

    def test_mark_subnet_containment_peer_fallback_marks_flat_sibling_host(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _mark_ipa_subnet_containment_peer_fallback,
            _mark_ipa_subnet_containment_warnings,
        )

        net24 = "10.112.128.0/24"
        host = "10.112.128.1/32"
        nodes = [
            {
                "name": "bench-net-00000",
                "url": "/a/2/",
                "prefix_display_cidr": net24,
                "children": [],
            },
            {
                "name": "bench-ip-0000001",
                "url": "/a/1/",
                "prefix_display_cidr": host,
                "children": [],
            },
        ]
        _mark_ipa_subnet_containment_warnings(nodes)
        self.assertNotIn("subnet_contained_in", nodes[1])
        _mark_ipa_subnet_containment_peer_fallback(nodes)
        self.assertEqual(nodes[1]["subnet_contained_in"], net24)
        self.assertEqual(nodes[1]["subnet_contained_in_name"], "bench-net-00000")


class IpaCidrFromNameEnrichTests(SimpleTestCase):
    def test_enrich_sets_prefix_role_for_dm_addr_leaf(self):
        nodes = [{"name": "dm-addr-10-112-148-0-28", "kind": "leaf", "children": []}]
        _enrich_ipa_object_tree_cidr_from_names(nodes)
        self.assertEqual(nodes[0]["prefix_display_cidr"], "10.112.148.0/28")
        self.assertEqual(nodes[0]["node_role"], IPA_NODE_ROLE_PREFIX)
        self.assertEqual(nodes[0]["kind"], "group")


class IpaCellDrilldownMetaTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_on_cell_direct_prefix(self, meta_fn):
        meta_fn.return_value = {
            "name": "dm-addr-10-112-128-0-28",
            "url": "/a/28/",
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 4,
        }
        obj = MagicMock()
        obj.pk = 28
        obj.name = "dm-addr-10-112-128-0-28"
        nodes = [
            {
                "name": "dm-addr-10-112-128-0-28",
                "url": "/a/28/",
                "ct": "10",
                "pk": "28",
                "kind": "leaf",
                "is_cell_direct": True,
                "prefix_display_cidr": "10.112.128.0/28",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {(10, 28): obj})
        self.assertIn("ipa_drilldown_meta", nodes[0])
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_ips"], 4)
        meta_fn.assert_called_once_with(obj)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_on_indirect_prefix(self, meta_fn):
        meta_fn.return_value = {
            "name": "dm-addr-10-112-128-0-28",
            "url": "/a/28/",
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 4,
        }
        obj = MagicMock()
        obj.pk = 28
        nodes = [
            {
                "name": "dm-addr-10-112-128-0-28",
                "ct": "10",
                "pk": "28",
                "kind": "leaf",
                "prefix_display_cidr": "10.112.128.0/28",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {(10, 28): obj})
        self.assertIn("ipa_drilldown_meta", nodes[0])
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_ips"], 4)
        meta_fn.assert_called_once_with(obj)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_skips_host_rows(self, meta_fn):
        nodes = [
            {
                "name": "h-10.0.0.1",
                "prefix_display_cidr": "10.0.0.1/32",
                "node_role": IPA_NODE_ROLE_HOST,
                "children": [],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {})
        self.assertNotIn("ipa_drilldown_meta", nodes[0])
        meta_fn.assert_not_called()

    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._lookup_ipam_prefix_from_ip_ref")
    def test_attach_ipa_drilldown_meta_uses_prefix_cidr_when_node_role_is_host(
        self, lookup_fn, stats_fn
    ):
        prefix = MagicMock()
        lookup_fn.return_value = prefix
        stats_fn.return_value = {
            "child_prefixes": {"count": 0},
            "ip_ranges": {"count": 0},
            "ip_addresses": {"count": 12},
        }
        nodes = [
            {
                "name": "demo-addr-host-018",
                "node_role": IPA_NODE_ROLE_HOST,
                "prefix_display_cidr": "10.199.35.0/25",
                "children": [],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {})
        self.assertIn("ipa_drilldown_meta", nodes[0])
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_ips"], 12)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._lookup_ipam_prefix_from_ip_ref")
    def test_attach_ipa_drilldown_meta_from_cidr_without_nsm_object(
        self, lookup_fn, stats_fn
    ):
        prefix = MagicMock()
        lookup_fn.side_effect = lambda ref: prefix if ref.get("str") else None
        stats_fn.return_value = {
            "child_prefixes": {"count": 0},
            "ip_ranges": {"count": 0},
            "ip_addresses": {"count": 100},
        }
        nodes = [
            {
                "name": "198.18.228.0/24",
                "prefix_display_cidr": "198.18.228.0/24",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "subnet_contained_in": "198.18.0.0/16",
                "children": [],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {})
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_ips"], 100)
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_subnets"], 0)
        lookup_fn.assert_called()
        stats_fn.assert_called_once_with(prefix)


class IpaCellTreeNetworkLinkTests(SimpleTestCase):
    def test_ensure_network_links_uses_node_url_when_ip_ref_missing(self):
        nodes = [
            {
                "name": "bench-net-00001",
                "url": "/plugins/netbox-nsm/addresses/1/",
                "ct": "10",
                "pk": "1",
                "prefix_display_cidr": "198.19.90.0/24",
                "children": [],
            }
        ]
        _ensure_ipa_cell_tree_network_links(nodes, {})
        self.assertEqual(
            nodes[0]["ip_ref"]["url"],
            "/plugins/netbox-nsm/addresses/1/",
        )
        self.assertEqual(nodes[0]["ip_ref"]["str"], "198.19.90.0/24")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._addr_ip_ref")
    def test_ensure_network_links_prefers_ipam_ref_from_object(self, ip_ref_fn):
        ip_ref_fn.return_value = {
            "str": "198.19.90.0/24",
            "url": "/ipam/prefixes/90/",
            "type": "Prefix",
        }
        obj = MagicMock()
        obj.pk = 1
        obj.get_absolute_url.return_value = "/plugins/netbox-nsm/addresses/1/"
        nodes = [
            {
                "name": "bench-net-00001",
                "url": "/plugins/netbox-nsm/addresses/1/",
                "ct": "10",
                "pk": "1",
                "prefix_display_cidr": "198.19.90.0/24",
                "children": [],
            }
        ]
        _ensure_ipa_cell_tree_network_links(nodes, {(10, 1): obj})
        self.assertEqual(nodes[0]["ip_ref"]["url"], "/ipam/prefixes/90/")


class IpaCellTreeIpamObjectRefTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._attach_addr_navigation_refs")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_cell_tree_ipam_object_for_node")
    def test_attach_ipam_object_ref_uses_description(self, ipam_obj_fn, nav_fn):
        prefix = MagicMock()
        prefix.description = "[Special] IETF: Private-Use (10.0.0.0/8)"
        prefix.prefix = "10.0.0.0/8"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/10/"
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        ipam_obj_fn.return_value = prefix

        nodes = [
            {
                "name": "bench-net-private",
                "prefix_display_cidr": "10.0.0.0/8",
                "children": [],
            }
        ]
        _attach_ipa_cell_ipam_object_refs(nodes, {})
        self.assertEqual(nodes[0]["ipam_object_ref"]["kind"], "prefix")
        self.assertEqual(
            nodes[0]["ipam_object_ref"]["description"],
            "[Special] IETF: Private-Use (10.0.0.0/8)",
        )
        self.assertEqual(nodes[0]["ipam_object_ref"]["url"], "/ipam/prefixes/10/")
        nav_fn.assert_called_once()

    def test_ipam_object_ref_prefix_without_description_returns_none(self):
        prefix = MagicMock()
        prefix.description = ""
        prefix.prefix = "10.0.0.0/8"
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        self.assertIsNone(_ipa_ipam_object_display_ref(prefix))

    def test_ipam_object_ref_uses_nsm_description_fallback(self):
        prefix = MagicMock()
        prefix.description = ""
        prefix.prefix = "10.0.0.0/8"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/10/"
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        nsm_obj = MagicMock()
        nsm_obj.description = "Policy prefix note"
        ref = _ipa_ipam_object_display_ref(prefix, nsm_obj=nsm_obj)
        self.assertEqual(ref["description"], "Policy prefix note")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._lookup_ipam_prefix_from_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_lookup_ipam_ipaddress_from_ref")
    def test_cell_tree_ipam_object_for_host_uses_prefix_display_cidr(
        self, ip_lookup_fn, prefix_lookup_fn
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_node import IPA_NODE_ROLE_HOST

        ip = MagicMock()
        ip_lookup_fn.return_value = ip
        node = {
            "name": "demo-addr-host-031",
            "prefix_display_cidr": "10.199.30.31/32",
            "ip_ref": {},
            "node_role": IPA_NODE_ROLE_HOST,
        }
        self.assertIs(_ipa_cell_tree_ipam_object_for_node(node), ip)
        ip_lookup_fn.assert_called_once_with({"str": "10.199.30.31/32"})
        prefix_lookup_fn.assert_not_called()

    def test_ipam_object_ref_ipaddress_includes_dns_name_and_description(self):
        ip = MagicMock()
        ip.description = "Gateway"
        ip.dns_name = "gw.example.com"
        ip.address = "10.0.0.1/32"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/1/"
        ip._meta.app_label = "ipam"
        ip._meta.model_name = "ipaddress"
        ref = _ipa_ipam_object_display_ref(ip)
        self.assertEqual(ref["kind"], "ipaddress")
        self.assertEqual(ref["dns_name"], "gw.example.com")
        self.assertEqual(ref["description"], "Gateway")
        self.assertEqual(ref["url"], "/ipam/ip-addresses/1/")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._attach_addr_navigation_refs")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_cell_tree_ipam_object_for_node")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_cell_address_fields")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_status")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_drilldown_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._mark_ipa_object_addr_drilldown_flags_lazy")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_object_tree_networks_from_objects")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_object_tree_cidr_from_names")
    def test_lazy_finalize_attaches_ipam_object_refs(
        self,
        cidr_fn,
        networks_fn,
        drilldown_fn,
        drilldown_meta_fn,
        status_fn,
        address_fields_fn,
        ipam_obj_fn,
        nav_fn,
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _finalize_ipa_cell_object_tree_lazy,
        )

        ip = MagicMock()
        ip.description = "Gateway"
        ip.dns_name = "gw.example.com"
        ip.address = "10.0.0.1/32"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/1/"
        ip._meta.app_label = "ipam"
        ip._meta.model_name = "ipaddress"
        ipam_obj_fn.return_value = ip

        nodes = [
            {
                "name": "bench-host",
                "prefix_display_cidr": "10.0.0.1/32",
                "ct": "10",
                "pk": "1",
                "children": [],
            }
        ]
        obj_by_key = {(10, 1): MagicMock()}

        result = _finalize_ipa_cell_object_tree_lazy(nodes, {(10, 1)}, obj_by_key)

        self.assertEqual(result[0]["ipam_object_ref"]["dns_name"], "gw.example.com")
        self.assertEqual(result[0]["ipam_object_ref"]["description"], "Gateway")
        drilldown_meta_fn.assert_called_once()

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._resolve_ipa_drilldown_meta_for_node")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._attach_addr_navigation_refs")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_cell_tree_ipam_object_for_node", return_value=None)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_cell_address_fields")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_status")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._mark_ipa_object_addr_drilldown_flags_lazy")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_object_tree_networks_from_objects")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_object_tree_cidr_from_names")
    def test_lazy_finalize_attaches_drilldown_meta_for_cell_direct_prefix(
        self,
        cidr_fn,
        networks_fn,
        drilldown_fn,
        status_fn,
        address_fields_fn,
        ipam_obj_fn,
        nav_fn,
        meta_fn,
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _finalize_ipa_cell_object_tree_lazy,
        )

        meta_fn.return_value = {
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 3,
        }
        nodes = [
            {
                "name": "bench-net-00000",
                "url": "/a/1/",
                "ct": "10",
                "pk": "1",
                "kind": "leaf",
                "prefix_display_cidr": "198.18.0.0/24",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [],
            }
        ]
        obj_by_key = {(10, 1): MagicMock()}

        result = _finalize_ipa_cell_object_tree_lazy(nodes, {(10, 1)}, obj_by_key)

        self.assertTrue(result[0].get("is_cell_direct"))
        self.assertEqual(result[0]["prefix_display_cidr"], "198.18.0.0/24")
        self.assertEqual(result[0]["ipa_drilldown_meta"]["count_ips"], 3)


class IpaCellObjectTreeTests(SimpleTestCase):
    def test_ipa_cell_object_tree_visible_always_when_nodes_exist(self):
        nodes = [{"name": "a", "children": []}, {"name": "b", "children": []}]
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 2, prefer_logical_merge=True))
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 1, prefer_logical_merge=True))
        self.assertFalse(_ipa_cell_object_tree_visible([], 1))

    def test_ipa_cell_object_tree_visible_shows_doppelt_on_single_object(self):
        nodes = [{"name": "a", "is_doppelt": True, "children": []}]
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 2))
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_build_ipa_cell_object_tree_marks_doppelt(self, build_node_fn):
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": str(kwargs.get("ct_id") or 10),
            "pk": str(obj.pk),
            "kind": "leaf",
            "children": [],
        }
        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        obj.address_type = None
        raw = [
            {"ct": "10", "pk": "5", "name": "bench-ip"},
            {"ct": "10", "pk": "5", "name": "bench-ip"},
        ]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 5): obj})
        self.assertEqual(len(nodes), 1)
        self.assertTrue(nodes[0].get("is_doppelt"))
        self.assertNotIn("object_duplicate", nodes[0])

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value=None)
    def test_build_ipa_cell_object_tree_includes_literal_any(
        self, _ip_ref_fn, _members_fn
    ):
        obj = MagicMock()
        obj.pk = 99
        obj.name = "ANY"
        obj.comments = format_network_nsm_config_comments("0.0.0.0/0").rstrip()
        obj.get_absolute_url.return_value = "#"
        obj.address_type = None
        raw = [{"ct": "10", "pk": "99", "name": "ANY"}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 99): obj})
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "ANY")
        self.assertEqual(nodes[0]["prefix_display_cidr"], "0.0.0.0/0")
        self.assertEqual(nodes[0]["node_role"], "nsm_prefix")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_build_ipa_cell_object_tree_ungrouped_direct_omits_group_pill(
        self, build_node_fn
    ):
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": str(kwargs.get("ct_id") or 10),
            "pk": str(obj.pk),
            "kind": "leaf",
            "children": [],
        }
        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        obj.address_type = None
        raw = [{"ct": "10", "pk": "5", "name": "bench-ip"}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 5): obj})
        self.assertNotIn("cell_groups", nodes[0])
        self.assertTrue(nodes[0].get("cell_groups_none"))
        self.assertFalse(nodes[0].get("cell_groups_multi"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_build_ipa_cell_object_tree_direct_plus_group_appends_none(
        self, build_node_fn, members_fn, _ip_ref_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        addr = MagicMock()
        addr.pk = 2
        addr.name = "shared-ip"
        addr.get_absolute_url.return_value = "/a/2/"
        addr.address_type = None

        group = MagicMock()
        group.pk = 10
        group.name = "group-a"
        group.get_absolute_url.return_value = "/g/a/"
        group.address_type = "address-group"
        group.address_group.all.return_value = []

        members_fn.side_effect = lambda obj: [addr] if obj is group else []
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": str(kwargs.get("ct_id") or 10),
            "pk": str(obj.pk),
            "kind": "leaf",
            "children": [],
        }

        raw = [
            {"ct": "10", "pk": "10", "name": "group-a"},
            {"ct": "10", "pk": "2", "name": "shared-ip"},
        ]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 2): addr, (10, 10): group})
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["group-a"],
        )
        self.assertFalse(nodes[0].get("cell_groups_multi"))
        self.assertFalse(nodes[0].get("cell_groups_none"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_build_ipa_cell_object_tree_direct_plus_multi_groups_appends_none(
        self, build_node_fn, members_fn, content_type_cls
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _apply_node_cell_groups

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        addr = MagicMock()
        addr.pk = 2
        addr.name = "shared-ip"
        addr.get_absolute_url.return_value = "/a/2/"
        addr.address_type = None

        group_a = MagicMock()
        group_a.pk = 10
        group_a.name = "group-a"
        group_a.get_absolute_url.return_value = "/g/a/"
        group_a.address_type = "address-group"

        group_b = MagicMock()
        group_b.pk = 11
        group_b.name = "group-b"
        group_b.get_absolute_url.return_value = "/g/b/"
        group_b.address_type = "address-group"

        members_fn.side_effect = lambda obj: (
            [addr] if obj in (group_a, group_b) else []
        )
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": str(kwargs.get("ct_id") or 10),
            "pk": str(obj.pk),
            "kind": "leaf",
            "children": [],
        }

        raw = [
            {"ct": "10", "pk": "2", "name": "shared-ip"},
            {"ct": "10", "pk": "10", "name": "group-a"},
            {"ct": "10", "pk": "11", "name": "group-b"},
        ]
        nodes = _build_ipa_cell_object_tree(
            raw, {(10, 2): addr, (10, 10): group_a, (10, 11): group_b}
        )
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["group-a", "group-b", "none"],
        )
        self.assertTrue(nodes[0].get("cell_groups_multi"))
        self.assertFalse(nodes[0].get("cell_groups_none"))

        node = {"name": "filter-test", "kind": "leaf", "children": []}
        _apply_node_cell_groups(
            node,
            [
                {"name": "group-a", "url": "/g/a/"},
                {"name": "group-b", "url": "/g/b/"},
            ],
            is_cell_direct=True,
        )
        self.assertEqual(
            [g["name"] for g in node.get("cell_groups") or []],
            ["group-a", "group-b", "none"],
        )
        self.assertTrue(node.get("cell_groups_multi"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value=None)
    def test_build_ipa_cell_object_tree_marks_shared_member_duplicate(
        self, _ip_ref, members_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct
        shared = MagicMock()
        shared.pk = 2
        shared.name = "shared-ip"
        shared.get_absolute_url.return_value = "/a/2/"

        group_a = MagicMock()
        group_a.pk = 10
        group_a.name = "group-a"
        group_a.get_absolute_url.return_value = "/g/a/"
        group_a.address_type = None

        group_b = MagicMock()
        group_b.pk = 11
        group_b.name = "group-b"
        group_b.get_absolute_url.return_value = "/g/b/"
        group_b.address_type = None

        members_fn.side_effect = lambda obj: (
            [shared] if obj in (group_a, group_b) else []
        )

        raw = [
            {"ct": "10", "pk": "10", "name": "group-a"},
            {"ct": "10", "pk": "11", "name": "group-b"},
        ]
        obj_by_key = {(10, 10): group_a, (10, 11): group_b}
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "shared-ip")
        self.assertTrue(nodes[0].get("cell_groups_multi"))
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["group-a", "group-b"],
        )
        self.assertNotIn("object_duplicate", nodes[0])

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_cell_object_tree_merges_same_network_once(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def attach_meta(node, obj):
            node["ip_ref"] = {
                "str": "10.112.134.0/24",
                "url": f"/ipam/prefixes/{obj.pk}/",
            }
            node["prefix_display_cidr"] = "10.112.134.0/24"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.return_value = {
            "str": "10.112.134.0/24",
            "url": "/ipam/prefixes/13/",
            "type": "Prefix",
        }

        def make_obj(pk, name, *, cell_direct=False):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        addr_a = make_obj(13, "dm-addr-10-112-134-0-24", cell_direct=True)
        addr_b = make_obj(99, "diff-test-10-112-134-0-24")

        raw = [
            {"ct": "10", "pk": "13", "name": addr_a.name},
            {"ct": "10", "pk": "99", "name": addr_b.name},
        ]
        nodes = _build_ipa_cell_object_tree(
            raw, {(10, 13): addr_a, (10, 99): addr_b}
        )

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["prefix_display_cidr"], "10.112.134.0/24")
        self.assertEqual(nodes[0]["name"], "dm-addr-10-112-134-0-24")
        self.assertTrue(nodes[0].get("is_cell_direct"))
        self.assertTrue(nodes[0].get("cell_addresses_multi"))
        self.assertEqual(
            [a["name"] for a in nodes[0].get("cell_addresses") or []],
            ["dm-addr-10-112-134-0-24", "diff-test-10-112-134-0-24"],
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_cell_object_tree_nests_host_under_prefix(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def attach_meta(node, obj):
            if obj.name.startswith("h-"):
                node["ip_ref"] = {
                    "str": "10.112.134.44/32",
                    "url": "/ipam/ip-addresses/44/",
                    "type": "IP Address",
                }
                node["prefix_display_cidr"] = "10.112.134.44/32"
                node["node_role"] = "nsm_host"
            else:
                node["ip_ref"] = {
                    "str": "10.112.134.0/24",
                    "url": "/ipam/prefixes/13/",
                    "type": "Prefix",
                }
                node["prefix_display_cidr"] = "10.112.134.0/24"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: attach_meta({}, obj).get("ip_ref")

        def make_obj(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        prefix = make_obj(13, "dm-addr-10-112-134-0-24")
        host = make_obj(44, "h-10.112.134.44")
        raw = [
            {"ct": "10", "pk": "13", "name": prefix.name},
            {"ct": "10", "pk": "44", "name": host.name},
        ]
        nodes = _build_ipa_cell_object_tree(
            raw, {(10, 13): prefix, (10, 44): host}
        )

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["prefix_display_cidr"], "10.112.134.0/24")
        self.assertEqual(len(nodes[0]["children"]), 1)
        self.assertEqual(nodes[0]["children"][0]["name"], "h-10.112.134.44")
        self.assertEqual(
            nodes[0]["children"][0].get("subnet_contained_in"),
            "10.112.134.0/24",
        )
        self.assertEqual(
            nodes[0]["children"][0].get("subnet_containment_display_net"),
            "10.112.134.44",
        )
        self.assertTrue(nodes[0].get("ipa_open_by_default"))
        self.assertNotIn("ipa_open_by_default", nodes[0]["children"][0])

    def test_mark_ipa_cell_open_by_default_skips_non_cell_direct_drilldown(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
            {
                "name": "bench-ip",
                "kind": "leaf",
                "ct": "10",
                "pk": "5",
                "addr_drilldown_lazy": True,
                "children": [],
            }
        ]
        _mark_ipa_cell_open_by_default(nodes)
        self.assertNotIn("ipa_open_by_default", nodes[0])

    def test_mark_ipa_cell_open_by_default_opens_ancestor_of_cell_direct_leaf(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
            {
                "name": "g-10.0.0.0/8",
                "kind": "group",
                "children": [
                    {
                        "name": "h-10.112.134.44",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "children": [],
                    }
                ],
            }
        ]
        _mark_ipa_cell_open_by_default(nodes)
        self.assertTrue(nodes[0].get("ipa_open_by_default"))
        self.assertNotIn("ipa_open_by_default", nodes[0]["children"][0])
        nodes = [
            {
                "name": "addr-a",
                "ct": "10",
                "pk": "1",
                "kind": "leaf",
                "prefix_display_cidr": "10.112.134.0/24",
                "cell_groups": [{"name": "grp-a", "url": "/g/a/"}],
                "children": [],
            },
            {
                "name": "addr-b",
                "ct": "10",
                "pk": "2",
                "kind": "leaf",
                "prefix_display_cidr": "10.112.134.0/24",
                "cell_groups": [{"name": "grp-b", "url": "/g/b/"}],
                "cell_groups_multi": True,
                "children": [],
            },
        ]
        merged = _merge_ipa_cell_nodes_by_network(nodes)
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            [g["name"] for g in merged[0].get("cell_groups") or []],
            ["grp-a", "grp-b"],
        )
        self.assertTrue(merged[0].get("cell_groups_multi"))

    def test_prune_ipa_object_tree_removes_duplicate_identities(self):
        nodes = [
            {
                "name": "first",
                "ct": "10",
                "pk": "1",
                "kind": "leaf",
                "children": [
                    {
                        "name": "dup-child",
                        "ct": "10",
                        "pk": "2",
                        "kind": "leaf",
                        "object_duplicate": True,
                        "children": [],
                    }
                ],
            },
            {
                "name": "second",
                "ct": "10",
                "pk": "3",
                "kind": "leaf",
                "object_duplicate": True,
                "children": [],
            },
        ]
        pruned = _prune_ipa_object_tree_duplicate_nodes(nodes)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["name"], "first")
        self.assertEqual(pruned[0]["children"], [])

    def test_prune_ipa_object_tree_removes_duplicate_networks(self):
        nodes = [
            {
                "name": "first",
                "prefix_display_cidr": "10.112.134.0/24",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "second",
                "prefix_display_cidr": "10.112.134.0/24",
                "kind": "leaf",
                "children": [],
            },
        ]
        pruned = _prune_ipa_object_tree_duplicate_nodes(nodes)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["name"], "first")

    def test_ipa_object_tree_sort_key_orders_by_network_then_prefixlen(self):
        nodes = [
            {
                "name": "b",
                "prefix_display_cidr": "172.16.0.0/12",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "a",
                "prefix_display_cidr": "10.112.134.0/24",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "c",
                "prefix_display_cidr": "10.112.129.0/24",
                "kind": "leaf",
                "children": [],
            },
        ]
        ordered = _sort_ipa_object_tree_siblings(nodes)
        self.assertEqual(
            [n["prefix_display_cidr"] for n in ordered],
            ["10.112.129.0/24", "10.112.134.0/24", "172.16.0.0/12"],
        )

    def test_ipa_object_tree_sort_key_orders_prefix_before_higher_hosts(self):
        """198.18.0.0/24 must sort before 198.19.240.x/32 (bench overlap cells)."""
        nodes = [
            {
                "name": "bench-ip-00049698",
                "node_role": "nsm_host",
                "ip_ref": {
                    "str": "198.19.240.98/32",
                    "url": "#",
                    "type": "IP Address",
                },
                "prefix_display_cidr": "198.19.240.98/32",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "bench-ip-00049699",
                "node_role": "nsm_host",
                "ip_ref": {
                    "str": "198.19.240.99/32",
                    "url": "#",
                    "type": "IP Address",
                },
                "prefix_display_cidr": "198.19.240.99/32",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "bench-net-00000",
                "node_role": "nsm_prefix",
                "ip_ref": {"str": "198.18.0.0/24", "url": "#", "type": "Prefix"},
                "kind": "leaf",
                "children": [],
            },
        ]
        ordered = _sort_ipa_object_tree_siblings(nodes)
        self.assertEqual(
            [n["name"] for n in ordered],
            ["bench-net-00000", "bench-ip-00049698", "bench-ip-00049699"],
        )

    def test_merge_ipa_cell_nodes_by_network_keeps_other_children(self):
        """Same-network merge must not drop the merged node's subtree."""
        nodes = [
            {
                "name": "198.18.0.0/20",
                "prefix_display_cidr": "198.18.0.0/20",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "kind": "group",
                "children": [
                    {
                        "name": "bench-grp-00000",
                        "prefix_display_cidr": "198.18.0.0/24",
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "kind": "group",
                        "children": [],
                    }
                ],
            },
            {
                "name": "198.18.0.0/20",
                "prefix_display_cidr": "198.18.0.0/20",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "kind": "group",
                "children": [
                    {
                        "name": "bench-grp-00001",
                        "prefix_display_cidr": "198.18.1.0/24",
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "kind": "group",
                        "children": [],
                    }
                ],
            },
        ]
        merged = _merge_ipa_cell_nodes_by_network(nodes)
        self.assertEqual(len(merged), 1)
        child_names = {c["name"] for c in merged[0].get("children") or []}
        self.assertEqual(child_names, {"bench-grp-00000", "bench-grp-00001"})

    def test_collapse_siblings_keeps_all_groups_under_shared_filler(self):
        """Group rows sharing one synthesized /20 parent must all survive collapse."""

        def _grp(name, cidr):
            return {
                "name": name,
                "prefix_display_cidr": cidr,
                "node_role": IPA_NODE_ROLE_GROUP,
                "kind": "group",
                "children": [],
            }

        def _filler(child):
            return {
                "name": "198.18.0.0/20",
                "prefix_display_cidr": "198.18.0.0/20",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "ipa_tree_node_type": IPA_TREE_NODE_IPAM_FILLER,
                "is_ipam_filler": True,
                "kind": "group",
                "children": [child],
            }

        super_node = {
            "name": "bench-net-super-00000",
            "prefix_display_cidr": "198.18.0.0/16",
            "node_role": IPA_NODE_ROLE_PREFIX,
            "kind": "group",
            "children": [
                _filler(_grp("bench-grp-00001", "198.18.1.0/24")),
                _filler(_grp("bench-grp-00002", "198.18.2.0/24")),
                _filler(_grp("bench-grp-00003", "198.18.3.0/24")),
            ],
        }
        collapsed = _collapse_ipa_cell_siblings_by_network([super_node])
        self.assertEqual(len(collapsed), 1)
        fillers = collapsed[0].get("children") or []
        self.assertEqual(len(fillers), 1, msg="the /20 fillers should collapse to one")
        group_names = {c["name"] for c in fillers[0].get("children") or []}
        self.assertEqual(
            group_names,
            {"bench-grp-00001", "bench-grp-00002", "bench-grp-00003"},
        )

    def test_merge_ipa_cell_nodes_by_network_sorts_unkeyed_after_network(self):
        nodes = [
            {
                "name": "host",
                "prefix_display_cidr": "198.19.240.98/32",
                "kind": "leaf",
                "children": [],
            },
            {
                "name": "subnet",
                "prefix_display_cidr": "198.18.0.0/24",
                "kind": "leaf",
                "children": [],
            },
        ]
        merged = _merge_ipa_cell_nodes_by_network(nodes)
        self.assertEqual(
            [n["name"] for n in merged],
            ["subnet", "host"],
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_prefix_for_cell_object", return_value=None)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_cell_object_tree_sorts_prefix_before_higher_hosts(
        self, content_type_cls, ip_ref_fn, _members_fn, _visible_fn, _stats_fn, _prefix_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def make_obj(pk, name, cidr, ref_type):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            obj.ip_address = None
            obj.range = None
            obj.prefix = None
            obj._addr = {
                "str": cidr,
                "url": f"/ipam/{pk}/",
                "type": ref_type,
                "ct": 10,
                "pk": pk,
            }
            return obj

        host98 = make_obj(98, "bench-ip-00049698", "198.19.240.98/32", "IP Address")
        host99 = make_obj(99, "bench-ip-00049699", "198.19.240.99/32", "IP Address")
        host100 = make_obj(100, "bench-ip-00049700", "198.19.240.100/32", "IP Address")
        subnet = make_obj(1, "bench-net-00000", "198.18.0.0/24", "Prefix")

        ip_ref_fn.side_effect = lambda obj: obj._addr

        raw = [
            {"ct": "10", "pk": str(host98.pk), "name": host98.name},
            {"ct": "10", "pk": str(host99.pk), "name": host99.name},
            {"ct": "10", "pk": str(host100.pk), "name": host100.name},
            {"ct": "10", "pk": str(subnet.pk), "name": subnet.name},
        ]
        obj_by_key = {
            (10, host98.pk): host98,
            (10, host99.pk): host99,
            (10, host100.pk): host100,
            (10, subnet.pk): subnet,
        }
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)
        self.assertEqual(
            [n["name"] for n in nodes],
            [
                "bench-net-00000",
                "bench-ip-00049698",
                "bench-ip-00049699",
                "bench-ip-00049700",
            ],
        )

    def test_sort_ipa_object_tree_siblings_recurses_into_children(self):
        nodes = [
            {
                "name": "parent",
                "prefix_display_cidr": "10.0.0.0/8",
                "kind": "group",
                "children": [
                    {
                        "name": "child-b",
                        "prefix_display_cidr": "10.112.137.0/24",
                        "kind": "leaf",
                        "children": [],
                    },
                    {
                        "name": "child-a",
                        "prefix_display_cidr": "10.112.129.0/24",
                        "kind": "leaf",
                        "children": [],
                    },
                ],
            }
        ]
        ordered = _sort_ipa_object_tree_siblings(nodes)
        self.assertEqual(
            [c["prefix_display_cidr"] for c in ordered[0]["children"]],
            ["10.112.129.0/24", "10.112.137.0/24"],
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_nested_group_member_gets_addr_drilldown_lazy(
        self, content_type_cls, members_fn, ip_ref_fn, _attach_fn, _stats_fn, _visible_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        member = MagicMock()
        member.pk = 2
        member.name = "dm-addr-10-112-137-0-24"
        member.get_absolute_url.return_value = "/a/2/"
        member.address_type = None

        group = MagicMock()
        group.pk = 5
        group.name = "dm-grp-005"
        group.get_absolute_url.return_value = "/g/5/"
        group.address_type = "address-group"

        members_fn.side_effect = lambda obj: [member] if obj is group else []
        ip_ref_fn.side_effect = lambda obj: (
            {
                "str": "10.112.137.0/24",
                "url": "/ipam/prefixes/2/",
                "type": "Prefix",
                "ct": 99,
                "pk": 2,
            }
            if obj is member
            else None
        )

        raw = [{"ct": "10", "pk": "5", "name": "dm-grp-005"}]
        obj_by_key = {(10, 5): group}
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "dm-addr-10-112-137-0-24")
        self.assertEqual(nodes[0]["kind"], "group")
        self.assertTrue(nodes[0].get("addr_drilldown_lazy"))
        self.assertEqual(nodes[0]["ip_ref"]["str"], "10.112.137.0/24")
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["dm-grp-005"],
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
    def test_mark_addr_drilldown_lazy_skipped_when_no_visible_content(self, _visible_fn):
        nodes = [
            {
                "name": "dm-addr-10-112-160-0-28",
                "ct": "275",
                "pk": "42",
                "ip_ref": {"str": "10.112.160.0/28"},
                "children": [],
            }
        ]
        obj = MagicMock()
        _mark_ipa_object_addr_drilldown_flags(nodes, {(275, 42): obj})
        self.assertNotIn("addr_drilldown_lazy", nodes[0])

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    def test_mark_addr_drilldown_lazy_skipped_without_resolved_object(self, _visible_fn):
        nodes = [
            {
                "name": "dm-addr-10-112-160-0-28",
                "ct": "275",
                "pk": "42",
                "ip_ref": {"str": "10.112.160.0/28"},
                "children": [],
            }
        ]
        _mark_ipa_object_addr_drilldown_flags(nodes, {})
        self.assertNotIn("addr_drilldown_lazy", nodes[0])

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipam_drilldown._lookup_ipam_prefix_from_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_nested_group_member_drilldown_without_ip_ref_type(
        self, content_type_cls, members_fn, ip_ref_fn, _attach_fn, lookup_fn, stats_fn, _visible_fn
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        member = MagicMock()
        member.pk = 2
        member.name = "dm-addr-10-112-137-0-24"
        member.get_absolute_url.return_value = "/a/2/"
        member.address_type = None

        group = MagicMock()
        group.pk = 5
        group.name = "dm-grp-005"
        group.get_absolute_url.return_value = "/g/5/"
        group.address_type = "address-group"

        members_fn.side_effect = lambda obj: [member] if obj is group else []
        ip_ref_fn.side_effect = lambda obj: (
            {
                "str": "10.112.137.0/24",
                "url": "/ipam/prefixes/2/",
                "ct": 99,
                "pk": 2,
            }
            if obj is member
            else None
        )
        lookup_fn.return_value = MagicMock()
        stats_fn.return_value = {
            "child_prefixes": {"count": 0, "label": "Prefixes", "url": "#"},
            "ip_addresses": {"count": 3, "label": "IP Addresses", "url": "#"},
            "ip_ranges": {"count": 0, "label": "IP Ranges", "url": "#"},
        }

        raw = [{"ct": "10", "pk": "5", "name": "dm-grp-005"}]
        obj_by_key = {(10, 5): group}
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        child = nodes[0]
        self.assertTrue(child.get("addr_drilldown_lazy"))
        self.assertTrue(child.get("ipam_stats"))
        self.assertEqual(child["kind"], "group")
        self.assertEqual(
            [g["name"] for g in child.get("cell_groups") or []],
            ["dm-grp-005"],
        )

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value=None)
    def test_build_ipa_cell_object_tree_collapses_members_under_parent(
        self, _ip_ref, members_fn, _attach_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        member_a = MagicMock()
        member_a.pk = 1
        member_a.name = "objekt 1"
        member_a.get_absolute_url.return_value = "/a/1/"
        member_a.address_type = None

        member_b = MagicMock()
        member_b.pk = 2
        member_b.name = "objekt 2"
        member_b.get_absolute_url.return_value = "/a/2/"
        member_b.address_type = None

        parent = MagicMock()
        parent.pk = 3
        parent.name = "Objekt 3"
        parent.get_absolute_url.return_value = "/g/3/"
        parent.address_type = "address-group"

        members_fn.side_effect = (
            lambda obj: [member_a, member_b] if obj is parent else []
        )

        raw = [
            {"ct": "10", "pk": "1", "name": "objekt 1"},
            {"ct": "10", "pk": "2", "name": "objekt 2"},
            {"ct": "10", "pk": "3", "name": "Objekt 3"},
        ]
        obj_by_key = {(10, 1): member_a, (10, 2): member_b, (10, 3): parent}
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 2)
        by_name = {n["name"]: n for n in nodes}
        self.assertIn("objekt 1", by_name)
        self.assertIn("objekt 2", by_name)
        self.assertEqual(
            [g["name"] for g in by_name["objekt 1"].get("cell_groups") or []],
            ["Objekt 3"],
        )
        self.assertTrue(by_name["objekt 1"].get("is_cell_direct"))
        self.assertTrue(by_name["objekt 2"].get("is_cell_direct"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    def test_build_ipa_cell_object_tree_nests_by_ip_containment(
        self, ip_ref_fn, _members_fn, attach_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def attach_meta(node, obj):
            refs = {
                1: {"str": "10.1.0.0/16", "url": "#", "type": "Prefix"},
                2: {"str": "10.1.1.1/32", "url": "#", "type": "Prefix"},
                3: {"str": "10.0.0.0/8", "url": "#", "type": "Prefix"},
            }
            ip_ref = refs[obj.pk]
            node["ip_ref"] = {"str": ip_ref["str"], "url": ip_ref["url"]}
            node["prefix_display_cidr"] = ip_ref["str"]
            node["kind"] = "leaf" if not node.get("children") else "group"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: {
            1: {"str": "10.1.0.0/16", "url": "#", "type": "Prefix"},
            2: {"str": "10.1.1.1/32", "url": "#", "type": "Prefix"},
            3: {"str": "10.0.0.0/8", "url": "#", "type": "Prefix"},
        }[obj.pk]

        def make_obj(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        obj_by_key = {
            (10, 1): make_obj(1, "objekt 1"),
            (10, 2): make_obj(2, "objekt 2"),
            (10, 3): make_obj(3, "Objekt 3"),
        }
        raw = [
            {"ct": "10", "pk": "1", "name": "objekt 1"},
            {"ct": "10", "pk": "2", "name": "objekt 2"},
            {"ct": "10", "pk": "3", "name": "Objekt 3"},
        ]
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Objekt 3")
        self.assertNotIn("subnet_contained_in", nodes[0])
        children = nodes[0]["children"]
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0]["name"], "objekt 1")
        self.assertEqual(children[0]["subnet_contained_in"], "10.0.0.0/8")
        grandchildren = children[0]["children"]
        self.assertEqual(len(grandchildren), 1)
        self.assertEqual(grandchildren[0]["name"], "objekt 2")
        self.assertEqual(grandchildren[0]["subnet_contained_in"], "10.0.0.0/8")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    def test_build_ipa_cell_object_tree_nests_by_ipam_prefix_hierarchy(
        self, attach_fn, _members_fn, content_type_cls, _stats_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        slash8 = MagicMock(spec=Prefix)
        slash8.pk = 99
        slash8.prefix = ipaddress.ip_network("10.0.0.0/8")
        slash8.__str__ = MagicMock(return_value="10.0.0.0/8")
        slash8.get_absolute_url.return_value = "/ipam/prefixes/99/"

        p24a = MagicMock(spec=Prefix)
        p24a.pk = 1
        p24a.prefix = ipaddress.ip_network("10.0.130.0/24")
        p24a.get_parents.return_value = [slash8]

        p24b = MagicMock(spec=Prefix)
        p24b.pk = 2
        p24b.prefix = ipaddress.ip_network("10.0.143.0/24")
        p24b.get_parents.return_value = [slash8]

        def attach_meta(node, obj):
            refs = {
                1: {"str": "10.0.130.0/24", "url": "/p/1/", "type": "Prefix"},
                2: {"str": "10.0.143.0/24", "url": "/p/2/", "type": "Prefix"},
            }
            if obj.pk not in refs:
                return node
            ip_ref = refs[obj.pk]
            node["ip_ref"] = {"str": ip_ref["str"], "url": ip_ref["url"]}
            node["prefix_display_cidr"] = ip_ref["str"]
            node["kind"] = "leaf"
            return node

        attach_fn.side_effect = attach_meta

        def make_addr(pk, name, prefix):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            obj.prefix = prefix
            obj.ip_address = None
            obj.range = None
            return obj

        group = MagicMock()
        group.pk = 10
        group.name = "g-10.0.0.0/8"
        group.get_absolute_url.return_value = "/g/10/"
        group.address_type = "address-group"
        group.prefix = None
        group.ip_address = None
        group.range = None

        obj_by_key = {
            (10, 10): group,
            (10, 1): make_addr(1, "bench-ip-0013031", p24a),
            (10, 2): make_addr(2, "bench-ip-0014328", p24b),
        }
        raw = [
            {"ct": "10", "pk": "1", "name": "bench-ip-0013031"},
            {"ct": "10", "pk": "2", "name": "bench-ip-0014328"},
            {"ct": "10", "pk": "10", "name": "g-10.0.0.0/8"},
        ]

        def prefix_filter(**kwargs):
            qs = MagicMock()
            if kwargs.get("prefix") == "10.0.0.0/8":
                qs.order_by.return_value.first.return_value = slash8
            else:
                qs.order_by.return_value.first.return_value = None
            return qs

        with patch.object(Prefix.objects, "filter", side_effect=prefix_filter):
            nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "g-10.0.0.0/8")
        self.assertEqual(nodes[0].get("prefix_display_cidr"), "10.0.0.0/8")
        child_names = [c["name"] for c in nodes[0].get("children") or []]
        self.assertEqual(child_names, ["bench-ip-0013031", "bench-ip-0014328"])
        for child in nodes[0]["children"]:
            self.assertEqual(child.get("subnet_contained_in"), "10.0.0.0/8")
            self.assertEqual(child.get("subnet_contained_in_name"), "g-10.0.0.0/8")
            self.assertIn("subnet_containment_display_net", child)
            self.assertTrue(child.get("is_cell_direct"))
        self.assertTrue(nodes[0].get("is_cell_direct"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value=None)
    def test_build_ipa_cell_object_tree_cell_direct_only_for_raw_selections(
        self, _ip_ref, members_fn, _attach_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        nested = MagicMock()
        nested.pk = 20
        nested.name = "n-10.0.0.0/8"
        nested.get_absolute_url.return_value = "/n/20/"
        nested.address_type = None

        group = MagicMock()
        group.pk = 10
        group.name = "g-10.0.0.0/8"
        group.get_absolute_url.return_value = "/g/10/"
        group.address_type = "address-group"

        members_fn.side_effect = lambda obj: [nested] if obj is group else []

        raw = [{"ct": "10", "pk": "10", "name": "g-10.0.0.0/8"}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 10): group, (10, 20): nested})

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "n-10.0.0.0/8")
        self.assertFalse(nodes[0].get("is_cell_direct"))
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["g-10.0.0.0/8"],
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref", return_value={"str": "10.1.0.0/16", "url": "#", "type": "Prefix"})
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_object_tree_node_attaches_ip_ref(
        self, content_type_cls, _ip_ref, _attach_fn
    ):
        from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import _build_ipa_object_tree_node

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        obj.get_absolute_url.return_value = "/a/5/"
        obj.address_type = None

        node = _build_ipa_object_tree_node(obj)
        self.assertEqual(node["kind"], "group")
        self.assertEqual(node["node_role"], IPA_NODE_ROLE_PREFIX)
        self.assertEqual(node["ip_ref"]["str"], "10.1.0.0/16")
        self.assertEqual(node["ip_ref"]["type"], "Prefix")
        self.assertNotIn("is_cell_direct", node)

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._resolve_ipam_stats_from_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_resolve_summary_type_counts_from_object_tree_prefix_refs(
        self, content_type_cls, _members_fn, ip_ref_fn, resolve_stats_fn, _attach_fn
    ):

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def make_addr(pk, name, cidr):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        addr_a = make_addr(1, "dm-addr-10-112-129-0-24", "10.112.129.0/24")
        addr_b = make_addr(2, "dm-addr-10-112-141-0-24", "10.112.141.0/24")
        ip_ref_fn.side_effect = lambda obj: {
            "str": "10.112.129.0/24" if obj.pk == 1 else "10.112.141.0/24",
            "url": f"/ipam/prefixes/{obj.pk}/",
            "type": "Prefix",
            "ct": 99,
            "pk": obj.pk,
        }
        resolve_stats_fn.side_effect = lambda ref: {
            "child_prefixes": {"count": 0, "label": "Prefixes", "url": "#"},
            "ip_addresses": {
                "count": 3 if "129" in str(ref.get("str") or "") else 7,
                "label": "IP Addresses",
                "url": "#",
            },
            "ip_ranges": {"count": 0, "label": "IP Ranges", "url": "#"},
        }

        raw = [
            {"ct": "10", "pk": "1", "name": addr_a.name},
            {"ct": "10", "pk": "2", "name": addr_b.name},
        ]
        obj_by_key = {(10, 1): addr_a, (10, 2): addr_b}
        object_tree = _build_ipa_cell_object_tree(raw, obj_by_key)
        counts = _resolve_summary_type_counts([], object_tree)

        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 0)

    def test_count_ipa_object_tree_group_duplicates(self):
        tree = [
            {
                "name": "a",
                "cell_groups_multi": True,
                "children": [
                    {"name": "child", "cell_groups_multi": False, "children": []},
                ],
            },
            {"name": "b", "cell_groups_multi": False, "children": []},
        ]
        self.assertEqual(_count_ipa_object_tree_group_duplicates(tree), 1)
        counts = _resolve_summary_type_counts([], tree)
        self.assertEqual(counts["count_group_duplicates"], 1)

    def test_resolve_summary_type_counts_matches_visible_cell_tree_networks(self):
        tree = [
            {
                "name": "bench-net-super-00000",
                "prefix_display_cidr": "198.18.0.0/16",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-net-00000",
                        "prefix_display_cidr": "198.18.0.0/24",
                        "node_role": IPA_NODE_ROLE_PREFIX,
                        "subnet_contained_in": "198.18.0.0/16",
                        "children": [
                            {
                                "name": "bench-ip-0000000",
                                "prefix_display_cidr": "198.18.0.1/32",
                                "node_role": IPA_NODE_ROLE_HOST,
                                "subnet_contained_in": "198.18.0.0/24",
                                "children": [],
                            }
                        ],
                    },
                    {
                        "name": "bench-grp-00001",
                        "prefix_display_cidr": "198.18.1.0/24",
                        "kind": "group",
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "subnet_contained_in": "198.18.0.0/16",
                        "children": [],
                    },
                    {
                        "name": "198.18.2.0/24",
                        "prefix_display_cidr": "198.18.2.0/24",
                        "ipa_tree_node_type": IPA_TREE_NODE_IPAM_FILLER,
                        "is_ipam_filler": True,
                        "ipam_synthetic": True,
                        "children": [],
                    },
                ],
            }
        ]

        counts = _resolve_summary_type_counts([], tree)

        self.assertEqual(counts["count_subnets"], 3)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 1)

    def test_ipam_ip_keys_skips_large_prefix_enumeration(self):
        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.get_child_ips.return_value = MagicMock(count=MagicMock(return_value=50000))

        keys, resolved = _ipa_ipam_ip_keys_for_object(prefix)
        self.assertFalse(resolved)
        self.assertEqual(keys, set())
        prefix.get_child_ips.return_value.values_list.assert_not_called()

    def test_cell_tree_type_counts_falls_back_for_large_prefix(self):
        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.get_child_ips.return_value = MagicMock(
            count=MagicMock(return_value=IPA_IPAM_CHILD_IP_ENUM_MAX + 1)
        )

        tree = [
            {
                "name": "big-net",
                "prefix_display_cidr": "10.0.0.0/8",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "host-a",
                        "prefix_display_cidr": "10.0.0.1/32",
                        "node_role": IPA_NODE_ROLE_HOST,
                        "children": [],
                    }
                ],
            }
        ]

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_cell_tree_ipam_object_for_node",
            return_value=prefix,
        ):
            counts = _ipa_cell_object_tree_type_counts(tree)

        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ips"], 1)

    def test_attach_ipam_refs_tolerates_unresolved_custom_object_type(self):
        obj = MagicMock()
        obj.pk = 42
        obj.custom_object_type = MagicMock()
        nodes = [{"ct": "10", "pk": "42", "name": "demo", "children": []}]
        obj_by_key = {(10, 42): obj}

        _attach_ipa_cell_ipam_object_refs(nodes, obj_by_key)
        self.assertNotIn("related_refs", nodes[0])

    def test_summary_counts_include_group_anchor_networks(self):
        tree = [
            {
                "name": "bench-net-super-00000",
                "prefix_display_cidr": "198.18.0.0/16",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-grp-00001",
                        "url": "/g/1/",
                        "ct": "10",
                        "pk": "101",
                        "kind": "group",
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "is_cell_direct": True,
                        "prefix_display_cidr": "198.18.1.0/24",
                        "children": [],
                    },
                    {
                        "name": "bench-grp-00002",
                        "url": "/g/2/",
                        "ct": "10",
                        "pk": "102",
                        "kind": "group",
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "is_cell_direct": True,
                        "prefix_display_cidr": "198.18.2.0/24",
                        "children": [],
                    },
                ],
            }
        ]

        counts = _resolve_summary_type_counts([], tree)

        self.assertEqual(counts["count_subnets"], 3)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 0)

    def test_group_coverage_marks_visible_and_membership_groups(self):
        group_visible = MagicMock()
        group_visible.pk = 101
        group_visible.name = "bench-grp-00001"
        group_visible.address_type = "address-group"
        group_visible.get_absolute_url.return_value = "/g/1/"
        group_merged = MagicMock()
        group_merged.pk = 102
        group_merged.name = "bench-grp-00002"
        group_merged.address_type = "address-group"
        group_merged.get_absolute_url.return_value = "/g/2/"
        member = MagicMock()
        member.pk = 201
        member.name = "bench-net-00002"
        member.address_type = None
        member.get_absolute_url.return_value = "/a/201/"

        tree = [
            {
                "name": "bench-grp-00001",
                "url": "/g/1/",
                "ct": "10",
                "pk": "101",
                "kind": "group",
                "node_role": IPA_NODE_ROLE_GROUP,
                "is_cell_direct": True,
                "prefix_display_cidr": "198.18.1.0/24",
                "children": [],
            },
            {
                "name": "bench-net-00002",
                "url": "/a/201/",
                "ct": "10",
                "pk": "201",
                "kind": "leaf",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "prefix_display_cidr": "198.18.2.0/24",
                "cell_groups": [{"name": "bench-grp-00002", "url": "/g/2/"}],
                "children": [],
            },
        ]
        raw = [
            {"ct": "10", "pk": "101", "name": "bench-grp-00001"},
            {"ct": "10", "pk": "102", "name": "bench-grp-00002"},
        ]

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_group_members",
            side_effect=lambda obj: [member],
        ):
            coverage = _build_ipa_group_coverage(
                raw,
                {(10, 101): group_visible, (10, 102): group_merged},
                tree,
            )

        self.assertEqual(coverage["summary"], {"total": 2, "visible": 1, "membership": 1, "missing": 0})
        states = {item["name"]: item["state"] for item in coverage["groups"]}
        self.assertEqual(states["bench-grp-00001"], "visible")
        self.assertEqual(states["bench-grp-00002"], "membership")

    def test_extended_summary_counts_expose_coverage_and_directness(self):
        tree = [
            {
                "name": "direct",
                "ct": "10",
                "pk": "1",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "is_cell_direct": True,
                "prefix_display_cidr": "10.0.0.0/24",
                "children": [],
            },
            {
                "name": "indirect",
                "ct": "10",
                "pk": "2",
                "node_role": IPA_NODE_ROLE_HOST,
                "prefix_display_cidr": "10.0.0.1/32",
                "status": "deprecated",
                "children": [],
            },
        ]
        coverage = {"summary": {"total": 3, "membership": 1}}

        extra = _ipa_cell_tree_extended_summary_counts(tree, coverage)

        self.assertEqual(extra["count_groups"], 3)
        self.assertEqual(extra["count_hidden_merged"], 1)
        self.assertEqual(extra["count_addresses"], 2)
        self.assertEqual(extra["count_non_active"], 1)
        self.assertEqual(extra["count_direct"], 1)
        self.assertEqual(extra["count_indirect"], 1)

    def test_attach_explain_fields_adds_row_reason_tooltip(self):
        tree = [
            {
                "name": "bench-ip-0000000",
                "is_cell_direct": True,
                "prefix_display_cidr": "198.18.0.1/32",
                "cell_groups": [{"name": "bench-grp-00000", "url": "/g/1/"}],
                "cell_addresses_multi": True,
                "subnet_contained_in": "198.18.0.0/24",
                "children": [],
            }
        ]

        _attach_ipa_explain_fields(tree)

        title = tree[0]["ipa_explain_title"]
        self.assertIn("direct in rule cell", title)
        self.assertIn("group member: bench-grp-00000", title)
        self.assertIn("alias/duplicate address names", title)
        self.assertIn("contained by 198.18.0.0/24", title)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_synthesize_ipam_parent_prefix_nests_hosts(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn, _stats_fn, _visible_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        host_cidr = "198.18.0.10/32"
        net24 = "198.18.0.0/24"

        def attach_meta(node, obj):
            ref = ip_ref_fn(obj)
            node["ip_ref"] = {"str": ref["str"], "url": ref["url"], "type": ref["type"]}
            node["prefix_display_cidr"] = ref["str"]
            node["node_role"] = "nsm_host" if "/32" in ref["str"] else "nsm_prefix"
            node["kind"] = "leaf"
            return node

        attach_fn.side_effect = attach_meta

        def make_host(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            obj.ip_address = MagicMock()
            obj.prefix = None
            obj.range = None
            return obj

        host = make_host(1, "bench-ip-00000010")
        ip_ref_fn.side_effect = lambda obj: {
            "str": host_cidr,
            "url": "/ipam/ip-addresses/1/",
            "type": "IP Address",
            "ct": 11,
            "pk": 1,
        }

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 2
        prefix.prefix = ipaddress.ip_network(net24)
        prefix.get_absolute_url.return_value = "/ipam/prefixes/2/"
        prefix.get_parents.return_value = []

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._lookup_containing_prefix_for_ipa_cell_node",
            return_value=prefix,
        ):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_prefix_for_cell_object",
                return_value=None,
            ):
                raw = [{"ct": "10", "pk": "1", "name": host.name}]
                nodes = _build_ipa_cell_object_tree(raw, {(10, 1): host})

        self.assertEqual(len(nodes), 1)
        parent = nodes[0]
        self.assertTrue(parent.get("ipam_synthetic"))
        self.assertTrue(parent.get("is_ipam_synthesized"))
        self.assertTrue(parent.get("is_ipam_filler"))
        self.assertNotIn("is_ipam_parent_prefix", parent)
        self.assertNotIn("in_cell", parent)
        self.assertEqual(parent.get("prefix_display_cidr"), net24)
        self.assertEqual(len(parent.get("children") or []), 1)
        self.assertEqual(parent["children"][0]["name"], host.name)
        self.assertTrue(parent["children"][0].get("is_cell_direct"))
        child = parent["children"][0]
        self.assertEqual(child.get("subnet_contained_in"), net24)
        self.assertEqual(child.get("subnet_contained_in_url"), "/ipam/prefixes/2/")

    def test_mark_ipa_cell_tree_parent_hints_uses_nearest_prefix_ancestor(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _mark_ipa_cell_tree_parent_hints

        nodes = [
            {
                "name": "198.18.0.0/16",
                "url": "/ipam/prefixes/16/",
                "prefix_display_cidr": "198.18.0.0/16",
                "is_ipam_filler": True,
                "ipam_synthetic": True,
                "children": [
                    {
                        "name": "198.18.0.0/24",
                        "url": "/ipam/prefixes/24/",
                        "prefix_display_cidr": "198.18.0.0/24",
                        "is_ipam_filler": True,
                        "ipam_synthetic": True,
                        "children": [
                            {
                                "name": "bench-ip-00000010",
                                "url": "/a/10/",
                                "prefix_display_cidr": "198.18.0.10/32",
                                "cell_groups_multi": True,
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        _mark_ipa_cell_tree_parent_hints(nodes)
        host = nodes[0]["children"][0]["children"][0]
        self.assertEqual(host.get("ipa_tree_parent_cidr"), "198.18.0.0/24")
        self.assertEqual(host.get("ipa_tree_parent_name"), "198.18.0.0/24")
        self.assertEqual(host.get("ipa_tree_parent_url"), "/ipam/prefixes/24/")

    def test_addr_node_prefix_cidr_accepts_nsm_address_host_ref(self):
        from netbox_nsm.analyzers.ip_analyzer.addr_ip_refs import _addr_node_prefix_cidr

        cidr = _addr_node_prefix_cidr(
            ip_ref={
                "str": "198.18.0.1/32",
                "url": "/ipam/ip-addresses/181/",
                "type": "Address",
            }
        )
        self.assertEqual(cidr, "198.18.0.1/32")

    def test_mark_ipa_subnet_containment_flags_group_with_same_cidr_as_parent_prefix(
        self,
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _mark_ipa_subnet_containment_warnings,
        )

        net24 = "198.18.3.0/24"
        nodes = [
            {
                "name": "bench-net-00346",
                "url": "/a/1/",
                "prefix_display_cidr": net24,
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-grp-00346",
                        "url": "/g/500/",
                        "prefix_display_cidr": net24,
                        "node_role": IPA_NODE_ROLE_GROUP,
                        "kind": "group",
                        "cell_pill_group": True,
                        "is_cell_direct": True,
                        "children": [],
                    }
                ],
            }
        ]
        _mark_ipa_subnet_containment_warnings(nodes)
        child = nodes[0]["children"][0]
        self.assertEqual(child.get("subnet_contained_in"), net24)
        self.assertEqual(child.get("subnet_contained_in_name"), "bench-net-00346")

    def test_build_ipa_cell_object_tree_marks_nested_host_with_address_ip_ref(
        self,
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _mark_ipa_subnet_containment_warnings

        net24 = "198.18.0.0/24"
        host_cidr = "198.18.0.1/32"
        nodes = [
            {
                "name": "bench-net-00000",
                "url": "/a/1/",
                "prefix_display_cidr": net24,
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-ip-0000000",
                        "url": "/a/505/",
                        "ip_ref": {
                            "str": host_cidr,
                            "url": "/ipam/ip-addresses/181/",
                            "type": "Address",
                        },
                        "node_role": "nsm_host",
                        "is_cell_direct": True,
                        "children": [],
                    }
                ],
            }
        ]
        _mark_ipa_subnet_containment_warnings(nodes)
        host = nodes[0]["children"][0]
        self.assertEqual(host.get("subnet_contained_in"), net24)

    def test_addr_tree_node_network_falls_back_to_prefix_display_cidr(self):
        from netbox_nsm.analyzers.ip_analyzer.addr_tree import _addr_tree_node_network

        node = {
            "ip_ref": {"str": "<broken>", "type": "Prefix"},
            "prefix_display_cidr": "198.18.0.0/24",
        }
        self.assertEqual(str(_addr_tree_node_network(node)), "198.18.0.0/24")

    def test_synthesize_ipa_cell_ipam_parent_prefixes_unit(self):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 2
        prefix.prefix = ipaddress.ip_network("198.18.0.0/24")
        prefix.get_absolute_url.return_value = "/ipam/prefixes/2/"
        prefix.get_parents.return_value = []

        host = {
            "name": "bench-ip-00000010",
            "url": "/a/1/",
            "kind": "leaf",
            "node_role": "nsm_host",
            "prefix_display_cidr": "198.18.0.10/32",
            "ip_ref": {"str": "198.18.0.10/32", "url": "#", "type": "IP Address"},
            "children": [],
        }

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._lookup_containing_prefix_for_ipa_cell_node",
            return_value=prefix,
        ):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._reorganize_ipa_object_tree_by_ipam_prefix_hierarchy",
                side_effect=lambda nodes, _obj: nodes,
            ):
                result = _synthesize_ipa_cell_ipam_parent_prefixes([host], {})

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].get("is_ipam_synthesized"))
        self.assertEqual(result[0].get("prefix_display_cidr"), "198.18.0.0/24")
        self.assertEqual(result[0]["children"][0]["name"], host["name"])

    def test_synthesize_ipa_cell_ipam_parent_prefixes_for_collapsed_group(self):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 2
        prefix.prefix = ipaddress.ip_network("198.18.3.0/24")
        prefix.get_absolute_url.return_value = "/ipam/prefixes/2/"
        prefix.get_parents.return_value = []

        group = {
            "name": "bench-grp-00346",
            "url": "/g/500/",
            "kind": "group",
            "node_role": IPA_NODE_ROLE_GROUP,
            "is_cell_direct": True,
            "prefix_display_cidr": "198.18.3.0/24",
            "children": [],
        }

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._lookup_containing_prefix_for_ipa_cell_node",
            return_value=prefix,
        ):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._reorganize_ipa_object_tree_by_ipam_prefix_hierarchy",
                side_effect=lambda nodes, _obj: nodes,
            ):
                result = _synthesize_ipa_cell_ipam_parent_prefixes([group], {})

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].get("is_ipam_synthesized"))
        self.assertEqual(result[0].get("prefix_display_cidr"), "198.18.3.0/24")
        self.assertEqual(result[0]["children"][0]["name"], group["name"])
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 2
        prefix.prefix = ipaddress.ip_network("198.18.0.0/24")
        prefix.get_absolute_url.return_value = "/ipam/prefixes/2/"

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_node_from_resolved_prefix",
            side_effect=lambda node, _prefix: node,
        ):
            node = _build_ipa_synthesized_parent_prefix_node(prefix)

        self.assertTrue(node.get("ipam_synthetic"))
        self.assertTrue(node.get("is_ipam_synthesized"))
        self.assertEqual(node.get("prefix_display_cidr"), "198.18.0.0/24")
        self.assertEqual(node.get("kind"), "group")


class IpaCellTreeDisplayTests(SimpleTestCase):
    def test_ipa_format_gap_label(self):
        self.assertEqual(_ipa_format_gap_label(99), "[99 used ip]")
        self.assertEqual(
            _ipa_format_gap_label(10, 145),
            "[10 used / 145 unused ip]",
        )

    def test_build_ipa_ipam_filler_prefix_node(self):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 16
        prefix.prefix = ipaddress.ip_network("10.0.0.0/16")
        prefix.get_absolute_url.return_value = "/ipam/prefixes/16/"

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_node_from_resolved_prefix",
            side_effect=lambda node, _prefix: node.update(
                {"prefix_display_cidr": "10.0.0.0/16"}
            )
            or node,
        ):
            node = _build_ipa_ipam_filler_prefix_node(prefix)

        self.assertEqual(node.get("ipa_tree_node_type"), IPA_TREE_NODE_IPAM_FILLER)
        self.assertTrue(node.get("is_ipam_filler"))
        self.assertTrue(node.get("ipam_synthetic"))
        self.assertNotIn("is_ipam_parent_prefix", node)

    def test_insert_ipam_filler_prefixes_inserts_missing_slash16(self):
        import ipaddress

        from ipam.models import Prefix

        slash8 = MagicMock(spec=Prefix)
        slash8.pk = 8
        slash8.prefix = ipaddress.ip_network("10.0.0.0/8")

        slash16 = MagicMock(spec=Prefix)
        slash16.pk = 16
        slash16.prefix = ipaddress.ip_network("10.0.0.0/16")
        slash16.get_absolute_url.return_value = "/ipam/prefixes/16/"
        slash16.get_parents.return_value = [slash8]

        slash24 = MagicMock(spec=Prefix)
        slash24.pk = 24
        slash24.prefix = ipaddress.ip_network("10.0.1.0/24")
        slash24.get_parents.return_value = [slash16, slash8]

        parent = {
            "name": "g-10.0.0.0/8",
            "kind": "group",
            "prefix_display_cidr": "10.0.0.0/8",
            "node_role": "nsm_prefix",
            "children": [
                {
                    "name": "n-10.0.1.0/24",
                    "kind": "leaf",
                    "ct": "10",
                    "pk": "24",
                    "prefix_display_cidr": "10.0.1.0/24",
                    "node_role": "nsm_prefix",
                    "children": [],
                }
            ],
        }
        obj_by_key = {(10, 24): MagicMock(pk=24, prefix=slash24)}

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_resolve_netbox_prefix_for_tree_node",
            side_effect=lambda node, _obj, **kwargs: slash24 if node.get("pk") == "24" else None,
        ):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_ipam_filler_prefix_node",
                side_effect=lambda prefix: {
                    "kind": "group",
                    "ipa_tree_node_type": IPA_TREE_NODE_IPAM_FILLER,
                    "is_ipam_filler": True,
                    "prefix_display_cidr": str(prefix.prefix),
                    "children": [],
                },
            ):
                result = _insert_ipam_filler_prefixes([parent], obj_by_key)

        filler = result[0]["children"][0]
        self.assertEqual(filler.get("ipa_tree_node_type"), IPA_TREE_NODE_IPAM_FILLER)
        self.assertEqual(filler.get("prefix_display_cidr"), "10.0.0.0/16")
        self.assertEqual(filler["children"][0]["name"], "n-10.0.1.0/24")

    def test_ipa_intermediate_ipam_prefix_chain_accepts_netaddr_prefixes(self):
        import ipaddress

        from ipam.models import Prefix
        from netaddr import IPNetwork

        slash8 = MagicMock(spec=Prefix)
        slash8.prefix = IPNetwork("10.0.0.0/8")

        slash16 = MagicMock(spec=Prefix)
        slash16.prefix = IPNetwork("10.0.0.0/16")
        slash16.get_parents.return_value = [slash8]

        slash24 = MagicMock(spec=Prefix)
        slash24.prefix = IPNetwork("10.0.1.0/24")
        slash24.get_parents.return_value = [slash16, slash8]

        parent_net = ipaddress.ip_network("10.0.0.0/8")
        chain = _ipa_intermediate_ipam_prefix_chain(parent_net, slash24)
        self.assertEqual([item.prefix for item in chain], [slash16.prefix])

    def test_insert_ipam_filler_prefixes_inserts_missing_slash16_with_netaddr(self):
        import ipaddress

        from ipam.models import Prefix
        from netaddr import IPNetwork

        slash8 = MagicMock(spec=Prefix)
        slash8.pk = 8
        slash8.prefix = IPNetwork("10.0.0.0/8")

        slash16 = MagicMock(spec=Prefix)
        slash16.pk = 16
        slash16.prefix = IPNetwork("10.0.0.0/16")
        slash16.get_absolute_url.return_value = "/ipam/prefixes/16/"
        slash16.get_parents.return_value = [slash8]

        slash24 = MagicMock(spec=Prefix)
        slash24.pk = 24
        slash24.prefix = IPNetwork("10.0.1.0/24")
        slash24.get_parents.return_value = [slash16, slash8]

        parent = {
            "name": "g-10.0.0.0/8",
            "kind": "group",
            "prefix_display_cidr": "10.0.0.0/8",
            "node_role": "nsm_prefix",
            "children": [
                {
                    "name": "n-10.0.1.0/24",
                    "kind": "leaf",
                    "ct": "10",
                    "pk": "24",
                    "prefix_display_cidr": "10.0.1.0/24",
                    "node_role": "nsm_prefix",
                    "children": [],
                }
            ],
        }
        obj_by_key = {(10, 24): MagicMock(pk=24, prefix=slash24)}

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_resolve_netbox_prefix_for_tree_node",
            side_effect=lambda node, _obj, **kwargs: slash24 if node.get("pk") == "24" else None,
        ):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._build_ipa_ipam_filler_prefix_node",
                side_effect=lambda prefix: {
                    "kind": "group",
                    "ipa_tree_node_type": IPA_TREE_NODE_IPAM_FILLER,
                    "is_ipam_filler": True,
                    "prefix_display_cidr": str(prefix.prefix),
                    "children": [],
                },
            ):
                result = _insert_ipam_filler_prefixes([parent], obj_by_key)

        filler = result[0]["children"][0]
        self.assertEqual(filler.get("prefix_display_cidr"), "10.0.0.0/16")

    def test_insert_ipa_host_gap_info_rows_between_hosts(self):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 24
        prefix.prefix = ipaddress.ip_network("10.0.1.0/24")
        prefix.get_child_ips.return_value = []

        tree = [
            {
                "name": "n-10.0.1.0/24",
                "kind": "group",
                "prefix_display_cidr": "10.0.1.0/24",
                "node_role": "nsm_prefix",
                "children": [
                    {
                        "name": "h-10.0.1.1",
                        "kind": "leaf",
                        "prefix_display_cidr": "10.0.1.1/32",
                        "node_role": "nsm_host",
                        "children": [],
                    },
                    {
                        "name": "h-10.0.1.100",
                        "kind": "leaf",
                        "prefix_display_cidr": "10.0.1.100/32",
                        "node_role": "nsm_host",
                        "children": [],
                    },
                ],
            }
        ]

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_resolve_netbox_prefix_for_tree_node",
            return_value=prefix,
        ):
            result = _insert_ipa_host_gap_info_rows(tree, {})

        child_kinds = [
            child.get("ipa_tree_node_type") or child.get("node_role")
            for child in result[0]["children"]
        ]
        self.assertEqual(child_kinds[0], "nsm_host")
        self.assertEqual(child_kinds[1], IPA_TREE_NODE_INFO_GAP)
        self.assertEqual(child_kinds[2], "nsm_host")
        gap = result[0]["children"][1]
        self.assertIn("used ip", gap.get("ipa_gap_label", ""))
        self.assertEqual(gap.get("ipa_gap_display_label"), gap.get("ipa_gap_label"))

    def test_prune_empty_ipa_info_gap_nodes_drops_labelless_rows(self):
        tree = [
            {
                "name": "n-10.0.1.0/24",
                "node_role": "nsm_prefix",
                "children": [
                    {
                        "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                        "kind": "ipa_info_gap",
                        "info_summary": True,
                        "children": [],
                    },
                    {
                        "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                        "kind": "ipa_info_gap",
                        "ipa_gap_label": "[5 used / 10 unused ip]",
                        "name": "[5 used / 10 unused ip]",
                        "children": [],
                    },
                ],
            }
        ]
        result = _prune_empty_ipa_info_gap_nodes(tree)
        self.assertEqual(len(result[0]["children"]), 1)
        self.assertIn("used ip", result[0]["children"][0].get("ipa_gap_label", ""))

    def test_ipa_info_gap_display_label_prefers_canonical_fields(self):
        node = {
            "ipa_gap_label": "[1 used ip]",
            "info_summary_label": "1 used ip",
            "name": "fallback-not-used",
        }
        self.assertEqual(_ipa_info_gap_display_label(node), "[1 used ip]")
        self.assertEqual(
            _ipa_info_gap_display_label({"info_summary_label": "5 used / 2 unused ip"}),
            "[5 used / 2 unused ip]",
        )
        self.assertFalse(_ipa_info_gap_display_label({"name": "bench-grp-001"}))
        self.assertTrue(_ipa_info_gap_row_is_visible({**node, "kind": "ipa_info_gap"}))
        self.assertFalse(
            _ipa_info_gap_row_is_visible(
                {"kind": "ipa_info_gap", "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP}
            )
        )

    def test_collapse_consecutive_ipa_info_gap_nodes(self):
        label = "[5 used / 10 unused ip]"
        tree = [
            {
                "kind": "ipa_info_gap",
                "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                "ipa_gap_label": label,
                "children": [],
            },
            {
                "kind": "ipa_info_gap",
                "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                "ipa_gap_label": label,
                "children": [],
            },
            {
                "kind": "ipa_info_gap",
                "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                "info_summary": True,
                "children": [],
            },
            {"kind": "leaf", "name": "host", "children": []},
        ]
        result = _collapse_consecutive_ipa_info_gap_nodes(tree)
        self.assertEqual(len(result), 2)
        self.assertEqual(_ipa_info_gap_display_label(result[0]), label)
        self.assertEqual(result[1]["name"], "host")

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_drilldown_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_cell_tree_with_filler_and_gap_rows(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn, _stats_fn, _visible_fn, _meta_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        slash8 = MagicMock(spec=Prefix)
        slash8.pk = 8
        slash8.prefix = ipaddress.ip_network("10.0.0.0/8")
        slash8.get_absolute_url.return_value = "/ipam/prefixes/8/"
        slash8.get_parents.return_value = []
        slash8.get_child_ips.return_value = MagicMock(
            __iter__=MagicMock(return_value=iter([])),
            count=MagicMock(return_value=0),
        )

        slash16 = MagicMock(spec=Prefix)
        slash16.pk = 16
        slash16.prefix = ipaddress.ip_network("10.0.0.0/16")
        slash16.get_absolute_url.return_value = "/ipam/prefixes/16/"
        slash16.get_parents.return_value = [slash8]
        slash16.get_child_ips.return_value = MagicMock(
            __iter__=MagicMock(return_value=iter([])),
            count=MagicMock(return_value=0),
        )

        slash24 = MagicMock(spec=Prefix)
        slash24.pk = 24
        slash24.prefix = ipaddress.ip_network("10.0.1.0/24")
        slash24.get_absolute_url.return_value = "/ipam/prefixes/24/"
        slash24.get_parents.return_value = [slash16, slash8]
        slash24.get_child_ips.return_value = MagicMock(
            __iter__=MagicMock(return_value=iter([])),
            count=MagicMock(return_value=0),
        )

        refs = {
            8: {"str": "10.0.0.0/8", "url": "/p/8/", "type": "Prefix"},
            16: {"str": "10.0.0.0/16", "url": "/p/16/", "type": "Prefix"},
            24: {"str": "10.0.1.0/24", "url": "/p/24/", "type": "Prefix"},
            1: {"str": "10.0.1.1/32", "url": "/ip/1/", "type": "IP Address"},
            100: {"str": "10.0.1.100/32", "url": "/ip/100/", "type": "IP Address"},
        }

        def attach_meta(node, obj):
            ref = refs[obj.pk]
            node["ip_ref"] = {"str": ref["str"], "url": ref["url"], "type": ref["type"]}
            node["prefix_display_cidr"] = ref["str"]
            if "/32" in ref["str"]:
                node["node_role"] = "nsm_host"
            else:
                node["node_role"] = "nsm_prefix"
            node["kind"] = "leaf"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: refs[obj.pk]

        def make_obj(pk, name, prefix=None):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            obj.prefix = prefix
            obj.ip_address = MagicMock() if "/32" in refs[pk]["str"] else None
            obj.range = None
            return obj

        obj8 = make_obj(8, "g-10.0.0.0/8", slash8)
        obj24 = make_obj(24, "n-10.0.1.0/24", slash24)
        obj1 = make_obj(1, "h-10.0.1.1")
        obj100 = make_obj(100, "h-10.0.1.100")

        def prefix_for_cell(obj):
            return {8: slash8, 24: slash24}.get(obj.pk)

        raw = [
            {"ct": "10", "pk": "8", "name": obj8.name},
            {"ct": "10", "pk": "24", "name": obj24.name},
            {"ct": "10", "pk": "1", "name": obj1.name},
            {"ct": "10", "pk": "100", "name": obj100.name},
        ]
        obj_by_key = {
            (10, 8): obj8,
            (10, 24): obj24,
            (10, 1): obj1,
            (10, 100): obj100,
        }

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_prefix_for_cell_object",
            side_effect=prefix_for_cell,
        ):
            nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        root = nodes[0]
        self.assertEqual(root.get("ipa_tree_node_type"), IPA_TREE_NODE_CELL_SELECTED)
        self.assertTrue(root.get("is_cell_direct"))
        self.assertTrue(root.get("in_cell"))

        filler = root["children"][0]
        self.assertEqual(filler.get("ipa_tree_node_type"), IPA_TREE_NODE_IPAM_FILLER)
        self.assertTrue(filler.get("ipam_synthetic"))
        self.assertNotIn("in_cell", filler)
        self.assertEqual(filler.get("prefix_display_cidr"), "10.0.0.0/16")

        net24 = filler["children"][0]
        self.assertEqual(net24.get("ipa_tree_node_type"), IPA_TREE_NODE_CELL_SELECTED)
        self.assertTrue(net24.get("in_cell"))
        self.assertEqual(net24.get("prefix_display_cidr"), "10.0.1.0/24")

        host_names = [
            child.get("name")
            for child in net24["children"]
        ]
        self.assertEqual(host_names, ["h-10.0.1.1", "h-10.0.1.100"])
        gap_rows = [
            child
            for child in net24["children"]
            if child.get("ipa_tree_node_type") == IPA_TREE_NODE_INFO_GAP
        ]
        self.assertEqual(gap_rows, [])

        root_nets = {
            child.get("prefix_display_cidr")
            for child in nodes
            if child.get("prefix_display_cidr")
        }
        self.assertNotIn("10.0.1.1/32", root_nets)
        self.assertNotIn("10.0.1.100/32", root_nets)

    def test_prune_removes_duplicate_host_under_prefix(self):
        host = {
            "name": "h-10.0.1.1",
            "prefix_display_cidr": "10.0.1.1/32",
            "node_role": "nsm_host",
            "ip_ref": {"str": "10.0.1.1/32"},
            "children": [],
        }
        tree = [
            {
                "name": "n-10.0.1.0/24",
                "prefix_display_cidr": "10.0.1.0/24",
                "node_role": "nsm_prefix",
                "children": [dict(host)],
            },
            host,
        ]
        pruned = _prune_ipa_object_tree_duplicate_nodes(tree)
        self.assertEqual(len(pruned), 1)
        self.assertEqual(pruned[0]["prefix_display_cidr"], "10.0.1.0/24")
        self.assertEqual(len(pruned[0]["children"]), 1)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_large_group_expands_only_cell_co_selected_members(
        self, content_type_cls, members_fn, _attach_fn
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import IPA_CELL_GROUP_FULL_EXPAND_MAX

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        def make_addr(pk, name):
            obj = MagicMock()
            obj.pk = pk
            obj.name = name
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            return obj

        direct = make_addr(1, "bench-ip-0000000")
        extra_members = [
            make_addr(pk, f"bench-ip-{pk:07d}")
            for pk in range(2, IPA_CELL_GROUP_FULL_EXPAND_MAX + 70)
        ]
        group = MagicMock()
        group.pk = 99
        group.name = "bench-grp-00000"
        group.get_absolute_url.return_value = "/g/99/"
        group.address_type = "address-group"
        members_fn.side_effect = lambda obj: [direct, *extra_members] if obj is group else []

        raw = [
            {"ct": "10", "pk": "1", "name": direct.name},
            {"ct": "10", "pk": "99", "name": group.name},
        ]
        obj_by_key = {(10, 1): direct, (10, 99): group}
        for member in extra_members:
            obj_by_key[(10, member.pk)] = member
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        names = {n.get("name") for n in nodes}
        self.assertIn(direct.name, names)
        self.assertNotIn(extra_members[0].name, names)
        self.assertLessEqual(len(nodes), 5)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_large_group_without_co_selected_members_is_collapsed_row(
        self, content_type_cls, members_fn, _attach_fn
    ):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import IPA_CELL_GROUP_FULL_EXPAND_MAX

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        members = []
        for pk in range(1, IPA_CELL_GROUP_FULL_EXPAND_MAX + 70):
            obj = MagicMock()
            obj.pk = pk
            obj.name = f"bench-ip-{pk:07d}"
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            members.append(obj)

        group = MagicMock()
        group.pk = 500
        group.name = "bench-grp-00346"
        group.get_absolute_url.return_value = "/g/500/"
        group.address_type = "address-group"
        members_fn.side_effect = lambda obj: members if obj is group else []

        raw = [{"ct": "10", "pk": "500", "name": group.name}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 500): group})

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], group.name)
        self.assertTrue(nodes[0].get("is_cell_direct"))
        self.assertEqual(nodes[0].get("kind"), "group")
        self.assertEqual(nodes[0].get("node_role"), IPA_NODE_ROLE_GROUP)
        self.assertTrue(
            nodes[0].get("cell_pill_group"),
            msg="collapsed address-group row must render an ADDRESS_GROUP pill",
        )

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_large_collapsed_group_nests_under_member_subnet_in_ipam_tree(
        self, content_type_cls, members_fn, _attach_fn
    ):
        import ipaddress

        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            IPA_CELL_GROUP_FULL_EXPAND_MAX,
            _enrich_ipa_collapsed_group_networks_from_members,
            _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy,
        )

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        subnet = MagicMock()
        subnet.pk = 1
        subnet.name = "bench-net-0000346"
        subnet.get_absolute_url.return_value = "/a/1/"
        subnet.address_type = None

        members = [subnet]
        for pk in range(2, IPA_CELL_GROUP_FULL_EXPAND_MAX + 70):
            host = MagicMock()
            host.pk = pk
            host.name = f"bench-ip-{pk:07d}"
            host.get_absolute_url.return_value = f"/a/{pk}/"
            host.address_type = None
            members.append(host)

        group = MagicMock()
        group.pk = 500
        group.name = "bench-grp-00346"
        group.get_absolute_url.return_value = "/g/500/"
        group.address_type = "address-group"
        members_fn.side_effect = lambda obj: members if obj is group else []

        prefix_node = {
            "name": subnet.name,
            "url": subnet.get_absolute_url(),
            "ct": "10",
            "pk": "1",
            "kind": "leaf",
            "node_role": "nsm_prefix",
            "prefix_display_cidr": "198.18.3.0/24",
            "children": [],
        }
        group_node = {
            "name": group.name,
            "url": group.get_absolute_url(),
            "ct": "10",
            "pk": "500",
            "kind": "group",
            "node_role": IPA_NODE_ROLE_GROUP,
            "cell_pill_group": True,
            "is_cell_direct": True,
            "children": [],
        }
        obj_by_key = {(10, 1): subnet, (10, 500): group}

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_member_containment_network",
            side_effect=lambda member: (
                ipaddress.ip_network("198.18.3.0/24")
                if member is subnet
                else ipaddress.ip_network(f"198.18.3.{member.pk}/32")
            ),
        ):
            nodes = [prefix_node, group_node]
            _enrich_ipa_collapsed_group_networks_from_members(nodes, obj_by_key)
            self.assertEqual(group_node.get("prefix_display_cidr"), "198.18.3.0/24")
            forest = _reorganize_ipa_object_tree_by_ipam_prefix_hierarchy(
                nodes, obj_by_key
            )

        self.assertEqual(len(forest), 1)
        child_names = {child.get("name") for child in forest[0].get("children") or []}
        self.assertIn(group.name, child_names)


class IpaCellTreeDrilldownGuardTests(SimpleTestCase):
    def test_cell_tree_has_visible_address_children_detects_host_under_prefix(self):
        node = {
            "children": [
                {
                    "name": "bench-ip-0000000",
                    "prefix_display_cidr": "198.18.0.1/32",
                    "node_role": "nsm_host",
                }
            ]
        }
        self.assertTrue(_ipa_cell_tree_has_visible_address_children(node))

    def test_cell_tree_has_visible_address_children_ignores_info_gap(self):
        node = {
            "children": [
                {
                    "ipa_tree_node_type": IPA_TREE_NODE_INFO_GAP,
                    "kind": "ipa_info_gap",
                }
            ]
        }
        self.assertFalse(_ipa_cell_tree_has_visible_address_children(node))

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    def test_mark_addr_drilldown_skipped_when_cell_children_present(self, _visible_fn):
        nodes = [
            {
                "name": "bench-net-00000",
                "ct": "10",
                "pk": "1",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "prefix_display_cidr": "198.18.0.0/24",
                "children": [
                    {
                        "name": "bench-ip-0000000",
                        "prefix_display_cidr": "198.18.0.1/32",
                        "node_role": "nsm_host",
                        "children": [],
                    }
                ],
            }
        ]
        obj = MagicMock()
        _mark_ipa_object_addr_drilldown_flags(nodes, {(10, 1): obj})
        self.assertNotIn("addr_drilldown_lazy", nodes[0])

    def test_mark_ipa_cell_pill_roles_flags_group_rows_only(self):
        nodes = [
            {
                "name": "bench-grp-00346",
                "node_role": IPA_NODE_ROLE_GROUP,
                "kind": "group",
                "children": [
                    {
                        "name": "bench-ip-0000000",
                        "node_role": "nsm_host",
                        "prefix_display_cidr": "198.18.0.1/32",
                        "children": [],
                    }
                ],
            },
            {
                "name": "filler",
                "is_ipam_filler": True,
                "ipa_tree_node_type": IPA_TREE_NODE_IPAM_FILLER,
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [],
            },
        ]
        _mark_ipa_cell_pill_roles(nodes)
        self.assertTrue(nodes[0].get("cell_pill_group"))
        self.assertNotIn("cell_pill_group", nodes[0]["children"][0])
        self.assertNotIn("cell_pill_group", nodes[1])

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._hub._attach_ipam_stats_meta")
    def test_attach_ipam_stats_uses_netbox_counts_not_visible_subtree(
        self, attach_fn, prefix_stats_fn
    ):
        prefix_stats_fn.return_value = {
            "child_prefixes": {"count": 259},
            "ip_ranges": {"count": 0},
            "ip_addresses": {"count": 0},
        }
        obj = MagicMock()
        obj.pk = 599
        nodes = [
            {
                "name": "bench-net-super-00000",
                "ct": "10",
                "pk": "599",
                "prefix_display_cidr": "198.18.0.0/16",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-ip-0000000",
                        "prefix_display_cidr": "198.18.0.1/32",
                        "node_role": "nsm_host",
                        "children": [],
                    }
                ],
            }
        ]
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_prefix_for_cell_object",
            return_value=MagicMock(),
        ):
            from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _attach_ipa_object_tree_ipam_stats

            _attach_ipa_object_tree_ipam_stats(nodes, {(10, 599): obj})
        attach_fn.assert_called_once()
        stats_arg = attach_fn.call_args[0][1]
        self.assertEqual(stats_arg["child_prefixes"]["count"], 259)
        self.assertEqual(stats_arg["ip_addresses"]["count"], 0)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_keeps_netbox_counts_with_visible_children(
        self, meta_fn
    ):
        meta_fn.return_value = {
            "name": "bench-net-super-00000",
            "url": "/ipam/prefixes/599/",
            "count_subnets": 259,
            "count_ranges": 0,
            "count_ips": 0,
        }
        obj = MagicMock()
        obj.pk = 599
        nodes = [
            {
                "name": "bench-net-super-00000",
                "ct": "10",
                "pk": "599",
                "prefix_display_cidr": "198.18.0.0/16",
                "node_role": IPA_NODE_ROLE_PREFIX,
                "children": [
                    {
                        "name": "bench-ip-0000000",
                        "prefix_display_cidr": "198.18.0.1/32",
                        "node_role": "nsm_host",
                        "children": [],
                    }
                ],
            }
        ]
        _attach_ipa_drilldown_meta(nodes, {(10, 599): obj})
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_subnets"], 259)
        self.assertEqual(nodes[0]["ipa_drilldown_meta"]["count_ips"], 0)


class IpaContainingPrefixCacheTests(SimpleTestCase):
    def test_batch_prefetch_uses_single_prefix_query(self):
        import ipaddress

        from ipam.models import Prefix

        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _IpaContainingPrefixCache,
            _ipa_most_specific_prefix_for_host,
        )

        slash24 = MagicMock(spec=Prefix)
        slash24.pk = 24
        slash24.prefix = ipaddress.ip_network("198.18.0.0/24")

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_query_prefixes_containing_hosts",
            return_value=[slash24],
        ) as query_fn:
            cache = _IpaContainingPrefixCache()
            nodes = [
                {
                    "name": "h-198.18.0.1",
                    "prefix_display_cidr": "198.18.0.1/32",
                    "node_role": "nsm_host",
                    "children": [],
                },
                {
                    "name": "h-198.18.0.2",
                    "prefix_display_cidr": "198.18.0.2/32",
                    "node_role": "nsm_host",
                    "children": [],
                },
            ]
            cache.register_tree(nodes)
            query_fn.assert_not_called()
            p1 = cache.resolve(nodes[0])
            p2 = cache.resolve(nodes[1])

        query_fn.assert_called_once()
        queried_hosts = query_fn.call_args[0][0]
        self.assertEqual(queried_hosts, {"198.18.0.1", "198.18.0.2"})
        self.assertIs(p1, slash24)
        self.assertIs(p2, slash24)

    def test_most_specific_prefix_picks_longest_match(self):
        import ipaddress

        from ipam.models import Prefix

        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _ipa_most_specific_prefix_for_host

        slash16 = MagicMock(spec=Prefix)
        slash16.prefix = ipaddress.ip_network("198.18.0.0/16")
        slash24 = MagicMock(spec=Prefix)
        slash24.prefix = ipaddress.ip_network("198.18.0.0/24")

        best = _ipa_most_specific_prefix_for_host(
            "198.18.0.10", [slash16, slash24]
        )
        self.assertIs(best, slash24)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_drilldown_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_ip_ref")
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_cell_tree_batches_prefix_lookups(
        self, content_type_cls, ip_ref_fn, _members_fn, attach_fn, _stats_fn, _visible_fn, _meta_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _IpaContainingPrefixCache,
            _synthesize_ipa_cell_ipam_parent_prefixes,
        )

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        slash24 = MagicMock(spec=Prefix)
        slash24.pk = 24
        slash24.prefix = ipaddress.ip_network("198.18.0.0/24")
        slash24.get_absolute_url.return_value = "/ipam/prefixes/24/"
        slash24.get_parents.return_value = []

        def attach_meta(node, obj):
            node["ip_ref"] = {
                "str": f"198.18.0.{obj.pk}/32",
                "url": f"/ipam/ip-addresses/{obj.pk}/",
                "type": "IP Address",
            }
            node["prefix_display_cidr"] = f"198.18.0.{obj.pk}/32"
            node["node_role"] = "nsm_host"
            node["kind"] = "leaf"
            return node

        attach_fn.side_effect = attach_meta
        ip_ref_fn.side_effect = lambda obj: attach_meta({}, obj).get("ip_ref")

        hosts = []
        for pk in (1, 2, 3):
            obj = MagicMock()
            obj.pk = pk
            obj.name = f"bench-ip-{pk:07d}"
            obj.get_absolute_url.return_value = f"/a/{pk}/"
            obj.address_type = None
            hosts.append(obj)

        nodes = [
            attach_meta(
                {
                    "name": obj.name,
                    "url": obj.get_absolute_url(),
                    "ct": "10",
                    "pk": str(obj.pk),
                    "kind": "leaf",
                    "children": [],
                },
                obj,
            )
            for obj in hosts
        ]

        cache = _IpaContainingPrefixCache()
        with patch.object(
            cache,
            "_resolve_hosts_batch",
            wraps=cache._resolve_hosts_batch,
        ) as batch_fn:
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_query_prefixes_containing_hosts",
                return_value=[slash24],
            ) as query_fn:
                cache.register_tree(nodes)
                _synthesize_ipa_cell_ipam_parent_prefixes(
                    nodes, {}, prefix_cache=cache
                )

        query_fn.assert_called_once()
        batch_fn.assert_called()
        resolved = [cache.resolve(node) for node in nodes]
        self.assertTrue(all(prefix is slash24 for prefix in resolved))


class IpaCellGroupSelfRefTests(SimpleTestCase):
    def test_scrub_removes_self_from_cell_groups_on_group_row(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _mark_ipa_cell_pill_roles,
            _scrub_ipa_cell_group_self_refs,
        )

        nodes = [
            {
                "name": "dm-grp-inner",
                "url": "/g/2/",
                "ct": "10",
                "pk": "2",
                "kind": "group",
                "node_role": IPA_NODE_ROLE_GROUP,
                "is_cell_direct": True,
                "cell_groups": [
                    {"name": "dm-grp-outer", "url": "/g/1/"},
                    {"name": "dm-grp-inner", "url": "/g/2/"},
                ],
                "cell_groups_multi": True,
                "children": [],
            }
        ]
        _mark_ipa_cell_pill_roles(nodes)
        _scrub_ipa_cell_group_self_refs(nodes)

        self.assertTrue(nodes[0].get("cell_pill_group"))
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["dm-grp-outer"],
        )
        self.assertFalse(nodes[0].get("cell_groups_multi"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    def test_nested_group_direct_selection_scrubs_self_membership(
        self, _attach_fn, members_fn, content_type_cls
    ):
        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct

        inner_member = MagicMock()
        inner_member.pk = 3
        inner_member.name = "bench-ip-0000003"
        inner_member.get_absolute_url.return_value = "/a/3/"
        inner_member.address_type = None

        inner_group = MagicMock()
        inner_group.pk = 2
        inner_group.name = "dm-grp-inner"
        inner_group.get_absolute_url.return_value = "/g/2/"
        inner_group.address_type = "address-group"

        outer_group = MagicMock()
        outer_group.pk = 1
        outer_group.name = "dm-grp-outer"
        outer_group.get_absolute_url.return_value = "/g/1/"
        outer_group.address_type = "address-group"

        members_fn.side_effect = lambda obj: {
            outer_group: [inner_group],
            inner_group: [inner_member],
        }.get(obj, [])

        raw = [
            {"ct": "10", "pk": "1", "name": "dm-grp-outer"},
            {"ct": "10", "pk": "2", "name": "dm-grp-inner"},
        ]
        obj_by_key = {
            (10, 1): outer_group,
            (10, 2): inner_group,
            (10, 3): inner_member,
        }
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 1)
        addr = nodes[0]
        self.assertEqual(addr["name"], "bench-ip-0000003")
        self.assertNotIn("cell_pill_group", addr)
        self.assertEqual(
            [g["name"] for g in addr.get("cell_groups") or []],
            ["dm-grp-outer", "dm-grp-inner"],
        )


class IpaCellDisplayHintTests(SimpleTestCase):
    def test_attach_cell_group_collapse_hints_from_count(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _attach_ipa_cell_display_hints

        groups = [{"name": f"grp-{idx}", "url": f"/g/{idx}/"} for idx in range(5)]
        nodes = [{"name": "addr", "cell_groups": groups, "cell_groups_multi": True, "children": []}]
        _attach_ipa_cell_display_hints(nodes)
        self.assertTrue(nodes[0].get("cell_groups_collapsed"))
        self.assertEqual(nodes[0].get("collapsed_group_count"), 5)

    def test_attach_address_compact_hints_for_alias_peers(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _attach_ipa_cell_display_hints

        nodes = [
            {
                "name": "bench-net-0000001",
                "url": "/a/1/",
                "cell_addresses_multi": True,
                "cell_addresses": [
                    {"name": "bench-net-0000001", "url": "/a/1/"},
                    {"name": "bench-alias-0000001", "url": "/a/2/"},
                ],
                "children": [],
            }
        ]
        _attach_ipa_cell_display_hints(nodes)
        self.assertTrue(nodes[0].get("cell_addresses_compact"))
        self.assertEqual(nodes[0]["cell_address_primary"]["name"], "bench-net-0000001")
        self.assertEqual(len(nodes[0].get("cell_address_alternates") or []), 1)

    def test_attach_parent_containment_does_not_set_compact_hint(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _attach_ipa_cell_display_hints

        nodes = [
            {
                "name": "h-10.112.134.44",
                "subnet_contained_in": "10.112.134.0/24",
                "subnet_contained_in_name": "dm-addr-10-112-134-0-24",
                "subnet_contained_in_url": "/a/13/",
                "children": [],
            }
        ]
        _attach_ipa_cell_display_hints(nodes)
        self.assertNotIn("cell_parent_hint_compact", nodes[0])
        self.assertNotIn("cell_cidr_parent_hint", nodes[0])

    def test_display_hints_preserve_collapsed_root_group_wrapper_count(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _attach_ipa_cell_display_hints,
            _wrap_collapsed_root_group_nodes,
        )

        def collapsed_group(pk):
            return {
                "name": f"bench-grp-{pk:05d}",
                "url": f"/g/{pk}/",
                "kind": "group",
                "node_role": "nsm_group",
                "cell_pill_group": True,
                "is_cell_direct": True,
                "children": [],
            }

        nodes = [collapsed_group(pk) for pk in range(1, 5)]
        wrapped = _wrap_collapsed_root_group_nodes(nodes)
        _attach_ipa_cell_display_hints(wrapped)
        self.assertEqual(wrapped[-1].get("collapsed_group_count"), 4)

    def test_wrap_collapsed_root_group_nodes(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS,
            _wrap_collapsed_root_group_nodes,
        )

        def collapsed_group(pk):
            return {
                "name": f"bench-grp-{pk:05d}",
                "url": f"/g/{pk}/",
                "kind": "group",
                "node_role": "nsm_group",
                "cell_pill_group": True,
                "is_cell_direct": True,
                "children": [],
            }

        nodes = [collapsed_group(pk) for pk in range(1, 5)]
        wrapped = _wrap_collapsed_root_group_nodes(nodes)
        self.assertEqual(len(wrapped), 1)
        self.assertEqual(
            wrapped[0].get("ipa_tree_node_type"),
            IPA_TREE_NODE_COLLAPSED_ROOT_GROUPS,
        )
        self.assertEqual(wrapped[0].get("collapsed_group_count"), 4)
        self.assertEqual(len(wrapped[0].get("children") or []), 4)

    def test_annotate_ipa_cell_tree_depth(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _annotate_ipa_cell_tree_depth

        nodes = [
            {
                "name": "root",
                "children": [
                    {"name": "child", "children": []},
                ],
            }
        ]
        _annotate_ipa_cell_tree_depth(nodes)
        self.assertEqual(nodes[0]["ipa_depth"], 0)
        self.assertEqual(nodes[0]["children"][0]["ipa_depth"], 1)

    def test_annotate_ipa_cell_tree_depth_skips_filler_depth_increment(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _annotate_ipa_cell_tree_depth

        nodes = [
            {
                "name": "root",
                "is_cell_direct": True,
                "children": [
                    {
                        "name": "198.18.0.0/20",
                        "is_ipam_filler": True,
                        "ipa_tree_node_type": "ipam_filler",
                        "children": [
                            {
                                "name": "198.18.0.0/24",
                                "is_cell_direct": True,
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        _annotate_ipa_cell_tree_depth(nodes)
        filler = nodes[0]["children"][0]
        net24 = filler["children"][0]
        self.assertEqual(filler["ipa_depth"], 1)
        self.assertEqual(net24["ipa_depth"], 1)

    def test_ipa_cell_tree_flat_row_is_visible_excludes_filler(self):
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import _ipa_cell_tree_flat_row_is_visible

        self.assertFalse(
            _ipa_cell_tree_flat_row_is_visible(
                {
                    "name": "198.18.0.0/20",
                    "is_ipam_filler": True,
                    "ipa_tree_node_type": "ipam_filler",
                }
            )
        )
        self.assertTrue(
            _ipa_cell_tree_flat_row_is_visible(
                {"name": "bench-net-00001", "is_cell_direct": True}
            )
        )

    def test_renest_contained_sibling_restores_depth_consistency(self):
        """A host stranded beside its containing prefix is re-homed under it.

        Regression: ``198.18.1.1/32`` rendered ``••`` (depth 2) while its
        siblings ``198.18.1.2/32`` … rendered ``•••`` (depth 3) because the
        ``.1`` row lingered next to the ``/24`` instead of inside it. After
        re-nesting, every host shares one depth = prefix depth + 1.
        """
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _annotate_ipa_cell_tree_depth,
            _renest_ipa_contained_cell_siblings,
        )

        def host(addr):
            return {
                "name": addr,
                "node_role": "nsm_host",
                "kind": "leaf",
                "prefix_display_cidr": addr,
                "is_cell_direct": True,
                "children": [],
            }

        prefix24 = {
            "name": "198.18.1.0/24",
            "node_role": "nsm_prefix",
            "kind": "group",
            "is_cell_direct": True,
            "prefix_display_cidr": "198.18.1.0/24",
            "children": [host("198.18.1.2/32"), host("198.18.1.3/32")],
        }
        # ``.1`` arrives stranded as a sibling of the /24 it belongs to.
        nodes = [host("198.18.1.1/32"), prefix24]

        renested = _renest_ipa_contained_cell_siblings(nodes)

        # The /24 is the only root; every host now lives under it.
        self.assertEqual(len(renested), 1)
        net24 = renested[0]
        self.assertEqual(net24["prefix_display_cidr"], "198.18.1.0/24")
        host_cidrs = sorted(
            child["prefix_display_cidr"] for child in net24["children"]
        )
        self.assertEqual(
            host_cidrs,
            ["198.18.1.1/32", "198.18.1.2/32", "198.18.1.3/32"],
        )

        _annotate_ipa_cell_tree_depth(renested)
        prefix_depth = net24["ipa_depth"]
        child_depths = {child["ipa_depth"] for child in net24["children"]}
        # All siblings share one depth, exactly one deeper than their parent.
        self.assertEqual(child_depths, {prefix_depth + 1})

    def test_renest_contained_sibling_is_idempotent(self):
        """Already-nested trees are left untouched (no spurious moves)."""
        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _renest_ipa_contained_cell_siblings,
        )

        nodes = [
            {
                "name": "198.18.1.0/24",
                "node_role": "nsm_prefix",
                "kind": "group",
                "prefix_display_cidr": "198.18.1.0/24",
                "children": [
                    {
                        "name": "198.18.1.5/32",
                        "node_role": "nsm_host",
                        "kind": "leaf",
                        "prefix_display_cidr": "198.18.1.5/32",
                        "children": [],
                    }
                ],
            }
        ]
        result = _renest_ipa_contained_cell_siblings(nodes)
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["children"]), 1)
        self.assertEqual(
            result[0]["children"][0]["prefix_display_cidr"], "198.18.1.5/32"
        )


class IpaCellAddressFieldTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils._addr_group_members")
    def test_resolve_group_anchor_member_prefers_prefix_member(self, members_fn):
        import ipaddress

        subnet = MagicMock()
        subnet.pk = 1
        subnet.name = "bench-net-00346"
        subnet.get_absolute_url.return_value = "/a/1/"

        host = MagicMock()
        host.pk = 2
        host.name = "bench-ip-0000346"
        host.get_absolute_url.return_value = "/a/2/"

        group = MagicMock()
        group.pk = 500
        group.name = "bench-grp-00346"
        members_fn.return_value = [subnet, host]

        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_member_containment_network",
            side_effect=lambda member: (
                ipaddress.ip_network("198.19.90.0/24")
                if member is subnet
                else ipaddress.ip_network("198.19.90.10/32")
            ),
        ):
            anchor = _ipa_resolve_group_anchor_member(group)

        self.assertIs(anchor, subnet)

    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_resolve_group_anchor_member")
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_expands_members", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_node_role_from_tree_node", return_value=IPA_NODE_ROLE_GROUP)
    def test_attach_cell_address_fields_sets_primary_for_collapsed_group(
        self, _role_fn, _expands_fn, anchor_fn
    ):
        anchor = MagicMock()
        anchor.pk = 1
        anchor.name = "bench-net-00346"
        anchor.get_absolute_url.return_value = "/a/1/"
        anchor_fn.return_value = anchor

        nodes = [
            {
                "name": "bench-grp-00346",
                "url": "/g/500/",
                "ct": "10",
                "pk": "500",
                "kind": "group",
                "node_role": IPA_NODE_ROLE_GROUP,
                "children": [],
            }
        ]
        group = MagicMock()
        group.pk = 500
        _attach_ipa_cell_address_fields(nodes, {(10, 500): group})

        self.assertEqual(
            nodes[0]["cell_group_anchor_address"]["name"],
            "bench-net-00346",
        )
        self.assertEqual(nodes[0]["cell_group_anchor_address"]["url"], "/a/1/")

    def test_attach_cell_address_fields_backfills_url_for_group_member(self):
        obj = MagicMock()
        obj.get_absolute_url.return_value = "/a/200/"
        nodes = [
            {
                "name": "bench-net-00000",
                "ct": "10",
                "pk": "200",
                "kind": "leaf",
                "cell_groups": [{"name": "bench-grp-00000", "url": "/g/1/"}],
                "children": [],
            }
        ]
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_node_role_from_tree_node",
            return_value=IPA_NODE_ROLE_PREFIX,
        ):
            _attach_ipa_cell_address_fields(nodes, {(10, 200): obj})

        self.assertEqual(nodes[0]["url"], "/a/200/")
