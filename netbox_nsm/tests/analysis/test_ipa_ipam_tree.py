"""Tests for IPA object-tree IPAM logical drilldown."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip.addr_constants import FIELD_TYPE_LABELS
from netbox_nsm.analyzers.ip.ipa_ipam_tree import (
    _apply_ipam_drilldown_presentation,
    _build_ipa_drilldown_source_meta,
    _build_ipa_object_drilldown_nodes,
    _build_ipa_object_ipam_tree,
    _dedupe_ipa_ipam_drilldown_nodes,
    _enrich_ipa_drilldown_nodes,
    _ipa_drilldown_parent_network,
    _resolve_ipam_object_for_drilldown,
    _strip_redundant_parent_network_drilldown_nodes,
)
from netbox_nsm.analyzers.ip.ipa_object_node import (
    IPA_NODE_ROLE_HOST,
    IPA_NODE_ROLE_IPAM_PREFIX,
    IPA_NODE_ROLE_PREFIX,
    IPA_NODE_ROLE_RANGE,
)


class IpaIpamTreeResolveTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_fk_object_for_addr_node")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_obj_from_ip_ref")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref")
    def test_resolve_prefers_ip_ref_target(
        self, ip_ref_fn, ipam_from_ref_fn, fk_fn
    ):
        prefix = MagicMock()
        ip_ref_fn.return_value = {
            "str": "10.1.0.0/16",
            "type": FIELD_TYPE_LABELS["prefix"],
            "pk": 1,
        }
        ipam_from_ref_fn.return_value = prefix
        obj = MagicMock()

        self.assertIs(_resolve_ipam_object_for_drilldown(obj), prefix)
        fk_fn.assert_not_called()

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_fk_object_for_addr_node")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref", return_value=None)
    def test_resolve_falls_back_to_fk(self, _ip_ref_fn, fk_fn):
        ip_range = MagicMock()
        fk_fn.return_value = ip_range
        self.assertIs(_resolve_ipam_object_for_drilldown(MagicMock()), ip_range)


class IpaIpamTreeBuildTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._build_ipam_prefix_layer_node")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_prefix_builds_ipam_prefix_layer(self, resolve_fn, layer_fn):
        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.pk = 5
        resolve_fn.return_value = prefix
        layer_fn.return_value = {
            "name": "10.112.129.0/24",
            "layer": "ipam_prefix",
            "kind": "group",
            "children": [],
        }
        obj = MagicMock()
        obj.pk = 99

        nodes = _build_ipa_object_ipam_tree(obj)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["layer"], "ipam_prefix")
        layer_fn.assert_called_once_with(prefix, {99})

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._build_ipam_range_resolve_nodes")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_range_builds_resolved_range_node(self, resolve_fn, range_fn):
        from ipam.models import IPRange

        ip_range = MagicMock(spec=IPRange)
        ip_range.pk = 7
        resolve_fn.return_value = ip_range
        range_fn.return_value = {
            "name": "10.0.0.1-10.0.0.10",
            "kind": "group",
            "children": [{"name": "10.0.0.1", "kind": "leaf", "children": []}],
        }
        obj = MagicMock()
        obj.pk = 42

        nodes = _build_ipa_object_ipam_tree(obj)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["kind"], "group")
        range_fn.assert_called_once_with(ip_range, {42})


class IpaIpamTreePresentationTests(SimpleTestCase):
    def test_apply_presentation_marks_ipam_prefix_role(self):
        node = {
            "layer": "ipam_prefix",
            "kind": "group",
            "children": [
                {
                    "kind": "group",
                    "ip_ref": {
                        "str": "198.18.130.0/24",
                        "type": FIELD_TYPE_LABELS["prefix"],
                    },
                    "children": [],
                },
                {
                    "kind": "group",
                    "ip_ref": {
                        "str": "10.0.0.1-10.0.0.10",
                        "type": FIELD_TYPE_LABELS["range"],
                    },
                    "children": [],
                },
                {
                    "kind": "leaf",
                    "ip_ref": {
                        "str": "10.112.129.1/32",
                        "type": FIELD_TYPE_LABELS["ip_address"],
                    },
                    "children": [],
                },
            ],
        }
        _apply_ipam_drilldown_presentation(node)

        self.assertEqual(node["node_role"], IPA_NODE_ROLE_IPAM_PREFIX)
        roles = [child["node_role"] for child in node["children"]]
        self.assertEqual(
            roles,
            [IPA_NODE_ROLE_PREFIX, IPA_NODE_ROLE_RANGE, IPA_NODE_ROLE_HOST],
        )
        self.assertNotIn("addr_drilldown_lazy", node)


class IpaObjectDrilldownNodesTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._flatten_addr_tree_paths", return_value=[])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_object_ipam_tree")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._object_supports_addr_analysis", return_value=True)
    def test_drilldown_uses_ipam_tree_for_prefix_container(
        self,
        _supports_fn,
        ipam_tree_fn,
        _filter_fn,
        _copy_fn,
        _leaf_fn,
        _paths_fn,
    ):
        ipam_tree_fn.return_value = [
            {
                "name": "10.112.129.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "children": [
                    {
                        "name": "10.112.129.1/32",
                        "kind": "leaf",
                        "children": [],
                    }
                ],
            }
        ]
        obj = MagicMock()

        nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["node_role"], IPA_NODE_ROLE_IPAM_PREFIX)
        self.assertEqual(copy_lines, [])
        ipam_tree_fn.assert_called_once_with(obj)

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._flatten_addr_tree_paths", return_value=[])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_drilldown_source_meta", return_value={"name": "dm-addr"})
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_object_ipam_tree")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._object_supports_addr_analysis", return_value=True)
    def test_drilldown_omits_shell_only_prefix_meta(
        self,
        _supports_fn,
        ipam_tree_fn,
        _meta_fn,
        _filter_fn,
        _copy_fn,
        _leaf_fn,
        _paths_fn,
    ):
        ipam_tree_fn.return_value = [
            {
                "name": "10.112.139.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "children": [],
            }
        ]
        obj = MagicMock()

        nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)

        self.assertEqual(nodes, [])
        self.assertEqual(copy_lines, [])

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._flatten_addr_tree_paths", return_value=["line"])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_object_ipam_tree", return_value=[])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._build_addr_tree_node")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._object_supports_addr_analysis", return_value=True)
    def test_drilldown_falls_back_to_host_leaf(
        self,
        _supports_fn,
        build_node_fn,
        _ipam_tree_fn,
        _copy_fn,
        _leaf_fn,
        _paths_fn,
    ):
        build_node_fn.return_value = {
            "name": "host-a",
            "kind": "leaf",
            "ip_ref": {
                "str": "10.0.0.1/32",
                "type": FIELD_TYPE_LABELS["ip_address"],
            },
            "children": [],
        }
        obj = MagicMock()
        obj.pk = 1

        nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["node_role"], IPA_NODE_ROLE_HOST)
        self.assertNotIn("ipa_drilldown_meta", nodes[0])
        self.assertEqual(copy_lines, ["line"])


class IpaDrilldownMetaTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_stats_ip_count", return_value=12)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_stats_range_count", return_value=3)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ipam_stats_subnet_count", return_value=5)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._ordered_ipam_stats", side_effect=lambda s: list(s.values()))
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_build_ipa_drilldown_source_meta_includes_tenant_and_counts(
        self, resolve_fn, prefix_stats_fn, _ordered_fn, subnet_fn, range_fn, ip_fn
    ):
        from ipam.models import Prefix

        tenant = MagicMock()
        tenant.__str__ = lambda self: "Dunder Mifflin"
        tenant.get_absolute_url.return_value = "/tenancy/tenants/1/"

        prefix = MagicMock(spec=Prefix)
        prefix.tenant = tenant

        obj = MagicMock()
        obj.name = "dm-addr-10-112-129-0-24"
        obj.get_absolute_url.return_value = "/a/1/"

        resolve_fn.return_value = prefix
        prefix_stats_fn.return_value = {
            "child_prefixes": {"count": 5},
            "ip_ranges": {"count": 3},
            "ip_addresses": {"count": 12},
        }

        meta = _build_ipa_drilldown_source_meta(obj)

        self.assertEqual(meta["name"], "dm-addr-10-112-129-0-24")
        self.assertEqual(meta["tenant_name"], "Dunder Mifflin")
        self.assertEqual(meta["count_subnets"], 5)
        self.assertEqual(meta["count_ranges"], 3)
        self.assertEqual(meta["count_ips"], 12)
        subnet_fn.assert_called_once()
        range_fn.assert_called_once()
        ip_fn.assert_called_once()


class IpaIpamDrilldownDedupeTests(SimpleTestCase):
    def test_dedupe_ipam_drilldown_drops_parent_network_and_repeated_keys(self):
        nodes = [
            {
                "name": "10.112.134.0/24",
                "ct": "99",
                "pk": "1",
                "kind": "group",
                "ip_ref": {"str": "10.112.134.0/24"},
                "children": [
                    {
                        "name": "10.112.134.0/24",
                        "ct": "99",
                        "pk": "2",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.134.0/24"},
                        "children": [],
                    },
                    {
                        "name": "10.112.160.0/28",
                        "ct": "99",
                        "pk": "3",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.160.0/28"},
                        "children": [],
                    },
                ],
            }
        ]
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.134.0/24")
        deduped = _dedupe_ipa_ipam_drilldown_nodes(nodes, exclude_network=parent_net)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(deduped[0]["children"]), 1)
        self.assertEqual(deduped[0]["children"][0]["name"], "10.112.160.0/28")

    def test_collapse_duplicate_network_drilldown_siblings_keeps_richest(self):
        from netbox_nsm.analyzers.ip.ipa_ipam_tree import (
            _collapse_duplicate_network_drilldown_siblings,
        )

        nodes = [
            {
                "name": "10.112.160.0/24",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/24"},
                "children": [],
            },
            {
                "name": "10.112.160.0/24",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/24"},
                "children": [
                    {
                        "name": "10.112.160.0/28",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.160.0/28"},
                        "children": [],
                    }
                ],
            },
        ]
        collapsed = _collapse_duplicate_network_drilldown_siblings(nodes)
        self.assertEqual(len(collapsed), 1)
        self.assertEqual(len(collapsed[0]["children"]), 1)
        self.assertEqual(collapsed[0]["children"][0]["name"], "10.112.160.0/28")

    def test_strip_redundant_parent_network_drilldown_hoists_children(self):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.134.0/24")
        nodes = [
            {
                "name": "10.112.134.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.134.0/24"},
                "children": [
                    {
                        "name": "10.112.134.44/32",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.134.44/32"},
                        "children": [],
                    }
                ],
            }
        ]
        stripped = _strip_redundant_parent_network_drilldown_nodes(
            nodes, parent_network=parent_net
        )
        self.assertEqual(len(stripped), 1)
        self.assertEqual(stripped[0]["name"], "10.112.134.44/32")

    def test_strip_redundant_parent_network_drilldown_removes_duplicate_groups(self):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.134.0/24")
        nodes = [
            {
                "name": "10.112.134.0/24",
                "kind": "group",
                "ip_ref": {"str": "10.112.134.0/24"},
                "prefix_display_cidr": "10.112.134.0/24",
                "children": [],
            },
            {
                "name": "10.112.134.0/24",
                "kind": "group",
                "ip_ref": {"str": "10.112.134.0/24"},
                "prefix_display_cidr": "10.112.134.0/24",
                "children": [],
            },
        ]
        stripped = _strip_redundant_parent_network_drilldown_nodes(
            nodes, parent_network=parent_net
        )
        self.assertEqual(stripped, [])

    def test_strip_redundant_parent_network_empty_when_no_children(self):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.134.0/24")
        nodes = [
            {
                "name": "10.112.134.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.134.0/24"},
                "children": [],
            }
        ]
        stripped = _strip_redundant_parent_network_drilldown_nodes(
            nodes, parent_network=parent_net
        )
        self.assertEqual(stripped, [])

    def test_strip_redundant_parent_network_recurses_into_children(self):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.160.0/24")
        nodes = [
            {
                "name": "10.112.160.0/22",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/22"},
                "children": [
                    {
                        "name": "10.112.160.0/24",
                        "layer": "ipam_prefix",
                        "kind": "group",
                        "ip_ref": {"str": "10.112.160.0/24"},
                        "children": [
                            {
                                "name": "10.112.160.0/28",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.112.160.0/28"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        stripped = _strip_redundant_parent_network_drilldown_nodes(
            nodes, parent_network=parent_net
        )
        self.assertEqual(len(stripped), 1)
        self.assertEqual(stripped[0]["name"], "10.112.160.0/22")
        self.assertEqual(len(stripped[0]["children"]), 1)
        self.assertEqual(stripped[0]["children"][0]["name"], "10.112.160.0/28")

    def test_strip_self_referential_redundant_networks_hoists_children(self):
        import ipaddress

        from netbox_nsm.analyzers.ip.ipa_tree_dedupe import (
            strip_self_referential_redundant_networks,
        )

        redundant = [ipaddress.ip_network("10.112.160.0/28")]
        nodes = [
            {
                "name": "10.112.160.0/28",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/28", "type": "Prefix"},
                "children": [
                    {
                        "name": "10.112.160.1/32",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.160.1/32"},
                        "children": [],
                    }
                ],
            }
        ]
        stripped = strip_self_referential_redundant_networks(
            nodes, redundant_networks=redundant
        )
        self.assertEqual(len(stripped), 1)
        self.assertEqual(stripped[0]["name"], "10.112.160.1/32")

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._sort_ipa_object_tree_siblings", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._apply_ipam_drilldown_presentation")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    def test_enrich_drilldown_strips_10_112_160_28_self_reference_shell(
        self, _filter_fn, _present_fn, _copy_fn, _leaf_fn, _sort_fn
    ):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.160.0/28")
        nodes = [
            {
                "name": "10.112.160.0/28",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/28"},
                "prefix_display_cidr": "10.112.160.0/28",
                "children": [
                    {
                        "name": "10.112.160.1/32",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.160.1/32"},
                        "children": [],
                    }
                ],
            }
        ]
        enriched = _enrich_ipa_drilldown_nodes(nodes, parent_network=parent_net)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["name"], "10.112.160.1/32")
        self.assertNotEqual(enriched[0].get("layer"), "ipam_prefix")

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._sort_ipa_object_tree_siblings", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._apply_ipam_drilldown_presentation")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    def test_enrich_drilldown_strips_redundant_28_child_under_container_prefix(
        self, _filter_fn, _present_fn, _copy_fn, _leaf_fn, _sort_fn
    ):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.160.0/28")
        nodes = [
            {
                "name": "10.112.160.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/24"},
                "children": [
                    {
                        "name": "10.112.160.0/28",
                        "kind": "group",
                        "ip_ref": {"str": "10.112.160.0/28"},
                        "prefix_display_cidr": "10.112.160.0/28",
                        "children": [
                            {
                                "name": "10.112.160.1/32",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.112.160.1/32"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        enriched = _enrich_ipa_drilldown_nodes(nodes, parent_network=parent_net)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["name"], "10.112.160.0/24")
        self.assertEqual(len(enriched[0]["children"]), 1)
        self.assertEqual(enriched[0]["children"][0]["name"], "10.112.160.1/32")

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._sort_ipa_object_tree_siblings", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._apply_ipam_drilldown_presentation")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    def test_enrich_drilldown_infers_10_112_160_28_parent_network(
        self, _filter_fn, _present_fn, _copy_fn, _leaf_fn, _sort_fn
    ):
        nodes = [
            {
                "name": "10.112.160.0/28",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/28"},
                "prefix_display_cidr": "10.112.160.0/28",
                "children": [],
            }
        ]
        enriched = _enrich_ipa_drilldown_nodes(nodes, parent_network=None)
        self.assertEqual(enriched, [])

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_ipa_drilldown_parent_network_prefers_object_cidr_over_container_prefix(
        self, resolve_fn, _ip_ref_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.prefix = ipaddress.ip_network("10.112.160.0/24")
        resolve_fn.return_value = prefix
        obj = MagicMock()
        obj.name = "dm-addr-10-112-160-0-28"

        net = _ipa_drilldown_parent_network(obj)

        self.assertEqual(net, ipaddress.ip_network("10.112.160.0/28"))

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._sort_ipa_object_tree_siblings", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._apply_ipam_drilldown_presentation")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    def test_enrich_drilldown_strips_10_112_160_ipam_prefix_shell(
        self, _filter_fn, _present_fn, _copy_fn, _leaf_fn, _sort_fn
    ):
        import ipaddress

        parent_net = ipaddress.ip_network("10.112.160.0/24")
        nodes = [
            {
                "name": "10.112.160.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/24"},
                "ipam_stats": [{"label": "Prefixes", "count": 1, "url": "#"}],
                "children": [
                    {
                        "name": "10.112.160.0/28",
                        "kind": "leaf",
                        "ip_ref": {"str": "10.112.160.0/28"},
                        "children": [],
                    }
                ],
            }
        ]
        enriched = _enrich_ipa_drilldown_nodes(nodes, parent_network=parent_net)
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["name"], "10.112.160.0/28")
        self.assertNotEqual(enriched[0].get("layer"), "ipam_prefix")

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_ipa_drilldown_parent_network_prefers_resolved_prefix(
        self, resolve_fn, _ip_ref_fn
    ):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.prefix = ipaddress.ip_network("10.112.160.0/24")
        resolve_fn.return_value = prefix
        obj = MagicMock(name="dm-addr-10-112-160-0-24")

        net = _ipa_drilldown_parent_network(obj)

        self.assertEqual(net, ipaddress.ip_network("10.112.160.0/24"))

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._flatten_addr_tree_paths", return_value=[])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_object_ipam_tree")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._object_supports_addr_analysis", return_value=True)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_build_drilldown_finalize_strips_hoisted_28_self_reference(
        self,
        resolve_fn,
        _ip_ref_fn,
        _supports_fn,
        ipam_tree_fn,
        _filter_fn,
        _copy_fn,
        _leaf_fn,
        _paths_fn,
    ):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.prefix = ipaddress.ip_network("10.112.160.0/24")
        resolve_fn.return_value = prefix
        ipam_tree_fn.return_value = [
            {
                "name": "10.112.160.0/24",
                "layer": "ipam_prefix",
                "kind": "group",
                "ip_ref": {"str": "10.112.160.0/24"},
                "children": [
                    {
                        "name": "10.112.160.0/28",
                        "kind": "group",
                        "ip_ref": {"str": "10.112.160.0/28"},
                        "prefix_display_cidr": "10.112.160.0/28",
                        "children": [
                            {
                                "name": "10.112.160.1/32",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.112.160.1/32"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        obj = MagicMock()
        obj.name = "dm-addr-10-112-160-0-28"

        nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "10.112.160.1/32")
        self.assertEqual(copy_lines, [])

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._sort_ipa_object_tree_siblings", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._apply_ipam_drilldown_presentation")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    def test_finalize_strips_self_referential_nsm_prefix_shell(
        self, _filter_fn, _present_fn, _copy_fn, _leaf_fn, _sort_fn
    ):
        import ipaddress

        from netbox_nsm.analyzers.ip.ipa_ipam_tree import _finalize_ipa_drilldown_nodes

        obj = MagicMock()
        obj.name = "dm-addr-10-112-160-0-28"
        nodes = [
            {
                "name": "10.112.160.0/28",
                "kind": "group",
                "node_role": "nsm_prefix",
                "ip_ref": {"str": "10.112.160.0/28", "type": "Prefix"},
                "prefix_display_cidr": "10.112.160.0/28",
                "ipam_stats_short": "0/0/0/1",
                "children": [],
            }
        ]

        finalized = _finalize_ipa_drilldown_nodes(nodes, obj)

        self.assertEqual(finalized, [])

    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._flatten_addr_tree_paths", return_value=[])
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_leaf_counts")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._enrich_addr_tree_copy_lines")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._filter_ipam_drilldown_category_nodes", side_effect=lambda n: n)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._build_ipa_object_ipam_tree")
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._object_supports_addr_analysis", return_value=True)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._hub._addr_ip_ref", return_value=None)
    @patch("netbox_nsm.analyzers.ip.ipa_ipam_tree._resolve_ipam_object_for_drilldown")
    def test_build_drilldown_omits_self_referential_prefix_shell(
        self,
        resolve_fn,
        _ip_ref_fn,
        _supports_fn,
        ipam_tree_fn,
        _filter_fn,
        _copy_fn,
        _leaf_fn,
        _paths_fn,
    ):
        import ipaddress

        from ipam.models import Prefix

        prefix = MagicMock(spec=Prefix)
        prefix.prefix = ipaddress.ip_network("10.112.160.0/28")
        resolve_fn.return_value = prefix
        ipam_tree_fn.return_value = [
            {
                "name": "10.112.160.0/28",
                "kind": "group",
                "node_role": "nsm_prefix",
                "ip_ref": {"str": "10.112.160.0/28", "type": "Prefix"},
                "prefix_display_cidr": "10.112.160.0/28",
                "ipam_stats_short": "0/0/0/1",
                "children": [],
            }
        ]
        obj = MagicMock()
        obj.name = "dm-addr-10-112-160-0-28"

        nodes, copy_lines = _build_ipa_object_drilldown_nodes(obj)

        self.assertEqual(nodes, [])
        self.assertEqual(copy_lines, [])
