"""Tests for IP Analyzer applet helpers."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.models.type_config import MatchingClassChoices
from netbox_nsm.rulebooks.cell_html import (
    ipa_loupe_button_html,
    render_rules_cell_ag as _render_rules_cell_ag,
    render_rules_merged_object_cell_html,
)
from netbox_nsm.rulebooks.rules_tab_base import (
    _build_rules_cell_html,
    _inject_rules_cell_context_attrs,
)
from netbox_nsm.analysis.addr_analysis_utils import (
    _addr_leaf_compare_key,
    _addr_tree_node_display_count,
    _build_addr_diff_analysis,
    _build_addr_diff_analysis_from_sides,
    _build_addr_tree_node,
    _build_ipa_cell_object_tree,
    _build_ipam_category_nodes,
    _build_multi_object_addr_analysis,
    _collect_addr_tree_leaf_map,
    _collect_ipam_prefix_children,
    _collect_ipam_prefix_children_impl,
    _count_addr_tree_duplicates,
    _count_ipa_object_tree_duplicates,
    _display_count_for_addr_nodes,
    _enrich_addr_tree_leaf_counts,
    _filter_non_contained_addr_nodes,
    _flatten_ipa_object_tree_copy_lines,
    _ipa_object_tree_type_counts,
    _mark_contained_addr_duplicate_flags,
    _flatten_ipam_grouped,
    _ipam_stats_ip_count,
    _ipam_stats_range_count,
    _ipam_stats_subnet_count,
    _ipam_stats_total,
    _object_is_addr_analyzable,
    _object_supports_addr_analysis,
    _ordered_ipam_stats,
    _ipam_stats_short,
    _prefix_ipam_stats,
    _prefix_is_large,
    _resolve_summary_type_counts,
    _type_counts_for_addr_nodes,
    _type_counts_for_diff_addr_keys,
)

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class ObjectIsAddrAnalyzableTests(SimpleTestCase):
    def test_nsm_object_requires_address_matching_class(self):
        addr = MagicMock()
        addr._meta.app_label = "netbox_custom_objects"
        addr._meta.model_name = "table1model"
        mc = {42: MatchingClassChoices.ZONE}
        self.assertFalse(_object_is_addr_analyzable(addr, 42, mc))

    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis", return_value=True
    )
    def test_true_for_address_class(self, _supports):
        prefix = MagicMock()
        mc = {7: MatchingClassChoices.ADDRESS}
        self.assertTrue(_object_is_addr_analyzable(prefix, 7, mc))

    def test_ipam_prefix_analyzable_without_typeconfig(self):
        prefix = MagicMock()
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        self.assertTrue(_object_supports_addr_analysis(prefix))
        self.assertTrue(_object_is_addr_analyzable(prefix, 14, {}))

    @patch("netbox_nsm.analysis.addr_analysis_utils.TypeConfig")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_builds_matching_class_map_when_none(self, _supports, typeconfig_cls):
        typeconfig_cls.objects.only.return_value = [
            MagicMock(content_type_id=42, matching_class=MatchingClassChoices.ADDRESS),
        ]
        addr = MagicMock()
        self.assertTrue(_object_is_addr_analyzable(addr, 42))
        typeconfig_cls.objects.only.assert_called_once_with(
            "content_type_id", "matching_class"
        )


class IpamPrefixTreeTests(SimpleTestCase):
    @patch("netbox_nsm.analysis.addr_analysis_utils._collect_ipam_drilldown_children")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    def test_nsm_address_with_prefix_expands_ipam_drilldown(
        self, ip_ref_fn, _group_container, drilldown_fn
    ):
        addr = MagicMock()
        addr.pk = 99
        addr.name = "bench-ip-demo"
        addr.get_absolute_url.return_value = "/custom-objects/99/"

        prefix = MagicMock()
        prefix.pk = 5
        prefix.__str__ = lambda self: "10.128.93.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        ip = MagicMock()
        ip.pk = 7
        ip.__str__ = lambda self: "10.128.93.1/32"
        ip._meta.app_label = "ipam"
        ip._meta.model_name = "ipaddress"
        ip.get_absolute_url.return_value = "/ipam/ip-addresses/7/"

        ip_ref_fn.side_effect = lambda obj: (
            {
                "str": "10.128.93.0/24",
                "url": "/ipam/prefixes/5/",
                "type": "Prefix",
                "ct": 14,
                "pk": 5,
            }
            if getattr(obj, "name", None) == "bench-ip-demo"
            else None
        )
        drilldown_fn.return_value = [ip]

        with patch(
            "netbox_nsm.analysis.addr_analysis_utils._ipam_fk_object_for_addr_node",
            return_value=prefix,
        ):
            with patch(
                "netbox_nsm.analysis.addr_analysis_utils._attach_addr_navigation_refs",
                side_effect=lambda node, **kw: node,
            ):
                with patch(
                    "netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display",
                    side_effect=lambda node, **kw: node,
                ):
                    node = _build_addr_tree_node(addr)

        self.assertEqual(node["kind"], "group")
        self.assertEqual(node["name"], "bench-ip-demo")
        self.assertEqual(node["ip_ref"]["ct"], 14)
        self.assertEqual(len(node["children"]), 1)

    def test_ipam_fk_field_order_matches_ip_ref_display(self):
        from netbox_nsm.analysis.addr_analysis_utils import (
            _ADDR_IPAM_FK_FIELDS,
            _ipam_fk_object_for_addr_node,
        )

        self.assertEqual(_ADDR_IPAM_FK_FIELDS[0], "prefix")
        addr = MagicMock()
        addr.prefix = MagicMock(name="prefix-obj")
        addr.ip_address = MagicMock(name="ip-obj")
        addr.range = None
        self.assertIs(_ipam_fk_object_for_addr_node(addr), addr.prefix)

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_prefix_ipam_meta", side_effect=lambda n, *a, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipam_category_nodes")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._collect_ipam_prefix_children_impl")
    def test_prefix_expands_to_linked_address_child(
        self, collect_impl, ip_ref_fn, _group_container, category_nodes, _ipam_meta
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.prefix = "10.245.10.0/24"
        prefix.__str__ = lambda self: "10.245.10.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        addr = MagicMock()
        addr.pk = 10
        addr.name = "demo-addr-0010"
        addr._meta.app_label = "netbox_custom_objects"
        addr._meta.model_name = "table1model"
        addr.get_absolute_url.return_value = "/custom-objects/10/"
        collect_impl.return_value = ({"nsm_addresses": [addr]}, {}, {})
        category_nodes.return_value = [
            {
                "kind": "category",
                "name": "Custom Objects > Addresses",
                "url": "/ipam/prefixes/5/",
                "count": 1,
                "children": [
                    {
                        "name": "demo-addr-0010",
                        "kind": "leaf",
                        "children": [],
                    }
                ],
            }
        ]

        def _ip_ref_side_effect(obj):
            if getattr(obj, "name", None) == "demo-addr-0010":
                return {
                    "str": "10.245.10.0/24",
                    "url": "/ipam/prefixes/5/",
                    "type": "Prefix",
                }
            return None

        ip_ref_fn.side_effect = _ip_ref_side_effect

        node = _build_addr_tree_node(prefix)

        self.assertIsNotNone(node)
        self.assertEqual(node["kind"], "group")
        self.assertEqual(len(node["children"]), 1)
        self.assertEqual(node["children"][0]["kind"], "category")
        self.assertEqual(node["children"][0]["children"][0]["name"], "demo-addr-0010")

        analysis = _build_multi_object_addr_analysis([prefix])
        self.assertEqual(analysis[0]["types"][0]["leaf_count"], 1)

    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    @patch("netbox_nsm.objects.address_ipam_fk.get_nsm_address_model")
    def test_collect_ipam_prefix_children_queries_all_kinds(
        self, addr_model_fn, stats_fn
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix.prefix = "10.245.10.0/24"

        child_prefix = MagicMock()
        ip = MagicMock()
        rng = MagicMock()
        addr = MagicMock()

        prefix.get_child_prefixes.return_value.order_by.return_value.__getitem__.return_value = [
            child_prefix
        ]
        prefix.get_child_ips.return_value.order_by.return_value.__getitem__.return_value = [
            ip
        ]
        prefix.get_child_ranges.return_value.order_by.return_value.__getitem__.return_value = [
            rng
        ]

        stats_fn.return_value = {
            "child_prefixes": {"count": 1, "label": "Child Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 1, "label": "IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 1, "label": "IP Ranges", "url": "/r/"},
        }

        addr_model = MagicMock()
        addr_filter = addr_model.objects.filter.return_value
        addr_filter.count.return_value = 1
        addr_filter.order_by.return_value.__getitem__.return_value = [addr]
        addr_model_fn.return_value = addr_model

        grouped, stats, truncated = _collect_ipam_prefix_children_impl(prefix)

        self.assertEqual(
            _flatten_ipam_grouped(grouped), [child_prefix, ip, rng, addr]
        )
        self.assertEqual(stats["child_prefixes"]["count"], 1)
        self.assertFalse(any(truncated.values()))

    def test_ordered_ipam_stats_keeps_netbox_tab_order(self):
        stats = {
            "ip_ranges": {"label": "IPAM > IP Ranges", "count": 3},
            "child_prefixes": {"label": "IPAM > Prefixes", "count": 1},
            "ip_addresses": {"label": "IPAM > IP Addresses", "count": 2},
        }
        ordered = _ordered_ipam_stats(stats)
        self.assertEqual(
            [item["label"] for item in ordered],
            ["IPAM > Prefixes", "IPAM > IP Addresses", "IPAM > IP Ranges"],
        )

    def test_ipam_stats_short_format(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 0},
                "ip_addresses": {"count": 100},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 101},
            }
        )
        self.assertEqual(_ipam_stats_short(ordered), "0/100/0/101")

    def test_ipam_stats_total_sums_pill_segments(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        self.assertEqual(_ipam_stats_total(ordered), 202069)

    def test_ipam_stats_ip_count_reads_ip_addresses_segment(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        self.assertEqual(_ipam_stats_ip_count(ordered), 200000)

    def test_display_count_uses_ipam_stats_on_group(self):
        node = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 2068},
                    "ip_addresses": {"count": 200000},
                    "ip_ranges": {"count": 0},
                    "nsm_addresses": {"count": 1},
                }
            ),
            "children": [{"kind": "category", "count": 2068, "children": []}],
        }
        _enrich_addr_tree_leaf_counts(node)
        self.assertEqual(node["leaf_count"], 202069)
        self.assertEqual(_addr_tree_node_display_count(node), 202069)
        self.assertEqual(_display_count_for_addr_nodes([node]), 200000)

    def test_type_counts_from_ipam_stats_on_group(self):
        node = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([node])
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 50000)

    def test_type_counts_from_loaded_tree_categories(self):
        node = {
            "kind": "group",
            "name": "n-10.245.10.0/24",
            "ip_ref": {"str": "10.245.10.0/24", "type": "Prefix"},
            "children": [
                {
                    "kind": "category",
                    "name": "IPAM > Prefixes",
                    "count": 2,
                    "children": [],
                },
                {
                    "kind": "category",
                    "name": "IPAM > IP Addresses",
                    "count": 5,
                    "children": [],
                },
                {
                    "kind": "category",
                    "name": "IPAM > IP Ranges",
                    "count": 1,
                    "children": [],
                },
            ],
        }
        counts = _type_counts_for_addr_nodes([node])
        self.assertEqual(counts["count_subnets"], 2)
        self.assertEqual(counts["count_ranges"], 1)
        self.assertEqual(counts["count_ips"], 5)

    def test_type_counts_excludes_contained_prefix_roots(self):
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "10.128.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([bench, slash8])
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 50000)

    def test_ipam_stats_subnet_and_range_count_helpers(self):
        ordered = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 3},
                "ip_addresses": {"count": 10},
                "ip_ranges": {"count": 2},
            }
        )
        self.assertEqual(_ipam_stats_subnet_count(ordered), 3)
        self.assertEqual(_ipam_stats_range_count(ordered), 2)
        self.assertEqual(_ipam_stats_ip_count(ordered), 10)

    @patch("netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis", return_value=True)
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes",
        return_value=([], ["all,line"]),
    )
    def test_build_multi_object_addr_analysis_includes_type_counts(
        self, build_nodes_fn, supports_fn
    ):
        node = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 1},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        build_nodes_fn.return_value = ([node], ["all,line"])
        analysis = _build_multi_object_addr_analysis([MagicMock()])
        type_block = analysis[0]["types"][0]
        self.assertEqual(type_block["count_subnets"], 1)
        self.assertEqual(type_block["count_ranges"], 0)
        self.assertEqual(type_block["count_ips"], 50000)
        self.assertEqual(type_block["leaf_count"], 50000)

    def test_resolve_summary_type_counts_falls_back_to_object_tree(self):
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "kind": "group",
                "children": [
                    {
                        "name": "n-10.1.0.0/16",
                        "kind": "leaf",
                        "children": [],
                        "ip_ref": {"str": "10.1.0.0/16", "type": "Prefix"},
                    }
                ],
            },
            {
                "name": "host-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.0.0.1/32", "type": "IP Address"},
            },
        ]
        counts = _resolve_summary_type_counts([], object_tree)
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 0)
        self.assertEqual(counts["count_ips"], 1)

    def test_ipa_object_tree_type_counts(self):
        object_tree = [
            {
                "name": "range-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.0.0.1-10.0.0.10", "type": "Range"},
            },
            {
                "name": "prefix-a",
                "kind": "leaf",
                "children": [],
                "ip_ref": {"str": "10.1.0.0/16", "type": "Prefix"},
            },
        ]
        counts = _ipa_object_tree_type_counts(object_tree)
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 1)
        self.assertEqual(counts["count_ips"], 0)

    def test_mark_contained_addr_duplicate_flags(self):
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "10.128.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "url": "/ipam/prefixes/99/",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "children": [],
        }
        nodes = [bench, slash8]
        _mark_contained_addr_duplicate_flags(nodes)
        self.assertTrue(bench.get("count_duplicate"))
        self.assertEqual(bench.get("count_duplicate_of"), "n-10.0.0.0/8")
        self.assertEqual(bench.get("count_duplicate_of_url"), "/ipam/prefixes/99/")
        self.assertNotIn("count_duplicate", slash8)

    def test_count_addr_tree_duplicates(self):
        bench = {
            "kind": "group",
            "name": "bench-ip",
            "count_duplicate": True,
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "children": [],
        }
        self.assertEqual(_count_addr_tree_duplicates([bench, slash8]), 1)

    def test_count_ipa_object_tree_duplicates(self):
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "children": [
                    {
                        "name": "bench-a",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                    {
                        "name": "bench-b",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                ],
            },
            {
                "name": "bench-a",
                "is_doppelt": True,
                "children": [],
            },
        ]
        self.assertEqual(_count_ipa_object_tree_duplicates(object_tree), 3)

    def test_resolve_summary_type_counts_merges_object_tree_duplicates(self):
        addr_analysis = [
            {
                "types": [
                    {
                        "count_subnets": 1,
                        "count_ranges": 0,
                        "count_ips": 50000,
                        "nodes": [],
                    }
                ]
            }
        ]
        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "children": [
                    {
                        "name": "bench-a",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    }
                ],
            }
        ]
        counts = _resolve_summary_type_counts(addr_analysis, object_tree)
        self.assertEqual(counts["count_ips"], 50000)
        self.assertEqual(counts["count_duplicates"], 1)

    @patch("netbox_nsm.objects.address_ipam_fk.get_nsm_address_model", return_value=None)
    @patch("django.urls.reverse", return_value="/ipam/")
    def test_prefix_ipam_stats_uses_get_child_ips_count(self, _reverse_fn, _addr_model_fn):
        prefix = MagicMock()
        prefix.pk = 1
        prefix.get_child_prefixes.return_value.count.return_value = 500
        prefix.get_child_ips.return_value.count.return_value = 50000
        prefix.get_child_ranges.return_value.count.return_value = 0
        stats = _prefix_ipam_stats(prefix)
        self.assertEqual(stats["ip_addresses"]["count"], 50000)
        prefix.get_child_ips.return_value.count.assert_called_once_with()

    def test_type_counts_group_slash8_skips_duplicate_nested_slash8_child(self):
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        nested = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        group = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ipam_stats": slash8_stats,
            "children": [nested],
        }
        counts = _type_counts_for_addr_nodes([group])
        self.assertEqual(counts["count_ips"], 50000)
        self.assertEqual(counts["count_subnets"], 500)

    def test_type_counts_group_inferred_slash8_uses_nested_prefix_ip_stats(self):
        """g-* group without ipam_stats: nested n-* /8 member supplies IP badge total."""
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        nested = {
            "kind": "group",
            "name": "n-10.0.0.0-8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/501/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        group = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "children": [nested],
        }
        counts = _type_counts_for_addr_nodes([group])
        self.assertEqual(counts["count_ips"], 50000)
        self.assertEqual(counts["count_subnets"], 500)

    def test_type_counts_equal_slash8_roots_keep_single_ip_total(self):
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 500},
                "ip_addresses": {"count": 50000},
                "ip_ranges": {"count": 0},
            }
        )
        g_root = {
            "kind": "group",
            "name": "g-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        n_root = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        nodes = [g_root, n_root]
        _mark_contained_addr_duplicate_flags(nodes)
        self.assertTrue(n_root.get("count_duplicate"))
        counts = _type_counts_for_addr_nodes(nodes)
        self.assertEqual(counts["count_ips"], 50000)

    def test_type_counts_slash8_parent_excludes_contained_slash24_ips(self):
        """IPs badge uses /8 ipam_stats, not /8 host capacity; /24 roots are excluded."""
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "10.128.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats(
                {
                    "child_prefixes": {"count": 500},
                    "ip_addresses": {"count": 50000},
                    "ip_ranges": {"count": 0},
                }
            ),
            "children": [],
        }
        counts = _type_counts_for_addr_nodes([bench, slash8])
        self.assertEqual(counts["count_subnets"], 500)
        self.assertEqual(counts["count_ips"], 50000)
        self.assertNotEqual(counts["count_ips"], 16777216)

    def test_display_count_excludes_prefixes_contained_in_another_root(self):
        bench_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 0},
                "ip_addresses": {"count": 100},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 101},
            }
        )
        slash8_stats = _ordered_ipam_stats(
            {
                "child_prefixes": {"count": 2068},
                "ip_addresses": {"count": 200000},
                "ip_ranges": {"count": 0},
                "nsm_addresses": {"count": 1},
            }
        )
        bench = {
            "kind": "group",
            "name": "bench-ip-0009313",
            "ip_ref": {"str": "10.128.93.0/24", "url": "/ipam/prefixes/1/", "type": "Prefix"},
            "ipam_stats": bench_stats,
            "children": [],
        }
        slash8 = {
            "kind": "group",
            "name": "n-10.0.0.0/8",
            "ip_ref": {"str": "10.0.0.0/8", "url": "/ipam/prefixes/99/", "type": "Prefix"},
            "ipam_stats": slash8_stats,
            "children": [],
        }
        nodes = [bench, slash8]
        self.assertEqual(_filter_non_contained_addr_nodes(nodes), [slash8])
        self.assertEqual(_display_count_for_addr_nodes(nodes), 200000)

    def test_display_count_keeps_sibling_prefixes(self):
        a = {
            "kind": "group",
            "name": "bench-a",
            "ip_ref": {"str": "10.128.93.0/24", "url": "/p/1/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        b = {
            "kind": "group",
            "name": "bench-b",
            "ip_ref": {"str": "10.129.34.0/24", "url": "/p/2/", "type": "Prefix"},
            "ipam_stats": _ordered_ipam_stats({"ip_addresses": {"count": 100}}),
            "children": [],
        }
        self.assertEqual(len(_filter_non_contained_addr_nodes([a, b])), 2)
        self.assertEqual(_display_count_for_addr_nodes([a, b]), 200)

    def test_prefix_is_large_by_child_count(self):
        stats = {"child_prefixes": {"count": 51}, "ip_addresses": {"count": 0}}
        self.assertTrue(_prefix_is_large(stats))

    def test_prefix_is_large_by_ip_count(self):
        stats = {"child_prefixes": {"count": 1}, "ip_addresses": {"count": 1001}}
        self.assertTrue(_prefix_is_large(stats))

    def test_prefix_not_large_below_thresholds(self):
        stats = {"child_prefixes": {"count": 50}, "ip_addresses": {"count": 1000}}
        self.assertFalse(_prefix_is_large(stats))

    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    def test_large_prefix_collect_skips_child_queries(self, stats_fn):
        prefix = MagicMock()
        prefix.pk = 99
        stats_fn.return_value = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }

        grouped, stats, truncated = _collect_ipam_prefix_children_impl(prefix)

        prefix.get_child_prefixes.assert_not_called()
        self.assertEqual(grouped["child_prefixes"], [])
        self.assertTrue(truncated["child_prefixes"])
        self.assertTrue(truncated["ip_addresses"])

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_node")
    def test_large_prefix_category_nodes_lazy_only(self, build_node_fn):
        prefix = MagicMock()
        prefix.pk = 99
        stats = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }
        grouped = {
            "child_prefixes": [],
            "ip_addresses": [],
            "ip_ranges": [],
            "nsm_addresses": [],
        }

        nodes = _build_ipam_category_nodes(prefix, grouped, stats, set())

        build_node_fn.assert_not_called()
        self.assertEqual(len(nodes), 3)
        self.assertTrue(nodes[0]["lazy_load"])
        self.assertEqual(nodes[0]["loaded_count"], 0)
        self.assertEqual(nodes[0]["count"], 2068)
        self.assertFalse(nodes[2]["lazy_load"])
        self.assertEqual(nodes[2]["count"], 0)

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_prefix_ipam_meta", side_effect=lambda n, *a, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_node")
    @patch("netbox_nsm.analysis.addr_analysis_utils._prefix_ipam_stats")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value=None)
    def test_large_ipam_prefix_tree_is_summary_only(
        self,
        _ip_ref,
        _group_container,
        stats_fn,
        build_node_fn,
        _pfx_display,
        _ipam_meta,
    ):
        prefix = MagicMock()
        prefix.pk = 99
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.__str__ = lambda self: "10.0.0.0/8"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/99/"
        stats_fn.return_value = {
            "child_prefixes": {"count": 2068, "label": "IPAM > Prefixes", "url": "/p/"},
            "ip_addresses": {"count": 200000, "label": "IPAM > IP Addresses", "url": "/i/"},
            "ip_ranges": {"count": 0, "label": "IPAM > IP Ranges", "url": "/r/"},
        }

        node = _build_addr_tree_node(prefix)

        build_node_fn.assert_not_called()
        prefix.get_child_prefixes.assert_not_called()
        self.assertEqual(node["kind"], "group")
        self.assertEqual(len(node["children"]), 3)
        lazy_cats = [c for c in node["children"] if c["count"] > 0]
        self.assertEqual(len(lazy_cats), 2)
        self.assertTrue(all(child["lazy_load"] for child in lazy_cats))


class RulesCellLoupeTests(SimpleTestCase):
    def test_cell_loupe_once_for_analyzable_objects(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn('data-addr-analyzable="1"', html)
        loupe_tag = re.search(r"<button[^>]*nsm-ipa-cell-loupe[^>]*>", html)
        self.assertIsNotNone(loupe_tag)
        self.assertNotIn("data-ct", loupe_tag.group(0))

    def test_cell_loupe_collects_all_objects_in_cell(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                },
                {
                    "url": "/a/2/",
                    "name": "net-b",
                    "color": "",
                    "ct": 1,
                    "pk": 3,
                    "addrAnalyzable": True,
                },
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 2)

    def test_cell_loupe_probe_and_visible_item_per_analyzable_object(self):
        """Stack/inline cells expose both probe markers and visible pills."""
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 1)
        self.assertEqual(
            html.count(
                'class="nsm-ag-cell-item" data-ct="1" data-pk="2" data-name="net-a" '
                'data-addr-analyzable="1"'
            ),
            1,
        )

    def test_cell_loupe_skipped_for_non_analyzable_object(self):
        html = _render_rules_cell_ag(
            [{"url": "/a/1/", "name": "net-a", "color": "", "ct": 1, "pk": 2}]
        )
        self.assertNotIn("nsm-ipa-loupe", html)

    def test_inject_rules_cell_context_attrs_on_cell_list(self):
        base = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        html = _inject_rules_cell_context_attrs(
            base,
            rule_index=44,
            rule_name="Allow Web",
            col_id="destination_addresses",
            col_position=5,
        )
        self.assertIn('data-rule-index="44"', html)
        self.assertIn('data-rule-name="Allow Web"', html)
        self.assertIn('data-col-id="destination_addresses"', html)
        self.assertIn('data-col-position="5"', html)

    def test_build_rules_object_cell_injects_context_attrs(self):
        class FakeRequest:
            GET = {}
            COOKIES = {}
            path = "/plugins/netbox_nsm/rulebooks/cot/demo/rules/"

            def get_full_path(self):
                return self.path

        col = {
            "kind": "object",
            "key": "destination_addresses",
            "col_id": "destination_addresses",
            "col_position": 5,
            "area_slug": "destination_addresses",
        }
        row = {
            "index": 44,
            "name": "Allow Web",
            "system": {"index": 44, "name": "Allow Web"},
            "cells_items": {
                "destination_addresses": [
                    {
                        "url": "/a/1/",
                        "name": "net-a",
                        "color": "",
                        "ct": 1,
                        "pk": 2,
                        "addrAnalyzable": True,
                    }
                ]
            },
        }
        html = _build_rules_cell_html(
            col,
            row,
            request=FakeRequest(),
            can_change=False,
            can_delete=False,
            object_fields_by_slug={},
        )
        self.assertIn('data-rule-index="44"', html)
        self.assertIn('data-rule-name="Allow Web"', html)
        self.assertIn('data-col-position="5"', html)

    def test_ipa_loupe_button_html_includes_identity(self):
        html = ipa_loupe_button_html(
            ct=5, pk=9, name="demo", title="Objekt analysieren"
        )
        self.assertIn('data-ct="5"', html)
        self.assertIn('data-pk="9"', html)
        self.assertIn("Objekt analysieren", html)

    def test_merged_cell_loupe_once_for_analyzable_objects(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Address",
                    "items": [
                        {
                            "url": "/a/1/",
                            "name": "bench-ip",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                            "addrAnalyzable": True,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertIn("nsm-ag-cell-merged", html)
        self.assertIn("nsm-ag-cell-type-items", html)
        self.assertIn("nsm-ag-cell-link", html)
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn("nsm-ag-cell-merged--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--item-loupe", html)
        self.assertIn('data-addr-analyzable="1"', html)

    def test_merged_cell_loupe_once_for_polymorphic_type_groups(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Address",
                    "items": [
                        {
                            "url": "/a/1/",
                            "name": "bench-ip-1",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                            "addrAnalyzable": True,
                        }
                    ],
                },
                {
                    "type_label": "Address Group",
                    "items": [
                        {
                            "url": "/g/1/",
                            "name": "g-10.0.0.0/8",
                            "color": "",
                            "ct": 1,
                            "pk": 5,
                            "addrAnalyzable": True,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ag-cell-merged--has-loupe", html)
        self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
        self.assertEqual(html.count("nsm-ag-cell-type-group"), 2)
        self.assertEqual(html.count("nsm-ag-cell-item--probe"), 2)

    def test_merged_cell_loupe_once_for_multiple_addresses(self):
        items = [
            {
                "url": "/a/1/",
                "name": "ip-1",
                "color": "",
                "ct": 1,
                "pk": 2,
                "addrAnalyzable": True,
            },
            {
                "url": "/a/2/",
                "name": "ip-2",
                "color": "",
                "ct": 1,
                "pk": 3,
                "addrAnalyzable": True,
            },
        ]
        for is_polymorphic in (True, False):
            with self.subTest(is_polymorphic=is_polymorphic):
                html = render_rules_merged_object_cell_html(
                    [{"type_label": "Address", "items": items}],
                    is_polymorphic=is_polymorphic,
                )
                self.assertEqual(html.count("nsm-ipa-loupe"), 1)
                self.assertIn("nsm-ipa-cell-loupe", html)
                if is_polymorphic:
                    self.assertIn("nsm-ag-cell-merged--has-loupe", html)
                    self.assertNotIn("nsm-ag-cell-list--has-loupe", html)
                else:
                    self.assertIn("nsm-ag-cell-list--has-loupe", html)
                self.assertNotIn("nsm-ag-cell-list--item-loupe", html)
                self.assertNotRegex(
                    html,
                    r'ip-1</a><button[^>]*nsm-ipa-loupe',
                )
                self.assertNotRegex(
                    html,
                    r'ip-2</a><button[^>]*nsm-ipa-loupe',
                )

    def test_merged_cell_skips_loupe_for_non_analyzable_objects(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Zone",
                    "items": [
                        {
                            "url": "/z/1/",
                            "name": "trust",
                            "color": "",
                            "ct": 1,
                            "pk": 2,
                        }
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertNotIn("nsm-ipa-loupe", html)

class AddrDiffAnalysisTests(SimpleTestCase):
    """Unit tests for IP analyzer diff partitioning."""

    def test_addr_leaf_compare_key_prefers_ip_ref(self):
        node = {
            "kind": "leaf",
            "name": "demo-host",
            "ip_ref": {"str": "10.0.0.1/32", "url": "#"},
        }
        self.assertEqual(_addr_leaf_compare_key(node), "10.0.0.1/32")

    def test_collect_addr_tree_leaf_map_dedupes_by_ip(self):
        nodes = [
            {
                "kind": "leaf",
                "name": "host-a",
                "url": "/a/",
                "ip_ref": {"str": "10.0.0.1", "url": "/ip/1/"},
                "children": [],
            },
            {
                "kind": "leaf",
                "name": "host-b",
                "url": "/b/",
                "ip_ref": {"str": "10.0.0.2", "url": "/ip/2/"},
                "children": [],
            },
        ]
        found = _collect_addr_tree_leaf_map(nodes)
        self.assertEqual(set(found.keys()), {"10.0.0.1", "10.0.0.2"})
        self.assertEqual(found["10.0.0.1"]["source_objects"][0]["name"], "host-a")

    def test_collect_addr_tree_leaf_map_tracks_multiple_source_names(self):
        nodes = [
            {
                "kind": "leaf",
                "name": "bench-ip-001",
                "url": "/a/",
                "ip_ref": {"str": "10.1.1.1/32", "url": "/ip/1/"},
                "children": [],
            },
            {
                "kind": "leaf",
                "name": "alias-host",
                "url": "/b/",
                "ip_ref": {"str": "10.1.1.1/32", "url": "/ip/1/"},
                "children": [],
            },
        ]
        found = _collect_addr_tree_leaf_map(nodes)
        self.assertEqual(len(found), 1)
        names = {o["name"] for o in found["10.1.1.1/32"]["source_objects"]}
        self.assertEqual(names, {"bench-ip-001", "alias-host"})

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_partitions_leaves(
        self, _supports, build_nodes_fn
    ):
        leaf_a = {
            "kind": "leaf",
            "name": "a1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.1", "url": "#"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "b1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.2", "url": "#"},
            "children": [],
        }
        leaf_common = {
            "kind": "leaf",
            "name": "c1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.3", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_a, leaf_common], []),
            ([leaf_b, leaf_common], []),
        ]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Left",
            label_b="Right",
        )

        self.assertEqual(len(result), 1)
        groups = result[0]["types"][0]["nodes"]
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[0]["diff_group"], "only-a")
        self.assertEqual(len(groups[0]["children"]), 1)
        self.assertEqual(groups[0]["children"][0]["diff_status"], "only_a")
        self.assertEqual(groups[1]["diff_group"], "only-b")
        self.assertEqual(groups[1]["children"][0]["diff_status"], "only_b")
        self.assertEqual(groups[2]["diff_group"], "both")
        self.assertEqual(groups[2]["children"][0]["diff_status"], "both")
        self.assertTrue(groups[2]["children"][0].get("diff_suppress_status"))
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(summary["only_a"], 1)
        self.assertEqual(summary["only_b"], 1)
        self.assertEqual(summary["both"], 1)
        self.assertEqual(summary["fund"], 0)
        self.assertEqual(summary["label_a"], "Left")
        self.assertEqual(summary["label_b"], "Right")
        self.assertEqual(groups[0]["name"], "Only in Left")
        self.assertEqual(groups[1]["name"], "Only in Right")
        self.assertEqual(groups[2]["name"], "In both")
        intersection = result[0]["types"][0]["intersection_tree"]
        self.assertEqual(len(intersection), 1)
        pair = intersection[0]
        self.assertTrue(pair.get("diff_intersection_pair"))
        self.assertEqual(pair.get("kind"), "leaf")
        self.assertEqual(pair.get("diff_status"), "both")
        self.assertTrue(pair.get("diff_same_name"))
        self.assertEqual(result[0]["types"][0]["intersection_leaf_count"], 1)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_three_tabs_partitions_leaves(
        self, _supports, build_nodes_fn
    ):
        leaf_tab1 = {
            "kind": "leaf",
            "name": "only-tab1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.1", "url": "#"},
            "children": [],
        }
        leaf_tab2 = {
            "kind": "leaf",
            "name": "only-tab2",
            "url": "#",
            "ip_ref": {"str": "10.0.0.2", "url": "#"},
            "children": [],
        }
        leaf_tab3 = {
            "kind": "leaf",
            "name": "only-tab3",
            "url": "#",
            "ip_ref": {"str": "10.0.0.4", "url": "#"},
            "children": [],
        }
        leaf_common = {
            "kind": "leaf",
            "name": "shared",
            "url": "#",
            "ip_ref": {"str": "10.0.0.3", "url": "#"},
            "children": [],
        }
        leaf_partial = {
            "kind": "leaf",
            "name": "partial",
            "url": "#",
            "ip_ref": {"str": "10.0.0.5", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_tab1, leaf_common, leaf_partial], []),
            ([leaf_tab2, leaf_common], []),
            ([leaf_tab3, leaf_common, leaf_partial], []),
        ]

        result = _build_addr_diff_analysis_from_sides(
            [
                {"objs": [MagicMock()], "label": "Tab 1"},
                {"objs": [MagicMock()], "label": "Tab 2"},
                {"objs": [MagicMock()], "label": "Tab 3"},
            ]
        )

        self.assertEqual(len(result), 1)
        groups = result[0]["types"][0]["nodes"]
        group_by_slug = {group["diff_group"]: group for group in groups}
        self.assertEqual(group_by_slug["only-side-0"]["name"], "Only in Tab 1")
        self.assertEqual(len(group_by_slug["only-side-0"]["children"]), 1)
        self.assertEqual(
            group_by_slug["only-side-0"]["children"][0]["diff_status"], "only_side_0"
        )
        self.assertEqual(group_by_slug["only-side-1"]["name"], "Only in Tab 2")
        self.assertEqual(len(group_by_slug["only-side-1"]["children"]), 1)
        self.assertEqual(group_by_slug["only-side-2"]["name"], "Only in Tab 3")
        self.assertEqual(len(group_by_slug["only-side-2"]["children"]), 1)
        self.assertEqual(group_by_slug["in-all"]["name"], "In all")
        self.assertEqual(len(group_by_slug["in-all"]["children"]), 1)
        self.assertEqual(group_by_slug["in-all"]["children"][0]["diff_status"], "both")
        self.assertEqual(group_by_slug["in-some"]["name"], "In some (3 tabs)")
        self.assertEqual(len(group_by_slug["in-some"]["children"]), 1)
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(summary["side_count"], 3)
        self.assertEqual(summary["in_all"], 1)
        self.assertEqual(summary["in_some"], 1)
        self.assertEqual(summary["only_by_side"][0]["count"], 1)
        self.assertEqual(summary["only_by_side"][1]["count"], 1)
        self.assertEqual(summary["only_by_side"][2]["count"], 1)

    def test_type_counts_for_diff_addr_keys(self):
        prefix_entry = {
            "ip_ref": {"str": "10.0.0.0/24", "type": "Prefix"},
        }
        range_entry = {
            "ip_ref": {"str": "10.0.1.0-10", "type": "Range"},
        }
        ip_entry = {
            "ip_ref": {"str": "10.0.0.1/32", "type": "IP Address"},
        }
        map_a = {"p": prefix_entry, "r": range_entry, "i": ip_entry}
        map_b = {"p": prefix_entry, "i": ip_entry, "j": ip_entry}
        counts = _type_counts_for_diff_addr_keys(map_a, map_b, ["r"], ["j"], ["p", "i"])
        self.assertEqual(counts["count_subnets"], 1)
        self.assertEqual(counts["count_ranges"], 1)
        self.assertEqual(counts["count_ips"], 2)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_includes_type_counts(
        self, _supports, build_nodes_fn
    ):
        leaf_a = {
            "kind": "leaf",
            "name": "only-a",
            "url": "#a",
            "ip_ref": {"str": "10.0.0.1/32", "type": "IP Address"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "only-b",
            "url": "#b",
            "ip_ref": {"str": "10.0.0.2/32", "type": "IP Address"},
            "children": [],
        }
        leaf_common = {
            "kind": "leaf",
            "name": "shared",
            "url": "#c",
            "ip_ref": {"str": "10.0.0.3/32", "type": "IP Address"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_a, leaf_common], []),
            ([leaf_b, leaf_common], []),
        ]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Left",
            label_b="Right",
        )

        type_block = result[0]["types"][0]
        self.assertEqual(type_block["count_subnets"], 0)
        self.assertEqual(type_block["count_ranges"], 0)
        self.assertEqual(type_block["count_ips"], 3)

    def test_diff_all_summary_renders_in_both_orange_badge(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_panel.html",
            {
                "addr_analysis": [
                    {
                        "field_slug": "diff",
                        "field_name": "",
                        "types": [
                            {
                                "type_name": "",
                                "count_subnets": 1,
                                "count_ranges": 0,
                                "count_ips": 200,
                                "nodes": [
                                    {
                                        "kind": "group",
                                        "name": "In both",
                                        "url": "#",
                                        "diff_group": "both",
                                        "children": [],
                                    }
                                ],
                                "diff_summary": {
                                    "label_a": "Left",
                                    "label_b": "Right",
                                    "only_a": 0,
                                    "only_b": 0,
                                    "both": 200,
                                    "fund": 3,
                                },
                            }
                        ],
                    }
                ],
            },
        )
        all_block = html.split("All", 1)[1]
        self.assertIn("Subnets: 1", all_block)
        self.assertIn("IPs: 200", all_block)
        self.assertIn("In both: 200", all_block)
        self.assertIn("Fund: 3", all_block)
        self.assertIn("nsm-addr-diff-in-both", all_block)
        self.assertIn("bg-warning-subtle text-warning", all_block)

    def test_addr_analysis_panel_renders_ipam_hierarchy_before_diff_groups(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_panel.html",
            {
                "addr_analysis": [
                    {
                        "field_slug": "diff",
                        "field_name": "Diff",
                        "types": [
                            {
                                "type_name": "Diff",
                                "nodes": [
                                    {
                                        "kind": "group",
                                        "name": "Only in Left",
                                        "url": "#",
                                        "diff_group": "only-a",
                                        "children": [],
                                    },
                                    {
                                        "kind": "group",
                                        "name": "In both",
                                        "url": "#",
                                        "diff_group": "both",
                                        "children": [],
                                    },
                                ],
                                "intersection_tree": [
                                    {
                                        "kind": "group",
                                        "name": "10.128.182.0/24",
                                        "url": "#",
                                        "children": [],
                                    }
                                ],
                                "intersection_leaf_count": 200,
                                "diff_summary": {
                                    "label_a": "Left",
                                    "label_b": "Right",
                                    "only_a": 0,
                                    "only_b": 0,
                                    "both": 200,
                                    "fund": 0,
                                },
                            }
                        ],
                    }
                ],
            },
        )
        hierarchy_pos = html.index("IPAM hierarchy (in both)")
        only_pos = html.index("Only in Left")
        all_pos = html.index("All")
        self.assertLess(hierarchy_pos, only_pos)
        self.assertLess(hierarchy_pos, all_pos)
        separator_pos = html.index("nsm-addr-diff-intersection-separator")
        self.assertLess(hierarchy_pos, separator_pos)
        self.assertLess(separator_pos, all_pos)

    def test_addr_analysis_panel_intersection_tree_uses_flat_rows(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_panel.html",
            {
                "addr_analysis": [
                    {
                        "field_slug": "diff",
                        "field_name": "Diff",
                        "types": [
                            {
                                "type_name": "Diff",
                                "nodes": [
                                    {
                                        "kind": "group",
                                        "name": "In both",
                                        "url": "#",
                                        "diff_group": "both",
                                        "children": [],
                                    },
                                ],
                                "intersection_tree": [
                                    {
                                        "kind": "group",
                                        "name": "10.128.182.0/24",
                                        "url": "#",
                                        "diff_ipam_hierarchy_prefix": True,
                                        "children": [
                                            {
                                                "kind": "leaf",
                                                "name": "bench-ip-0018231",
                                                "url": "#",
                                                "diff_intersection_pair": True,
                                                "diff_status": "both",
                                                "diff_same_name": True,
                                                "diff_name_a": "bench-ip-0018231",
                                                "diff_url_a": "#",
                                                "leaf_count": 100,
                                                "ip_ref": {
                                                    "str": "10.128.182.0/24",
                                                    "url": "#",
                                                },
                                                "prefix_display_cidr": "10.128.182.0/24",
                                                "prefix_display_netmask": "255.255.255.0",
                                                "children": [],
                                            },
                                        ],
                                    },
                                ],
                                "intersection_leaf_count": 100,
                                "diff_summary": {
                                    "label_a": "Left",
                                    "label_b": "Right",
                                },
                            }
                        ],
                    }
                ],
            },
        )
        self.assertIn("nsm-addr-intersection-flat-row", html)
        self.assertIn("bench-ip-0018231", html)
        self.assertIn("10.128.182.0/24", html)
        children_pos = html.index("nsm-addr-diff-intersection-children")
        children_end = html.index("</details>", children_pos)
        children_html = html[children_pos:children_end]
        self.assertNotIn("<details", children_html)
        self.assertIn("nsm-addr-diff-intersection-children", html)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_uses_descriptive_side_labels(
        self, _supports, build_nodes_fn
    ):
        leaf_a = {
            "kind": "leaf",
            "name": "a1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.1", "url": "#"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "b1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.2", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [([leaf_a], []), ([leaf_b], [])]

        label_a = "Allow Web (2) / destination_addresses"
        label_b = "Deny SSH (3) / source_addresses"
        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a=label_a,
            label_b=label_b,
        )

        groups = result[0]["types"][0]["nodes"]
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(groups[0]["name"], f"Only in {label_a}")
        self.assertEqual(groups[1]["name"], f"Only in {label_b}")
        self.assertEqual(summary["label_a"], label_a)
        self.assertEqual(summary["label_b"], label_b)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_intersection_tree_only_shared_keys(
        self, _supports, build_nodes_fn
    ):
        leaf_a = {
            "kind": "leaf",
            "name": "a1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.1", "url": "#"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "b1",
            "url": "#",
            "ip_ref": {"str": "10.0.0.2", "url": "#"},
            "children": [],
        }
        leaf_common = {
            "kind": "leaf",
            "name": "shared",
            "url": "#",
            "ip_ref": {"str": "10.0.0.3", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_a, leaf_common], []),
            ([leaf_b, leaf_common], []),
        ]

        result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])
        intersection = result[0]["types"][0]["intersection_tree"]
        self.assertEqual(result[0]["types"][0]["intersection_leaf_count"], 1)
        pair = intersection[0]
        self.assertTrue(pair.get("diff_intersection_pair"))
        self.assertEqual((pair.get("ip_ref") or {}).get("str"), "10.0.0.3")
        self.assertEqual(pair.get("diff_status"), "both")
        self.assertTrue(pair.get("diff_same_name"))

    def test_addr_tree_node_renders_english_diff_labels(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "host-a",
                    "url": "#",
                    "ip_ref": {"str": "10.0.0.1", "url": "#"},
                    "diff_status": "only_a",
                    "diff_same_name": True,
                    "diff_name_a": "host-a",
                    "diff_url_a": "#",
                    "children": [],
                },
                "depth": 1,
                "prefix": "diff",
                "diff_label_a": "Tab A",
                "diff_label_b": "Tab B",
            },
        )
        self.assertNotIn("badge nsm-addr-diff", html)
        self.assertNotIn("only in Tab A", html)
        self.assertIn("nsm-ipa-diff-name-a", html)
        self.assertIn("host-a", html)
        self.assertNotIn("only A", html)

        html_both = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "shared",
                    "url": "#",
                    "ip_ref": {"str": "10.0.0.5", "url": "#"},
                    "diff_status": "both",
                    "diff_same_name": True,
                    "diff_name_a": "shared",
                    "diff_url_a": "#",
                    "children": [],
                },
                "depth": 1,
                "prefix": "diff-ipam",
            },
        )
        self.assertIn("nsm-ipa-diff-name-pill", html_both)
        self.assertIn("shared", html_both)
        self.assertNotIn("badge nsm-addr-diff", html_both)
        self.assertNotIn("nsm-addr-diff--side-a", html_both)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_empty_intersection_tree_when_no_overlap(
        self, _supports, build_nodes_fn
    ):
        build_nodes_fn.side_effect = [
            (
                [
                    {
                        "kind": "leaf",
                        "name": "a1",
                        "url": "#",
                        "ip_ref": {"str": "10.0.0.1", "url": "#"},
                        "children": [],
                    }
                ],
                [],
            ),
            (
                [
                    {
                        "kind": "leaf",
                        "name": "b1",
                        "url": "#",
                        "ip_ref": {"str": "10.0.0.2", "url": "#"},
                        "children": [],
                    }
                ],
                [],
            ),
        ]
        result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])
        self.assertEqual(result[0]["types"][0]["intersection_tree"], [])
        self.assertEqual(result[0]["types"][0]["intersection_leaf_count"], 0)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_fund_on_cross_side_name_mismatch(
        self, _supports, build_nodes_fn
    ):
        leaf_a = {
            "kind": "leaf",
            "name": "bench-ip-001",
            "url": "#a",
            "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "server-prod",
            "url": "#b",
            "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_a], []),
            ([leaf_b], []),
        ]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Tab A",
            label_b="Tab B",
        )

        groups = result[0]["types"][0]["nodes"]
        both_group = next(g for g in groups if g["diff_group"] == "both")
        self.assertEqual(both_group["diff_group"], "both")
        self.assertEqual(len(both_group["children"]), 1)
        leaf = both_group["children"][0]
        self.assertEqual(leaf["diff_status"], "both")
        self.assertTrue(leaf.get("diff_suppress_status"))
        self.assertTrue(leaf.get("diff_fund"))
        self.assertIn("bench-ip-001", leaf.get("fund_tooltip", ""))
        self.assertIn("server-prod", leaf.get("fund_tooltip", ""))
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(summary["both"], 1)
        self.assertEqual(summary["fund"], 1)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_no_fund_when_same_name_and_ip(
        self, _supports, build_nodes_fn
    ):
        leaf = {
            "kind": "leaf",
            "name": "shared-host",
            "url": "#",
            "ip_ref": {"str": "10.0.0.5/32", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf], []),
            ([dict(leaf)], []),
        ]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
        )

        both_group = next(
            g for g in result[0]["types"][0]["nodes"] if g["diff_group"] == "both"
        )
        both_leaf = both_group["children"][0]
        self.assertEqual(both_leaf["diff_status"], "both")
        self.assertTrue(both_leaf.get("diff_suppress_status"))
        self.assertFalse(both_leaf.get("diff_fund"))
        self.assertTrue(both_leaf.get("diff_same_name"))
        self.assertEqual(result[0]["types"][0]["diff_summary"]["fund"], 0)

    def test_addr_tree_node_renders_diff_name_pill_two_colors(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "bench-ip-0013031",
                    "url": "#a",
                    "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
                    "diff_status": "both",
                    "diff_same_name": False,
                    "diff_name_a": "bench-ip-0013031",
                    "diff_name_b": "server-prod",
                    "diff_url_a": "#a",
                    "diff_url_b": "#b",
                    "diff_intersection_pair": True,
                    "children": [],
                },
                "depth": 1,
                "prefix": "diff-ipam",
            },
        )
        self.assertIn("nsm-ipa-diff-name-pill", html)
        self.assertIn("nsm-ipa-diff-name-a", html)
        self.assertIn("nsm-ipa-diff-name-b", html)
        self.assertIn("bench-ip-0013031", html)
        self.assertIn("server-prod", html)
        self.assertIn("nsm-ipa-diff-name-sep", html)
        self.assertNotIn("only in", html)

    def test_build_addr_diff_analysis_sets_diff_name_fields_on_fund(self):
        leaf_a = {
            "kind": "leaf",
            "name": "bench-ip-0013031",
            "url": "#a",
            "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
            "children": [],
        }
        leaf_b = {
            "kind": "leaf",
            "name": "server-prod",
            "url": "#b",
            "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
            "children": [],
        }
        with patch(
            "netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes"
        ) as build_nodes_fn, patch(
            "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
            return_value=True,
        ):
            build_nodes_fn.side_effect = [([leaf_a], []), ([leaf_b], [])]
            result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])

        both_leaf = next(
            g for g in result[0]["types"][0]["nodes"] if g["diff_group"] == "both"
        )["children"][0]
        self.assertFalse(both_leaf.get("diff_same_name"))
        self.assertEqual(both_leaf.get("diff_name_a"), "bench-ip-0013031")
        self.assertEqual(both_leaf.get("diff_name_b"), "server-prod")

        intersection = result[0]["types"][0]["intersection_tree"][0]
        self.assertFalse(intersection.get("diff_same_name"))
        self.assertEqual(intersection.get("diff_name_a"), "bench-ip-0013031")
        self.assertEqual(intersection.get("diff_name_b"), "server-prod")

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_intersection_tree_rolls_up_shared_prefix(
        self, _supports, build_nodes_fn
    ):
        host_leaves = [
            {
                "kind": "leaf",
                "name": f"host-{i}",
                "url": f"#ip{i}",
                "ip_ref": {"str": f"10.129.169.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in (1, 2, 3)
        ]
        prefix_a = {
            "kind": "group",
            "name": "net-left",
            "url": "#prefix-a",
            "ip_ref": {
                "str": "10.129.169.0/24",
                "url": "#prefix-a",
                "type": "Prefix",
                "ct": 11,
                "pk": 24,
            },
            "prefix_display_cidr": "10.129.169.0/24",
            "children": [
                {
                    "kind": "category",
                    "name": "IP Addresses",
                    "count": 3,
                    "children": host_leaves,
                }
            ],
        }
        prefix_b = {
            **prefix_a,
            "name": "net-right",
            "url": "#prefix-b",
        }
        build_nodes_fn.side_effect = [([prefix_a], []), ([prefix_b], [])]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Rule 2/5",
            label_b="Rule 3/5",
        )

        intersection = result[0]["types"][0]["intersection_tree"]
        self.assertEqual(len(intersection), 1)
        node = intersection[0]
        self.assertTrue(node.get("diff_ipam_hierarchy_prefix"))
        self.assertFalse(node.get("diff_intersection_pair"))
        self.assertEqual((node.get("ip_ref") or {}).get("str"), "10.129.169.0/24")
        self.assertEqual(node.get("kind"), "group")
        self.assertEqual(len(node.get("children") or []), 3)
        for child in node["children"]:
            self.assertTrue(child.get("diff_intersection_pair"))
        self.assertEqual(result[0]["types"][0]["intersection_leaf_count"], 3)
        both_group = next(
            g for g in result[0]["types"][0]["nodes"] if g["diff_group"] == "both"
        )
        self.assertEqual(len(both_group["children"]), 1)
        prefix_node = both_group["children"][0]
        self.assertTrue(prefix_node.get("diff_ipam_hierarchy_prefix"))
        self.assertEqual(
            (prefix_node.get("ip_ref") or {}).get("str"), "10.129.169.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), 3)
        for child in prefix_node["children"]:
            self.assertEqual(child.get("diff_status"), "both")
            self.assertTrue(child.get("diff_suppress_status"))

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_both_group_rolls_up_many_shared_hosts(
        self, _supports, build_nodes_fn
    ):
        host_count = 200
        host_leaves = [
            {
                "kind": "leaf",
                "name": f"host-{i}",
                "url": f"#ip{i}",
                "ip_ref": {"str": f"10.128.182.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in range(1, host_count + 1)
        ]
        prefix_group = {
            "kind": "group",
            "name": "shared-net",
            "url": "#prefix",
            "ip_ref": {
                "str": "10.128.182.0/24",
                "url": "#prefix",
                "type": "Prefix",
                "ct": 11,
                "pk": 182,
            },
            "prefix_display_cidr": "10.128.182.0/24",
            "children": [
                {
                    "kind": "category",
                    "name": "IP Addresses",
                    "count": host_count,
                    "children": host_leaves,
                }
            ],
        }
        build_nodes_fn.side_effect = [([prefix_group], []), ([prefix_group], [])]

        result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])
        both_group = next(
            g for g in result[0]["types"][0]["nodes"] if g["diff_group"] == "both"
        )
        self.assertEqual(len(both_group["children"]), 1)
        prefix_node = both_group["children"][0]
        self.assertTrue(prefix_node.get("diff_ipam_hierarchy_prefix"))
        self.assertEqual(
            (prefix_node.get("ip_ref") or {}).get("str"), "10.128.182.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), host_count)
        self.assertEqual(result[0]["types"][0]["diff_summary"]["both"], host_count)

    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_intersection_tree_keeps_hosts_when_prefix_incomplete(
        self, _supports, build_nodes_fn
    ):
        shared_leaf = {
            "kind": "leaf",
            "name": "host-1",
            "url": "#ip1",
            "ip_ref": {"str": "10.129.169.1/32", "url": "#ip1"},
            "children": [],
        }
        only_b_leaf = {
            "kind": "leaf",
            "name": "host-2",
            "url": "#ip2",
            "ip_ref": {"str": "10.129.169.2/32", "url": "#ip2"},
            "children": [],
        }
        prefix_group = {
            "kind": "group",
            "name": "net",
            "url": "#prefix",
            "ip_ref": {
                "str": "10.129.169.0/24",
                "url": "#prefix",
                "type": "Prefix",
                "ct": 11,
                "pk": 24,
            },
            "prefix_display_cidr": "10.129.169.0/24",
            "children": [
                {
                    "kind": "category",
                    "name": "IP Addresses",
                    "count": 2,
                    "children": [shared_leaf, only_b_leaf],
                }
            ],
        }
        build_nodes_fn.side_effect = [
            (
                [
                    {
                        **prefix_group,
                        "children": [
                            {
                                "kind": "category",
                                "name": "IP Addresses",
                                "count": 1,
                                "children": [shared_leaf],
                            }
                        ],
                    }
                ],
                [],
            ),
            ([prefix_group], []),
        ]

        result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])
        intersection = result[0]["types"][0]["intersection_tree"]
        self.assertEqual(len(intersection), 1)
        prefix_node = intersection[0]
        self.assertTrue(prefix_node.get("diff_ipam_hierarchy_prefix"))
        self.assertEqual(
            (prefix_node.get("ip_ref") or {}).get("str"), "10.129.169.0/24"
        )
        self.assertEqual(prefix_node.get("kind"), "group")
        self.assertEqual(len(prefix_node.get("children") or []), 1)
        host = prefix_node["children"][0]
        self.assertTrue(host.get("diff_intersection_pair"))
        self.assertEqual((host.get("ip_ref") or {}).get("str"), "10.129.169.1/32")
        self.assertEqual(host.get("kind"), "leaf")

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    @patch("netbox_nsm.analysis.addr_analysis_utils._lookup_containing_prefix_for_intersection_node")
    def test_build_addr_diff_intersection_tree_nests_flat_ips_under_prefix(
        self, lookup_prefix_fn, _supports, build_nodes_fn, content_type_cls
    ):
        import ipaddress

        from ipam.models import Prefix

        ct = MagicMock()
        ct.pk = 11
        content_type_cls.objects.get_for_model.return_value = ct

        p24 = MagicMock(spec=Prefix)
        p24.pk = 182
        p24.prefix = ipaddress.ip_network("10.128.182.0/24")
        p24.__str__ = MagicMock(return_value="10.128.182.0/24")
        p24.get_absolute_url.return_value = "/ipam/prefixes/182/"
        lookup_prefix_fn.return_value = p24

        shared_leaves = [
            {
                "kind": "leaf",
                "name": f"host-{i}",
                "url": f"#ip{i}",
                "ip_ref": {"str": f"10.128.182.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in (1, 10)
        ]
        build_nodes_fn.side_effect = [(shared_leaves, []), (shared_leaves, [])]

        result = _build_addr_diff_analysis([MagicMock()], [MagicMock()])
        intersection = result[0]["types"][0]["intersection_tree"]
        self.assertEqual(len(intersection), 1)
        prefix_node = intersection[0]
        self.assertTrue(prefix_node.get("diff_ipam_hierarchy_prefix"))
        self.assertEqual(
            (prefix_node.get("ip_ref") or {}).get("str"), "10.128.182.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), 2)
        child_keys = {
            (child.get("ip_ref") or {}).get("str")
            for child in prefix_node["children"]
        }
        self.assertEqual(
            child_keys, {"10.128.182.1/32", "10.128.182.10/32"}
        )
        for child in prefix_node["children"]:
            self.assertTrue(child.get("diff_intersection_pair"))

    def test_addr_tree_node_diff_leaf_omits_redundant_status_badge(self):
        from django.template.loader import render_to_string

        for diff_status, diff_label, suppress_status in (
            ("only_a", "Tab A", False),
            ("only_b", "Tab B", False),
            ("both", None, True),
        ):
            with self.subTest(diff_status=diff_status):
                html = render_to_string(
                    "netbox_nsm/inc/addr_tree_node.html",
                    {
                        "node": {
                            "kind": "leaf",
                            "name": "bench-ip-001",
                            "url": "#",
                            "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
                            "diff_status": diff_status,
                            "diff_suppress_status": suppress_status,
                            "diff_name_a": "bench-ip-001",
                            "diff_name_b": "bench-ip-001",
                            "diff_url_a": "#",
                            "diff_url_b": "#",
                            "children": [],
                        },
                        "depth": 1,
                        "prefix": "diff",
                        "diff_label_a": "Tab A",
                        "diff_label_b": "Tab B",
                    },
                )
                self.assertNotIn("badge nsm-addr-diff", html)
                if suppress_status:
                    self.assertNotIn(
                        "nsm-addr-diff-leaf--" + diff_status, html
                    )
                else:
                    self.assertIn("nsm-addr-diff-leaf--" + diff_status, html)
                self.assertIn("10.1.1.1/32", html)
                if diff_label:
                    self.assertNotIn(f"only in {diff_label}", html)

    def test_addr_tree_node_renders_diff_fund_badge(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "bench-ip-001",
                    "url": "#",
                    "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
                    "diff_status": "both",
                    "diff_fund": True,
                    "fund_tooltip": "Same IP, different names (A: bench-ip-001; B: server-prod)",
                    "children": [],
                },
                "depth": 1,
                "prefix": "src",
            },
        )
        self.assertIn("nsm-addr-fund", html)
        self.assertIn("Fund", html)
        self.assertIn("nsm-addr-diff-leaf--fund", html)


class IpAnalyzerMergeAssetsTests(SimpleTestCase):
    """Static checks for multi-tab Merge/Diff in the floating applet."""

    def test_applet_js_exposes_merge_ui(self):
        js = (_PLUGIN_ROOT / "plugin_assets/js/nsm_ip_analyzer_applet.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("nsm-ipa-applet-merge", js)
        self.assertIn("mergeTabs", js)
        self.assertIn("collectObjectsFromTabs", js)
        self.assertIn("collectRawObjects", js)
        self.assertIn("rawObjects", js)
        self.assertIn("Merged (", js)
        self.assertIn("scheduleBodyScale", js)
        self.assertIn("nsm-ipa-applet-body-scale", js)
        self.assertIn("loupeCellContainer", js)
        self.assertIn("collectRulesCellContext", js)
        self.assertIn("rulesCellTabTitle", js)
        self.assertIn("rulesCellContextLabel", js)
        self.assertIn("diffTabContextLabel", js)
        self.assertIn("contextLabel: diffTabContextLabel(sourceTabs)", js)
        self.assertIn("rulesCellDiffSideLabel", js)
        self.assertIn("diffSideLabel", js)
        self.assertIn("diffLabel", js)
        self.assertIn('"Rule "', js)

    def test_collect_cell_objects_skips_probes_when_visible_items_exist(self):
        js = (_PLUGIN_ROOT / "plugin_assets/js/nsm_ip_analyzer_applet.js").read_text(
            encoding="utf-8"
        )
        self.assertIn(":not(.nsm-ag-cell-item--probe)", js)
        self.assertIn("nsm-ag-cell-item--probe[data-addr-analyzable", js)

    def test_applet_js_exposes_diff_ui(self):
        js = (_PLUGIN_ROOT / "plugin_assets/js/nsm_ip_analyzer_applet.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("nsm-ipa-applet-diff", js)
        self.assertIn("diffTabs", js)
        self.assertIn("buildDiffQuery", js)
        self.assertIn("diffTabTitleFromTabs", js)
        self.assertIn("formatDiffSummary", js)
        self.assertIn("tab.sides", js)
        self.assertIn('mode", "diff"', js)
        self.assertIn("Diff (", js)
        self.assertIn("var canDiff = this.tabs.length >= 2", js)
        self.assertIn("mindestens 2 Tabs", js)
        self.assertNotIn("var canDiff = this.tabs.length === 2", js)
        self.assertIn("Fund:", js)
        self.assertIn("nsm-ipa-applet-toolbar", js)
        self.assertIn("nsm-ipa-applet-toolbar-actions", js)
        self.assertIn("nsm-ipa-applet-add-object", js)
        self.assertIn("Objekt hinzufügen", js)
        self.assertIn("_pickAddObject", js)
        self.assertIn("addObjectTypesApiUrl", js)
        self.assertIn("nsm-ipa-applet-add-modal", js)

    def test_applet_css_integrates_object_tree_in_addr_children(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ipa-applet .nsm-addr-children .nsm-ipa-object-tree-rows", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-subnet-contained", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node--subnet-warning", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node--doppelt-warning", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-expanded-warnings", css)
        self.assertNotIn(".nsm-ipa-applet .nsm-ipa-tree-dots", css)
        self.assertNotIn(".nsm-ipa-object-tree-title", css)
        self.assertNotIn(".nsm-ipa-object-tree {", css)
        self.assertNotIn(".nsm-ipa-object-tree-dots", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-cell-pill", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-diff-name-pill .nsm-ipa-diff-name-a", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-diff-name-pill .nsm-ipa-diff-name-b", css)
        self.assertIn("var(--nsm-ipa-accent)", css)
        self.assertNotIn("border-left: 3px solid var(--nsm-ipa-accent)", css)
        self.assertIn(".nsm-ipa-applet .nsm-ipa-addr-drilldown .nsm-addr-summary", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-addr-leaf-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node > \.nsm-addr-summary\s*\{[^}]*padding:\s*0",
        )
        self.assertIn(".nsm-ipa-applet .nsm-ipa-object-node", css)
        self.assertIn("gap: 0", css)
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-addr-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-addr-leaf-summary,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node > \.nsm-addr-summary\s*\{[^}]*line-height:\s*1;",
        )
        self.assertIn(
            ".nsm-ipa-applet .nsm-addr-children .nsm-ipa-object-tree-rows > details.nsm-ipa-object-node + details.nsm-ipa-object-node",
            css,
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*display:\s*inline-block",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*padding:\s*0 0\.28rem",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill\s*\{[^}]*line-height:\s*1;",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-addr-link,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-cell-pill \.nsm-addr-obj-link\s*\{[^}]*margin:\s*0",
        )

    def test_subnet_warning_pill_keeps_accent_text_and_warning_border(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet summary\.nsm-ipa-object-node--subnet-warning \.nsm-ipa-cell-pill,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-ipa-cell-pill\s*\{"
            r"[^}]*border:\s*1px solid var\(--bs-warning,\s*var\(--tblr-warning,\s*#f59f0a\)\) !important",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet summary\.nsm-ipa-object-node--subnet-warning \.nsm-ipa-cell-pill,\s*"
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-ipa-cell-pill\s*\{"
            r"[^}]*border-color:\s*var\(--bs-warning,\s*var\(--tblr-warning,\s*#f59f0a\)\)",
        )
        self.assertNotRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-ipa-cell-pill\s*\{[^}]*background:",
        )
        self.assertNotIn(
            ".nsm-ipa-object-node--subnet-warning .nsm-ipa-cell-pill .nsm-addr-obj-link",
            css,
        )
        self.assertNotRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-addr-obj-link",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-addr-ip",
        )
        self.assertRegex(
            css,
            r"\.nsm-ipa-applet \.nsm-ipa-object-node--subnet-warning \.nsm-addr-prefix-text",
        )

    def test_diff_status_badges_use_solid_contrast(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/addr_analysis_assets.html"
        ).read_text(encoding="utf-8")
        for source in (css, assets):
            self.assertRegex(
                source,
                r"\.nsm-addr-diff--only_a[^}]*background-color:\s*var\(--bs-primary",
            )
            self.assertRegex(
                source,
                r"\.nsm-addr-diff--only_b[^}]*background-color:\s*var\(--bs-success",
            )
            self.assertIn("color: #fff", source)
            self.assertIn("--bs-badge-color: #fff", source)

    def test_applet_css_toolbar_above_tabs(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ipa-applet-toolbar", css)
        self.assertIn(".nsm-ipa-applet-toolbar-actions", css)
        self.assertIn(".nsm-ipa-applet-add-object", css)
        self.assertIn(".nsm-ipa-applet-add-modal", css)
        self.assertIn(".nsm-ipa-applet--has-toolbar", css)

    @patch("netbox_nsm.analysis.ipa_add_object_types.get_api_url_for_content_type")
    @patch("netbox_nsm.analysis.ipa_add_object_types.ContentType")
    def test_build_ipa_add_object_categories_includes_ipam_and_cot(
        self, content_type_cls, api_url_fn
    ):
        from netbox_nsm.analysis.ipa_add_object_types import build_ipa_add_object_categories

        prefix_ct = MagicMock(pk=11)
        addr_ct = MagicMock(pk=22)
        group_ct = MagicMock(pk=33)

        def get_ct(app_label, model):
            ct = MagicMock()
            if (app_label, model) == ("ipam", "prefix"):
                ct.pk = 11
            elif (app_label, model) == ("ipam", "ipaddress"):
                ct.pk = 12
            elif (app_label, model) == ("ipam", "iprange"):
                ct.pk = 13
            elif app_label == "netbox_custom_objects" and model == "table7model":
                ct.pk = 22
            elif app_label == "netbox_custom_objects" and model == "table8model":
                ct.pk = 33
            else:
                raise content_type_cls.DoesNotExist
            return ct

        content_type_cls.objects.get.side_effect = get_ct
        content_type_cls.DoesNotExist = Exception
        api_url_fn.side_effect = lambda ct: f"/api/example/{ct.pk}/"

        cot_address = MagicMock(pk=7, slug="nsm_address")
        cot_group = MagicMock(pk=8, slug="nsm_address_group")

        with patch(
            "netbox_custom_objects.models.CustomObjectType.objects.filter"
        ) as cot_filter:
            cot_filter.return_value.only.return_value.first.side_effect = [
                cot_address,
                cot_group,
            ]
            categories = build_ipa_add_object_categories()

        self.assertEqual([cat["id"] for cat in categories], ["ipam", "nsm_address", "nsm_address_group"])
        self.assertEqual(len(categories[0]["types"]), 3)
        self.assertEqual(categories[1]["types"][0]["ct_id"], 22)
        self.assertEqual(categories[2]["types"][0]["ct_id"], 33)

    def test_applet_assets_cache_bust_bumped(self):
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/nsm_ip_analyzer_applet_assets.html"
        ).read_text(encoding="utf-8")
        self.assertIn("nsm_ip_analyzer_applet.js", assets)
        self.assertIn("?v=202606138", assets)
        self.assertIn("NSM_IP_ANALYSIS_ADD_OBJECT_TYPES_API", assets)

    def test_merged_cell_loupe_corner_hover_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/rulebook_rules.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ag-cell-merged--has-loupe > .nsm-ipa-cell-loupe", css)
        self.assertIn("left: auto", css)
        self.assertIn(
            ".nsm-ag-cell-merged--has-loupe:hover > .nsm-ipa-cell-loupe", css
        )

    def test_cell_loupe_list_position_scoped_in_applet_css(self):
        css = (_PLUGIN_ROOT / "plugin_assets/css/nsm_ip_analyzer_applet.css").read_text(
            encoding="utf-8"
        )
        self.assertIn(".nsm-ag-cell-list--has-loupe > .nsm-ipa-cell-loupe", css)
        self.assertNotRegex(
            css,
            r"(?<!\.)nsm-ipa-cell-loupe\s*\{[^}]*position:\s*absolute",
        )


class IpaCellObjectTreeTests(SimpleTestCase):
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipa_object_tree_node")
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
        raw = [
            {"ct": "10", "pk": "5", "name": "bench-ip"},
            {"ct": "10", "pk": "5", "name": "bench-ip"},
        ]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 5): obj})
        self.assertEqual(len(nodes), 2)
        self.assertFalse(nodes[0].get("is_doppelt"))
        self.assertTrue(nodes[1].get("is_doppelt"))
        self.assertNotIn("object_duplicate", nodes[1])

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

        members_fn.side_effect = lambda obj: [shared] if obj is group_a else [shared]

        raw = [
            {"ct": "10", "pk": "10", "name": "group-a"},
            {"ct": "10", "pk": "11", "name": "group-b"},
        ]
        obj_by_key = {(10, 10): group_a, (10, 11): group_b}
        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)

        self.assertEqual(len(nodes), 2)
        shared_nodes = [
            child
            for root in nodes
            for child in root.get("children") or []
            if child.get("name") == "shared-ip"
        ]
        self.assertEqual(len(shared_nodes), 2)
        self.assertFalse(shared_nodes[0].get("object_duplicate"))
        self.assertTrue(shared_nodes[1].get("object_duplicate"))
        self.assertEqual(shared_nodes[1].get("object_duplicate_of"), "shared-ip")

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
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

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "Objekt 3")
        child_names = [c["name"] for c in nodes[0].get("children") or []]
        self.assertEqual(child_names, ["objekt 1", "objekt 2"])

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ip_meta")
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

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members", return_value=[])
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ip_meta")
    def test_build_ipa_cell_object_tree_nests_by_ipam_prefix_hierarchy(
        self, attach_fn, _members_fn, content_type_cls
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
            self.assertTrue(child.get("is_cell_direct"))

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ip_meta", side_effect=lambda n, o: n)
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
        self.assertTrue(nodes[0].get("is_cell_direct"))
        nested_node = (nodes[0].get("children") or [])[0]
        self.assertEqual(nested_node["name"], "n-10.0.0.0/8")
        self.assertFalse(nested_node.get("is_cell_direct"))

    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_addr_node_prefix_display", side_effect=lambda n, **k: n)
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref_node_dict", return_value={"str": "10.1.0.0/16", "url": "#"})
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref", return_value={"str": "10.1.0.0/16", "url": "#", "type": "Prefix"})
    @patch("django.contrib.contenttypes.models.ContentType")
    def test_build_ipa_object_tree_node_attaches_ip_ref(
        self, content_type_cls, _ip_ref, ip_ref_dict_fn, _attach_fn
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
        self.assertEqual(node["kind"], "leaf")
        self.assertEqual(node["ip_ref"]["str"], "10.1.0.0/16")
        self.assertNotIn("is_cell_direct", node)
        ip_ref_dict_fn.assert_called_once()


class IpaObjectTreeTemplateIntegrationTests(SimpleTestCase):
    def test_object_tree_cell_direct_class_on_cell_objects(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "url": "/g/8/",
                "ct": "10",
                "pk": "8",
                "kind": "group",
                "is_cell_direct": True,
                "children": [
                    {
                        "name": "n-10.1.0.0/16",
                        "url": "/n/16/",
                        "ct": "10",
                        "pk": "16",
                        "kind": "leaf",
                        "children": [],
                    }
                ],
            },
            {
                "name": "bench-ip-0014328",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "leaf",
                "is_cell_direct": True,
                "ip_ref": {"str": "10.128.143.0/24", "url": "#"},
                "prefix_display_cidr": "10.128.143.0/24",
                "addr_drilldown_lazy": True,
                "children": [],
            },
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertEqual(html.count("nsm-ipa-object-node--cell-direct"), 2)
        self.assertEqual(html.count("nsm-ipa-cell-pill"), 2)
        self.assertIn("g-10.0.0.0/8", html)
        self.assertIn("n-10.1.0.0/16", html)
        self.assertIn("bench-ip-0014328", html)
        self.assertIn("nsm-ipa-addr-drilldown", html)
        drilldown_pos = html.index("nsm-ipa-addr-drilldown")
        self.assertNotIn(
            "nsm-ipa-object-node--cell-direct",
            html[drilldown_pos:],
        )
        self.assertNotIn("nsm-ipa-cell-pill", html[drilldown_pos:])
        group_summary_start = html.index("nsm-ipa-object-node--cell-direct")
        group_summary_end = html.index("</summary>", group_summary_start)
        group_summary_html = html[group_summary_start:group_summary_end]
        self.assertIn('class="nsm-ipa-cell-pill"', group_summary_html)
        self.assertIn("g-10.0.0.0/8", group_summary_html)
        self.assertNotIn("→", group_summary_html)
        leaf_summary_start = html.index("nsm-ipa-object-node--cell-direct", group_summary_end)
        leaf_summary_end = html.index("</summary>", leaf_summary_start)
        leaf_summary_html = html[leaf_summary_start:leaf_summary_end]
        self.assertIn('class="nsm-ipa-cell-pill"', leaf_summary_html)
        pill_end = leaf_summary_html.index("</span>", leaf_summary_html.index("nsm-ipa-cell-pill"))
        pill_html = leaf_summary_html[:pill_end]
        self.assertIn("bench-ip-0014328", pill_html)
        self.assertNotIn("→", pill_html)
        self.assertNotIn("10.128.143.0/24", pill_html)
        self.assertIn("→", leaf_summary_html[pill_end:])
        self.assertIn("10.128.143.0/24", leaf_summary_html[pill_end:])
        child_leaf_pos = html.index("n-10.1.0.0/16")
        child_leaf_end = html.index("</div>", child_leaf_pos)
        child_leaf_html = html[child_leaf_pos:child_leaf_end]
        self.assertNotIn("nsm-ipa-cell-pill", child_leaf_html)

    def test_object_tree_integrated_in_all_view_not_separate_section(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "group-a",
                "url": "/g/a/",
                "ct": "10",
                "pk": "10",
                "kind": "group",
                "children": [],
                "is_doppelt": False,
            },
            {
                "name": "bench-ip",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "leaf",
                "children": [],
                "is_doppelt": True,
            },
        ]
        addr_analysis = [
            {
                "field_name": "",
                "field_slug": "selected",
                "types": [
                    {
                        "type_name": "",
                        "leaf_count": 1,
                        "all_copy_lines": [],
                        "nodes": [
                            {
                                "name": "bench-ip",
                                "url": "/a/5/",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.0.0.1", "url": "#"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": addr_analysis, "object_tree": object_tree},
        )
        self.assertIn("nsm-addr-top", html)
        self.assertIn("nsm-ipa-object-tree-rows", html)
        self.assertIn("nsm-addr-details", html)
        self.assertIn("nsm-ipa-object-doppelt", html)
        self.assertIn("bench-ip", html)
        self.assertNotIn("nsm-ipa-object-tree-title", html)
        self.assertNotIn("nsm-ipa-object-tree-dots", html)
        self.assertNotIn("10.0.0.1", html)
        self.assertNotIn("nsm-ipa-object-tree-rows--has-addr", html)

    def test_object_tree_renders_subnet_warning(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "Objekt 3",
                "url": "/g/3/",
                "ct": "10",
                "pk": "3",
                "kind": "group",
                "ip_ref": {"str": "10.0.0.0/8", "url": "#"},
                "prefix_display_cidr": "10.0.0.0/8",
                "children": [
                    {
                        "name": "objekt 1",
                        "url": "/a/1/",
                        "kind": "group",
                        "ip_ref": {"str": "10.1.0.0/16", "url": "#"},
                        "prefix_display_cidr": "10.1.0.0/16",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [
                            {
                                "name": "objekt 2",
                                "url": "/a/2/",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
                                "prefix_display_cidr": "10.1.1.1/32",
                                "subnet_contained_in": "10.0.0.0/8",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertNotIn("nsm-ipa-tree-dots", html)
        self.assertNotIn("••", html)
        self.assertIn("nsm-ipa-subnet-contained", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertIn("mdi-alert-circle-outline", html)
        self.assertNotIn("(warn duplicate", html)
        self.assertIn("nsm-ipa-expanded-warning--subnet", html)
        self.assertIn("warn duplicate → 10.0.0.0/8", html)
        self.assertIn("10.0.0.0/8", html)
        self.assertIn("10.1.0.0/16", html)
        self.assertIn("10.1.1.1/32", html)

    def test_object_tree_only_renders_all_section(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "group-a",
                "url": "/g/a/",
                "ct": "10",
                "pk": "10",
                "kind": "group",
                "children": [{"name": "member", "url": "#", "kind": "leaf", "children": []}],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-addr-top", html)
        self.assertIn("nsm-ipa-object-tree-rows", html)
        self.assertIn("nsm-addr-details", html)
        self.assertIn("group-a", html)
        self.assertNotIn("nsm-ipa-object-tree-title", html)
        self.assertNotIn("nsm-ipa-object-tree-dots", html)

    def test_object_tree_renders_collapsed_with_lazy_drilldown_placeholder(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "bench-ip",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "leaf",
                "ip_ref": {"str": "10.128.130.0/24", "url": "#"},
                "prefix_display_cidr": "10.128.130.0/24",
                "addr_drilldown_lazy": True,
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-object-node", html)
        self.assertIn("nsm-ipa-addr-drilldown", html)
        self.assertIn('data-lazy-ct="10"', html)
        self.assertIn('data-lazy-pk="5"', html)
        self.assertNotIn('data-lazy-prefix=', html)
        self.assertNotRegex(html, r'<details[^>]*open[^>]*nsm-ipa-object-node')

    def test_object_tree_expanded_subnet_warning_with_lazy_drilldown(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "bench-ip-0014328",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "leaf",
                "ip_ref": {"str": "10.128.143.0/24", "url": "#"},
                "prefix_display_cidr": "10.128.143.0/24",
                "subnet_contained_in": "10.0.0.0/8",
                "subnet_contained_in_name": "g-10.0.0.0/8",
                "addr_drilldown_lazy": True,
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-subnet-contained", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertIn("nsm-ipa-expanded-warning--subnet", html)
        self.assertIn("warn duplicate → 10.0.0.0/8", html)
        self.assertIn("g-10.0.0.0/8", html)
        self.assertIn("nsm-ipa-addr-drilldown", html)
        expanded_pos = html.index("nsm-ipa-expanded-warning--subnet")
        drilldown_pos = html.index("nsm-ipa-addr-drilldown")
        self.assertLess(expanded_pos, drilldown_pos)

    def test_object_tree_expanded_doppelt_warning(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "bench-ip",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "group",
                "is_doppelt": True,
                "children": [
                    {
                        "name": "member",
                        "url": "#",
                        "kind": "leaf",
                        "children": [],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-object-doppelt", html)
        self.assertIn("nsm-ipa-object-node--doppelt-warning", html)
        self.assertIn("nsm-ipa-expanded-warning--doppelt", html)
        self.assertIn("Duplicate cell entry", html)

    def test_flatten_ipa_object_tree_copy_lines_includes_warn_duplicate(self):
        nodes = [
            {
                "name": "bench-ip",
                "ip_ref": {"str": "10.128.130.0/24"},
                "prefix_display_cidr": "10.128.130.0/24",
                "subnet_contained_in": "10.0.0.0/8",
                "children": [],
            }
        ]
        lines = _flatten_ipa_object_tree_copy_lines(nodes)
        self.assertEqual(
            lines,
            ["bench-ip,10.128.130.0/24,warn duplicate→10.0.0.0/8"],
        )

    @patch("netbox_nsm.analysis.addr_analysis_utils._ipa_object_has_addr_drilldown", return_value=True)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipa_object_tree_node")
    def test_build_ipa_cell_object_tree_marks_addr_drilldown_lazy(
        self, build_node_fn, drilldown_fn
    ):
        build_node_fn.side_effect = lambda obj, **kwargs: {
            "name": obj.name,
            "url": "#",
            "ct": "10",
            "pk": str(obj.pk),
            "kind": "leaf",
            "children": [],
        }
        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        raw = [{"ct": "10", "pk": "5", "name": "bench-ip"}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 5): obj})
        self.assertTrue(nodes[0].get("addr_drilldown_lazy"))
        drilldown_fn.assert_called()

    def test_all_summary_renders_subnet_range_ip_badges(self):
        from django.template.loader import render_to_string

        addr_analysis = [
            {
                "field_name": "",
                "field_slug": "selected",
                "types": [
                    {
                        "type_name": "",
                        "leaf_count": 50000,
                        "count_subnets": 1,
                        "count_ranges": 0,
                        "count_ips": 50000,
                        "all_copy_lines": [],
                        "nodes": [
                            {
                                "name": "g-10.0.0.0/8",
                                "url": "/g/1/",
                                "kind": "group",
                                "ipam_stats": _ordered_ipam_stats(
                                    {
                                        "child_prefixes": {"count": 1},
                                        "ip_addresses": {"count": 50000},
                                        "ip_ranges": {"count": 0},
                                    }
                                ),
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": addr_analysis, "object_tree": None},
        )
        self.assertIn("Subnets: 1", html)
        self.assertIn("Ranges: 0", html)
        self.assertIn("IPs: 50000", html)

    def test_all_summary_renders_duplicate_badge_from_object_tree(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "g-10.0.0.0/8",
                "kind": "group",
                "children": [
                    {
                        "name": "bench-a",
                        "kind": "leaf",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                    {
                        "name": "bench-b",
                        "kind": "leaf",
                        "subnet_contained_in": "10.0.0.0/8",
                        "children": [],
                    },
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": [],
                "object_tree": object_tree,
                "summary_type_counts": {
                    "count_subnets": 2,
                    "count_ranges": 0,
                    "count_ips": 0,
                    "count_duplicates": 2,
                },
            },
        )
        self.assertIn("Warnings: 2", html)
        self.assertIn("nsm-addr-duplicate-summary", html)
        self.assertIn("bg-warning-subtle", html)

    def test_all_summary_renders_duplicate_badge_in_addr_analysis_row(self):
        from django.template.loader import render_to_string

        addr_analysis = [
            {
                "field_name": "",
                "field_slug": "selected",
                "types": [
                    {
                        "type_name": "",
                        "leaf_count": 50000,
                        "count_subnets": 1,
                        "count_ranges": 0,
                        "count_ips": 50000,
                        "count_duplicates": 3,
                        "all_copy_lines": [],
                        "nodes": [],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": addr_analysis,
                "object_tree": [{"name": "g-10.0.0.0/8", "children": []}],
            },
        )
        self.assertIn("Warnings: 3", html)

    def test_addr_tree_still_renders_without_object_tree(self):
        from django.template.loader import render_to_string

        addr_analysis = [
            {
                "field_name": "",
                "field_slug": "selected",
                "types": [
                    {
                        "type_name": "",
                        "leaf_count": 1,
                        "all_copy_lines": [],
                        "nodes": [
                            {
                                "name": "bench-ip",
                                "url": "/a/5/",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.0.0.1", "url": "#"},
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": addr_analysis, "object_tree": None},
        )
        self.assertIn("10.0.0.1", html)
        self.assertNotIn("nsm-ipa-object-tree-rows", html)
