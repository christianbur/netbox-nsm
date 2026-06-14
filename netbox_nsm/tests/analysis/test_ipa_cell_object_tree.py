"""Tests for IPA cell object tree builders."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analysis.addr_analysis_utils import (
    _build_ipa_cell_object_tree,
    _count_ipa_object_tree_duplicates,
    _count_ipa_object_tree_group_duplicates,
    _flatten_ipa_object_tree_copy_lines,
    _ipa_cell_object_tree_visible,
    _ipa_object_tree_type_counts,
    _resolve_summary_type_counts,
)
from netbox_nsm.objects.address_literal import format_network_nsm_config_comments
from netbox_nsm.analysis.ipa_object_node import IPA_NODE_ROLE_PREFIX
from netbox_nsm.analysis.ipa_object_tree import (
    _attach_ipa_drilldown_meta,
    _enrich_ipa_object_tree_cidr_from_names,
    _ipa_cidr_from_object_name,
    _ipa_object_tree_sort_key,
    _ipa_subnet_containment_display_net,
    _mark_ipa_object_addr_drilldown_flags,
    _mark_ipa_subnet_containment_warnings,
    _merge_ipa_cell_nodes_by_network,
    _prune_ipa_object_tree_duplicate_nodes,
    _sort_ipa_object_tree_siblings,
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


class IpaCidrFromNameEnrichTests(SimpleTestCase):
    def test_enrich_sets_prefix_role_for_dm_addr_leaf(self):
        nodes = [{"name": "dm-addr-10-112-148-0-28", "kind": "leaf", "children": []}]
        _enrich_ipa_object_tree_cidr_from_names(nodes)
        self.assertEqual(nodes[0]["prefix_display_cidr"], "10.112.148.0/28")
        self.assertEqual(nodes[0]["node_role"], IPA_NODE_ROLE_PREFIX)
        self.assertEqual(nodes[0]["kind"], "group")


class IpaCellDrilldownMetaTests(SimpleTestCase):
    @patch("netbox_nsm.analysis.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_on_cell_direct_leaf_prefix(self, meta_fn):
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

    @patch("netbox_nsm.analysis.ipa_ipam_tree._build_ipa_drilldown_source_meta")
    def test_attach_ipa_drilldown_meta_skips_non_cell_direct(self, meta_fn):
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
        self.assertNotIn("ipa_drilldown_meta", nodes[0])
        meta_fn.assert_not_called()


class IpaCellObjectTreeTests(SimpleTestCase):
    def test_ipa_cell_object_tree_visible_always_when_nodes_exist(self):
        nodes = [{"name": "a", "children": []}, {"name": "b", "children": []}]
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 2, prefer_logical_merge=True))
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 1, prefer_logical_merge=True))
        self.assertFalse(_ipa_cell_object_tree_visible([], 1))

    def test_ipa_cell_object_tree_visible_shows_doppelt_on_single_object(self):
        nodes = [{"name": "a", "is_doppelt": True, "children": []}]
        self.assertTrue(_ipa_cell_object_tree_visible(nodes, 2))
    @patch("netbox_nsm.analysis.ipa_object_tree._build_ipa_cell_flat_address_node")
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

    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
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

    @patch("netbox_nsm.analysis.ipa_object_tree._build_ipa_cell_flat_address_node")
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
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    @patch("netbox_nsm.analysis.ipa_object_tree._build_ipa_cell_flat_address_node")
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
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    @patch("netbox_nsm.analysis.ipa_object_tree._build_ipa_cell_flat_address_node")
    def test_build_ipa_cell_object_tree_direct_plus_multi_groups_appends_none(
        self, build_node_fn, members_fn, content_type_cls
    ):
        from netbox_nsm.analysis.ipa_object_tree import _apply_node_cell_groups

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
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
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

    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
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

    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
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
        from netbox_nsm.analysis.ipa_object_tree import _mark_ipa_cell_open_by_default

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
        from netbox_nsm.analysis.ipa_object_tree import _mark_ipa_cell_open_by_default

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

    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
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

    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=False)
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

    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
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

    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    @patch("netbox_nsm.analysis.ipam_drilldown._prefix_ipam_stats")
    @patch("netbox_nsm.analysis.ipam_drilldown._lookup_ipam_prefix_from_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
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
    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
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
    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
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

    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ipam_stats")
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta")
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
        p24a.prefix = ipaddress.ip_network("10.128.130.0/24")
        p24a.get_parents.return_value = [slash8]

        p24b = MagicMock(spec=Prefix)
        p24b.pk = 2
        p24b.prefix = ipaddress.ip_network("10.128.143.0/24")
        p24b.get_parents.return_value = [slash8]

        def attach_meta(node, obj):
            refs = {
                1: {"str": "10.128.130.0/24", "url": "/p/1/", "type": "Prefix"},
                2: {"str": "10.128.143.0/24", "url": "/p/2/", "type": "Prefix"},
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
    @patch("netbox_nsm.analysis.ipa_object_tree._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
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

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value={"str": "10.1.0.0/16", "url": "#", "type": "Prefix"})
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_object_tree_node_attaches_ip_ref(
        self, content_type_cls, _ip_ref, _attach_fn
    ):
        from netbox_nsm.analysis.addr_analysis_utils import _build_ipa_object_tree_node

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

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._resolve_ipam_stats_from_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
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
        self.assertEqual(counts["count_ips"], 10)

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
