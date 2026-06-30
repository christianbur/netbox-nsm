"""Tests for address diff analysis."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils import (
    _addr_leaf_compare_key,
    _build_addr_diff_analysis,
    _build_addr_diff_analysis_from_sides,
    _build_addr_diff_group,
    _collect_addr_tree_leaf_map,
    _count_addr_tree_duplicates,
    _filter_non_contained_addr_nodes,
    _mark_contained_addr_duplicate_flags,
    _resolve_summary_type_counts,
    _type_counts_for_diff_addr_keys,
)

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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_analysis_rolls_up_only_side_prefix(
        self, _supports, build_nodes_fn
    ):
        host_leaves = [
            {
                "kind": "leaf",
                "name": f"host-{i}",
                "url": f"#ip{i}",
                "ip_ref": {"str": f"198.19.170.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in (1, 2, 3)
        ]
        prefix = {
            "kind": "group",
            "name": "net-left",
            "url": "#prefix-a",
            "ip_ref": {
                "str": "198.19.170.0/24",
                "url": "#prefix-a",
                "type": "Prefix",
                "ct": 11,
                "pk": 170,
            },
            "prefix_display_cidr": "198.19.170.0/24",
            "children": [
                {
                    "kind": "category",
                    "name": "IP Addresses",
                    "count": 3,
                    "children": host_leaves,
                }
            ],
        }
        build_nodes_fn.side_effect = [([prefix], []), ([], [])]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Rule 1/5",
            label_b="Rule 3/7",
        )

        only_group = next(
            g for g in result[0]["types"][0]["nodes"] if g["diff_group"] == "only-a"
        )
        self.assertEqual(only_group["diff_label"], "Rule 1/5")
        self.assertEqual(len(only_group["children"]), 1)
        prefix_node = only_group["children"][0]
        self.assertTrue(prefix_node.get("diff_ipam_hierarchy_prefix"))
        self.assertEqual(
            (prefix_node.get("ip_ref") or {}).get("str"), "198.19.170.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), 3)
        for child in prefix_node["children"]:
            self.assertEqual(child.get("diff_status"), "only_a")
            self.assertEqual(child.get("diff_label"), "Rule 1/5")

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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
        self.assertEqual(group_by_slug["in-some"]["name"], "In some")
        self.assertEqual(
            group_by_slug["in-some"]["diff_present_labels"], ["Tab 1", "Tab 3"]
        )
        self.assertEqual(len(group_by_slug["in-some"]["children"]), 1)
        self.assertEqual(
            group_by_slug["in-some"]["children"][0]["diff_present_labels"],
            ["Tab 1", "Tab 3"],
        )
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(summary["side_count"], 3)
        self.assertEqual(summary["in_all"], 1)
        self.assertEqual(summary["in_some"], 1)
        self.assertEqual(summary["only_by_side"][0]["count"], 1)
        self.assertEqual(summary["only_by_side"][1]["count"], 1)
        self.assertEqual(summary["only_by_side"][2]["count"], 1)

    def test_build_addr_diff_group_stores_diff_present_labels(self):
        group = _build_addr_diff_group(
            "In some",
            [{"kind": "leaf", "name": "x", "url": "#", "children": []}],
            diff_group="in-some",
            diff_present_labels=["Tab 1", "Tab 3"],
        )
        self.assertEqual(group["name"], "In some")
        self.assertEqual(group["diff_present_labels"], ["Tab 1", "Tab 3"])

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_in_some_splits_by_presence_pattern(
        self, _supports, build_nodes_fn
    ):
        def leaf(name, ip):
            return {
                "kind": "leaf",
                "name": name,
                "url": "#",
                "ip_ref": {"str": ip, "url": "#"},
                "children": [],
            }

        build_nodes_fn.side_effect = [
            ([leaf("t0-only", "10.0.0.1"), leaf("shared", "10.0.0.9"), leaf("ab", "10.0.0.5")], []),
            ([leaf("t1-only", "10.0.0.2"), leaf("shared", "10.0.0.9")], []),
            ([leaf("t2-only", "10.0.0.3"), leaf("shared", "10.0.0.9"), leaf("cd", "10.0.0.6")], []),
            ([leaf("t3-only", "10.0.0.4"), leaf("shared", "10.0.0.9"), leaf("ab", "10.0.0.5"), leaf("cd", "10.0.0.6")], []),
        ]
        result = _build_addr_diff_analysis_from_sides(
            [
                {"objs": [MagicMock()], "label": "Rule A / destination"},
                {"objs": [MagicMock()], "label": "Rule B / destination"},
                {"objs": [MagicMock()], "label": "Rule C / destination"},
                {"objs": [MagicMock()], "label": "Rule D / destination"},
            ]
        )
        in_some_groups = [
            g
            for g in result[0]["types"][0]["nodes"]
            if g.get("diff_group") == "in-some"
        ]
        self.assertEqual(len(in_some_groups), 2)
        labels_by_name = {
            tuple(g["diff_present_labels"]): g["name"] for g in in_some_groups
        }
        self.assertEqual(
            labels_by_name[("Rule A / destination", "Rule D / destination")],
            "In some",
        )
        self.assertEqual(
            labels_by_name[("Rule C / destination", "Rule D / destination")],
            "In some",
        )

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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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
        self.assertIn("Name conflict: 3", all_block)
        self.assertIn("nsm-addr-diff-in-both", all_block)
        self.assertIn("bg-warning-subtle text-warning", all_block)

    def test_addr_analysis_panel_omits_ipam_hierarchy_intersection_block(self):
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
                                        "name": "198.18.182.0/24",
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
        self.assertNotIn("IPAM hierarchy (in both)", html)
        self.assertNotIn("nsm-addr-diff-intersection", html)
        self.assertNotIn("nsm-addr-diff-intersection-separator", html)
        only_pos = html.index("Only in Left")
        all_pos = html.index("All")
        self.assertLess(all_pos, only_pos)

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_same_subnet_different_hosts_not_in_both(
        self, _supports, build_nodes_fn
    ):
        """Hosts in the same /24 but different /32 must not appear under In both."""
        leaf_18231 = {
            "kind": "leaf",
            "name": "bench-ip-0018231",
            "url": "#a",
            "ip_ref": {"str": "198.18.182.32/32", "url": "#"},
            "children": [],
        }
        leaf_18210 = {
            "kind": "leaf",
            "name": "bench-ip-0018210",
            "url": "#b",
            "ip_ref": {"str": "198.18.182.11/32", "url": "#"},
            "children": [],
        }
        build_nodes_fn.side_effect = [
            ([leaf_18231], []),
            ([leaf_18210], []),
        ]

        result = _build_addr_diff_analysis(
            [MagicMock()],
            [MagicMock()],
            label_a="Rule 2",
            label_b="Rule 3",
        )

        groups = result[0]["types"][0]["nodes"]
        both_groups = [g for g in groups if g.get("diff_group") == "both"]
        self.assertEqual(both_groups, [])
        summary = result[0]["types"][0]["diff_summary"]
        self.assertEqual(summary["both"], 0)
        self.assertEqual(summary["only_a"], 1)
        self.assertEqual(summary["only_b"], 1)
        self.assertEqual(result[0]["types"][0]["intersection_leaf_count"], 0)

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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
                "ipa_cell_pill": False,
            },
        )
        self.assertIn("nsm-ipa-diff-name-pill", html)
        self.assertIn("bench-ip-0013031", html)
        self.assertIn("server-prod", html)
        self.assertIn("nsm-ipa-diff-name-sep", html)
        self.assertNotIn("only in", html)

    def test_addr_tree_node_renders_address_pill_in_ipa_diff_mode(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip_analyzer.addr_diff_fund import _enrich_diff_cell_pill_fields

        node = {
            "kind": "leaf",
            "name": "dm-addr-10-112-134-0-24",
            "url": "#a",
            "ip_ref": {"str": "10.112.134.0/24", "url": "#"},
            "prefix_display_cidr": "10.112.134.0/24",
            "diff_status": "both",
            "diff_same_name": True,
            "diff_name_a": "dm-addr-10-112-134-0-24",
            "diff_url_a": "#a",
            "children": [],
        }
        _enrich_diff_cell_pill_fields(node, entry={"source_objects": [{"name": node["name"], "url": "#a"}]})
        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": node,
                "depth": 2,
                "prefix": "ipa",
                "ipa_cell_pill": True,
            },
        )
        self.assertIn("nsm-ipa-cell-type", html)
        self.assertIn("ADDRESS", html)
        self.assertIn("dm-addr-10-112-134-0-24", html)
        self.assertIn("10.112.134.0/24", html)
        self.assertNotIn("nsm-ipa-diff-name-pill", html)
        self.assertNotIn("nsm-addr-ip", html)
        self.assertNotIn("→", html)

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
            "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes"
        ) as build_nodes_fn, patch(
            "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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
                "ip_ref": {"str": f"198.19.169.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in (1, 2, 3)
        ]
        prefix_a = {
            "kind": "group",
            "name": "net-left",
            "url": "#prefix-a",
            "ip_ref": {
                "str": "198.19.169.0/24",
                "url": "#prefix-a",
                "type": "Prefix",
                "ct": 11,
                "pk": 24,
            },
            "prefix_display_cidr": "198.19.169.0/24",
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
        self.assertEqual((node.get("ip_ref") or {}).get("str"), "198.19.169.0/24")
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
            (prefix_node.get("ip_ref") or {}).get("str"), "198.19.169.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), 3)
        for child in prefix_node["children"]:
            self.assertEqual(child.get("diff_status"), "both")
            self.assertTrue(child.get("diff_suppress_status"))

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
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
                "ip_ref": {"str": f"198.18.182.{i}/32", "url": f"#ip{i}"},
                "children": [],
            }
            for i in range(1, host_count + 1)
        ]
        prefix_group = {
            "kind": "group",
            "name": "shared-net",
            "url": "#prefix",
            "ip_ref": {
                "str": "198.18.182.0/24",
                "url": "#prefix",
                "type": "Prefix",
                "ct": 11,
                "pk": 182,
            },
            "prefix_display_cidr": "198.18.182.0/24",
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
            (prefix_node.get("ip_ref") or {}).get("str"), "198.18.182.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), host_count)
        self.assertEqual(result[0]["types"][0]["diff_summary"]["both"], host_count)

    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    def test_build_addr_diff_intersection_tree_keeps_hosts_when_prefix_incomplete(
        self, _supports, build_nodes_fn
    ):
        shared_leaf = {
            "kind": "leaf",
            "name": "host-1",
            "url": "#ip1",
            "ip_ref": {"str": "198.19.169.1/32", "url": "#ip1"},
            "children": [],
        }
        only_b_leaf = {
            "kind": "leaf",
            "name": "host-2",
            "url": "#ip2",
            "ip_ref": {"str": "198.19.169.2/32", "url": "#ip2"},
            "children": [],
        }
        prefix_group = {
            "kind": "group",
            "name": "net",
            "url": "#prefix",
            "ip_ref": {
                "str": "198.19.169.0/24",
                "url": "#prefix",
                "type": "Prefix",
                "ct": 11,
                "pk": 24,
            },
            "prefix_display_cidr": "198.19.169.0/24",
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
            (prefix_node.get("ip_ref") or {}).get("str"), "198.19.169.0/24"
        )
        self.assertEqual(prefix_node.get("kind"), "group")
        self.assertEqual(len(prefix_node.get("children") or []), 1)
        host = prefix_node["children"][0]
        self.assertTrue(host.get("diff_intersection_pair"))
        self.assertEqual((host.get("ip_ref") or {}).get("str"), "198.19.169.1/32")
        self.assertEqual(host.get("kind"), "leaf")

    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._build_addr_tree_nodes")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._object_supports_addr_analysis",
        return_value=True,
    )
    @patch("netbox_nsm.analyzers.ip_analyzer.addr_analysis_utils._lookup_containing_prefix_for_intersection_node")
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
        p24.prefix = ipaddress.ip_network("198.18.182.0/24")
        p24.__str__ = MagicMock(return_value="198.18.182.0/24")
        p24.get_absolute_url.return_value = "/ipam/prefixes/182/"
        lookup_prefix_fn.return_value = p24

        shared_leaves = [
            {
                "kind": "leaf",
                "name": f"host-{i}",
                "url": f"#ip{i}",
                "ip_ref": {"str": f"198.18.182.{i}/32", "url": f"#ip{i}"},
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
            (prefix_node.get("ip_ref") or {}).get("str"), "198.18.182.0/24"
        )
        self.assertEqual(len(prefix_node.get("children") or []), 2)
        child_keys = {
            (child.get("ip_ref") or {}).get("str")
            for child in prefix_node["children"]
        }
        self.assertEqual(
            child_keys, {"198.18.182.1/32", "198.18.182.10/32"}
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
                    "diff_name_a": "bench-ip-001",
                    "diff_name_b": "server-prod",
                    "diff_url_a": "#a",
                    "diff_url_b": "#b",
                    "fund_tooltip": "Same IP, different names (A: bench-ip-001; B: server-prod)",
                    "children": [],
                },
                "depth": 1,
                "prefix": "src",
            },
        )
        self.assertIn("nsm-addr-diff-fund-row", html)
        self.assertIn("nsm-addr-fund", html)
        self.assertIn("Name conflict", html)
        self.assertIn("nsm-addr-diff-leaf--fund", html)
        self.assertIn("nsm-addr-diff-fund-network", html)
        self.assertIn("10.1.1.1/32", html)
        self.assertIn("bench-ip-001", html)
        self.assertIn("server-prod", html)
        self.assertNotIn("nsm-addr-ip", html)
        self.assertNotIn("→", html)

    def test_addr_tree_node_renders_diff_fund_row_filters_ip_like_name(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "h-10.112.134.44",
                    "url": "#",
                    "ip_ref": {"str": "10.112.134.44/24", "url": "#"},
                    "diff_status": "both",
                    "diff_fund": True,
                    "diff_name_a": "10.112.134.44/24",
                    "diff_name_b": "h-10.112.134.44",
                    "diff_url_a": "#a",
                    "diff_url_b": "#b",
                    "fund_tooltip": "Same IP, different names",
                    "children": [],
                },
                "depth": 1,
                "prefix": "src",
            },
        )
        self.assertIn("nsm-addr-diff-fund-row", html)
        self.assertEqual(html.count("10.112.134.44/24"), 1)
        self.assertIn("h-10.112.134.44", html)
        self.assertNotIn("nsm-ipa-diff-name-sep", html)
        self.assertNotIn("nsm-addr-ip", html)
        self.assertNotIn("→", html)

    def test_diff_mode_build_ip_analysis_payload_includes_object_tree(self):
        from netbox_nsm.analyzers.ip_analyzer.ip_analysis_service import build_ip_analysis_payload

        addr_analysis = [
            {
                "field_slug": "diff",
                "types": [
                    {
                        "nodes": [
                            {
                                "kind": "group",
                                "name": "Only in A",
                                "url": "#",
                                "diff_group": "only-a",
                                "children": [
                                    {
                                        "kind": "leaf",
                                        "name": "host-a",
                                        "url": "#",
                                        "ip_ref": {"str": "10.0.0.1/32", "url": "#"},
                                        "prefix_display_cidr": "10.0.0.1/32",
                                        "diff_status": "only_a",
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                        "leaf_count": 1,
                    }
                ],
            }
        ]
        payload = build_ip_analysis_payload(
            addr_analysis=addr_analysis,
            selections=[],
            unsupported=[],
            mode="diff",
            include_structured_data=True,
        )
        self.assertTrue(payload.get("object_tree"))
        self.assertEqual(len(payload["object_tree"]), 1)
        self.assertEqual(payload["object_tree"][0]["diff_group"], "only-a")

        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_intersection_flat_node.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "bench-ip-001",
                    "url": "#",
                    "ip_ref": {"str": "10.1.1.1/32", "url": "#"},
                    "diff_status": "both",
                    "diff_fund": True,
                    "diff_intersection_pair": True,
                    "diff_name_a": "bench-ip-001",
                    "diff_name_b": "server-prod",
                    "diff_url_a": "#a",
                    "diff_url_b": "#b",
                    "children": [],
                },
            },
        )
        self.assertIn("nsm-addr-diff-fund-row", html)
        self.assertIn("10.1.1.1/32", html)
        self.assertNotIn("nsm-addr-ip", html)
        self.assertNotIn("→", html)


