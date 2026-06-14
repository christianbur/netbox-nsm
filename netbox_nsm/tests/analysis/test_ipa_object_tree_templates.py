"""Template integration tests for IPA object tree."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analysis.addr_analysis_utils import (
    _build_ipa_cell_object_tree,
    _flatten_ipa_object_tree_copy_lines,
    _ordered_ipam_stats,
    _resolve_summary_type_counts,
)

class IpaObjectTreeTemplateIntegrationTests(SimpleTestCase):
    _OBJECT_TREE_FIXTURE = [
        {
            "name": "n-10.1.0.0/16",
            "url": "/n/16/",
            "ct": "10",
            "pk": "16",
            "kind": "leaf",
            "cell_groups": [{"name": "g-10.0.0.0/8", "url": "/g/8/"}],
            "children": [],
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

    def _render_object_tree_html(self):
        from django.template.loader import render_to_string

        return render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": self._OBJECT_TREE_FIXTURE},
        )

    def test_ipa_nested_leaf_renders_cell_pill(self):
        html = self._render_object_tree_html()
        child_name_pos = html.index("n-10.1.0.0/16")
        child_leaf_start = html.rfind('<div class="nsm-addr-leaf', 0, child_name_pos)
        child_leaf_end = html.index("</div>", child_name_pos)
        child_leaf_html = html[child_leaf_start:child_leaf_end]
        self.assertIn("nsm-ipa-cell-pill--address", child_leaf_html)

    def test_cell_group_labels_render_multi_group_orange(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-addr-10-112-148-0-28",
                "url": "/a/28/",
                "ct": "10",
                "pk": "28",
                "kind": "leaf",
                "cell_groups": [
                    {"name": "dm-grp-030", "url": "/g/30/"},
                    {"name": "dm-grp-015", "url": "/g/15/"},
                ],
                "cell_groups_multi": True,
                "prefix_display_cidr": "10.112.148.0/28",
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": [],
                "object_tree": object_tree,
                "summary_type_counts": _resolve_summary_type_counts([], object_tree),
            },
        )
        self.assertIn("nsm-ipa-cell-pill--multi", html)
        self.assertNotIn("nsm-ipa-cell-pill--address nsm-ipa-cell-pill--multi", html)
        self.assertIn("nsm-addr-group-duplicate-summary", html)
        self.assertIn("Duplicates: 1", html)
        self.assertEqual(html.count("nsm-ipa-cell-pill--multi"), 1)
        self.assertEqual(html.count("ADDRESS_GROUP"), 1)
        self.assertIn("dm-grp-030", html)
        self.assertIn("dm-grp-015", html)
        self.assertIn("nsm-ipa-cell-pill-entry", html)
        self.assertIn("nsm-ipa-cell-pill-body--stack", html)
        self.assertNotIn("nsm-ipa-cell-pill-sep", html)
        self.assertNotIn("nsm-ipa-cell-pill--group-none", html)
        self.assertNotIn(">none<", html)

    def test_cell_group_labels_omit_pill_for_ungrouped_address(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-addr-10-112-200-0-24",
                "url": "/a/200/",
                "ct": "10",
                "pk": "200",
                "kind": "leaf",
                "cell_groups_none": True,
                "prefix_display_cidr": "10.112.200.0/24",
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertNotIn("nsm-ipa-cell-pill--group", html)
        self.assertNotIn("nsm-ipa-cell-pill--group-none", html)
        self.assertNotIn("nsm-ipa-cell-pill-link--none", html)
        self.assertNotIn("ADDRESS_GROUP", html)
        self.assertNotIn(">none<", html)
        self.assertNotIn("nsm-ipa-cell-pill--multi", html)

    def test_cell_group_labels_append_none_for_cell_direct_multi_group(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analysis.ipa_object_tree import _apply_node_cell_groups

        node = {
            "name": "dm-addr-10-112-134-0-24",
            "url": "/a/134/",
            "ct": "10",
            "pk": "134",
            "kind": "leaf",
            "is_cell_direct": True,
            "prefix_display_cidr": "10.112.134.0/24",
            "children": [],
        }
        _apply_node_cell_groups(
            node,
            [
                {"name": "dm-grp-001", "url": "/g/1/"},
                {"name": "dm-grp-014", "url": "/g/14/"},
            ],
            is_cell_direct=True,
        )
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": [node]},
        )
        self.assertIn("nsm-ipa-cell-pill--multi", html)
        self.assertNotIn("nsm-ipa-cell-pill--address nsm-ipa-cell-pill--multi", html)
        self.assertIn("dm-grp-001", html)
        self.assertIn("dm-grp-014", html)
        self.assertIn(">none<", html)
        self.assertIn("nsm-ipa-cell-pill-link--none", html)

    def test_cell_address_pill_orange_only_for_multiple_names(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-addr-10-112-139-0-24",
                "url": "/a/139/",
                "ct": "10",
                "pk": "139",
                "kind": "leaf",
                "cell_groups": [
                    {"name": "dm-grp-001", "url": "/g/1/"},
                    {"name": "dm-grp-011", "url": "/g/11/"},
                ],
                "cell_groups_multi": True,
                "prefix_display_cidr": "10.112.139.0/24",
                "children": [],
            },
            {
                "name": "dm-addr-10-112-139-0-24",
                "url": "/a/139/",
                "ct": "10",
                "pk": "139",
                "kind": "leaf",
                "cell_addresses": [
                    {"name": "dm-addr-10-112-139-0-24", "url": "/a/139/"},
                    {"name": "diff-addr-10-112-139-0-24", "url": "/a/239/"},
                ],
                "cell_addresses_multi": True,
                "cell_groups_multi": True,
                "prefix_display_cidr": "10.112.139.0/24",
                "children": [],
            },
        ]
        html_multi_groups_only = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": [object_tree[0]]},
        )
        html_multi_addresses = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": [object_tree[1]]},
        )
        self.assertNotIn("nsm-ipa-cell-pill--address nsm-ipa-cell-pill--multi", html_multi_groups_only)
        self.assertIn("nsm-ipa-cell-pill--group nsm-ipa-cell-pill--multi", html_multi_groups_only)
        self.assertIn("nsm-ipa-cell-pill--address nsm-ipa-cell-pill--multi", html_multi_addresses)
        self.assertIn("nsm-ipa-cell-pill-entry", html_multi_groups_only)
        self.assertIn("nsm-ipa-cell-pill-body--stack", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-cell-pill-sep", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-duplicate-indicator", html_multi_addresses)
        self.assertNotIn("mdi-alert-circle-outline", html_multi_addresses)
        self.assertIn('title="Multiple address names share this network in the rule cell"', html_multi_addresses)
        self.assertIn("diff-addr-10-112-139-0-24", html_multi_addresses)
        self.assertIn("nsm-ipa-cell-pill-entry", html_multi_addresses)
        self.assertIn("nsm-ipa-cell-pill-body--stack", html_multi_addresses)
        self.assertNotIn("nsm-ipa-cell-pill-sep", html_multi_addresses)

    def test_inactive_object_renders_italic_and_status_icon(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": [],
                "object_tree": [
                    {
                        "name": "old-addr",
                        "url": "/a/9/",
                        "ct": "10",
                        "pk": "9",
                        "kind": "leaf",
                        "status": "deprecated",
                        "cell_groups": [
                            {
                                "name": "old-grp",
                                "url": "/g/9/",
                                "status": "reserved",
                            }
                        ],
                        "prefix_display_cidr": "10.112.200.0/24",
                        "children": [],
                    }
                ],
            },
        )
        self.assertIn("nsm-ipa-cell-pill-link--inactive", html)
        self.assertIn("mdi-information-outline", html)
        self.assertIn("nsm-object-status-icon--deprecated", html)
        self.assertIn("nsm-object-status-icon--reserved", html)

    def test_cell_pill_links_expose_full_name_title(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {
                "addr_analysis": [],
                "object_tree": [
                    {
                        "name": "diff-test-10-112-134-0-24",
                        "url": "/a/134/",
                        "ct": "10",
                        "pk": "134",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "cell_addresses": [
                            {"name": "diff-test-10-112-134-0-24", "url": "/a/134/"},
                            {"name": "dm-addr-10-112-134-0-24", "url": "/a/234/"},
                        ],
                        "cell_addresses_multi": True,
                        "cell_groups": [
                            {"name": "dm-grp-001", "url": "/g/1/"},
                            {"name": "dm-grp-014", "url": "/g/14/"},
                            {"name": "none", "url": "", "is_none": True},
                        ],
                        "cell_groups_multi": True,
                        "prefix_display_cidr": "10.112.134.0/24",
                        "children": [],
                    }
                ],
            },
        )
        self.assertIn('title="diff-test-10-112-134-0-24"', html)
        self.assertIn('title="dm-addr-10-112-134-0-24"', html)
        self.assertIn('title="dm-grp-001"', html)
        self.assertIn('title="dm-grp-014"', html)
        self.assertNotIn('title="none"', html)

    def test_ipam_drilldown_summary_renders_parent_object_meta(self):
        from django.template.loader import render_to_string

        cell_html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "name": "dm-addr-10-112-129-0-24",
                        "url": "/a/1/",
                        "ct": "10",
                        "pk": "1",
                        "kind": "group",
                        "is_cell_direct": True,
                        "prefix_display_cidr": "10.112.129.0/24",
                        "node_role": "nsm_prefix",
                        "ipa_drilldown_meta": {
                            "name": "dm-addr-10-112-129-0-24",
                            "url": "/a/1/",
                            "tenant_name": "Dunder Mifflin",
                            "tenant_url": "/tenancy/tenants/1/",
                            "count_subnets": 2,
                            "count_ranges": 1,
                            "count_ips": 8,
                        },
                        "children": [],
                    }
                ],
                "depth": 1,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        drilldown_html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "name": "10.112.129.0/24",
                        "url": "/ipam/prefixes/1/",
                        "kind": "group",
                        "layer": "ipam_prefix",
                        "ipam_stats": [{"label": "Prefixes", "count": 2, "url": "#"}],
                        "children": [],
                    }
                ],
                "depth": 2,
                "prefix": "ipa",
                "show_copy": False,
                "ipa_cell_pill": False,
            },
        )
        self.assertIn("nsm-ipa-cell-object-row", cell_html)
        self.assertIn("nsm-ipa-cell-object-summary--has-info", cell_html)
        self.assertIn("nsm-ipa-drilldown-meta--info", cell_html)
        self.assertIn("nsm-ipa-drilldown-meta-info-stat", cell_html)
        self.assertIn("Info", cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta-pill--name", cell_html)
        self.assertIn("dm-addr-10-112-129-0-24", cell_html)
        self.assertIn("Dunder Mifflin", cell_html)
        self.assertIn('class="nsm-ipa-drilldown-meta-info-stat-val">2<', cell_html)
        self.assertIn('class="nsm-ipa-drilldown-meta-info-stat-val">1<', cell_html)
        self.assertIn('class="nsm-ipa-drilldown-meta-info-stat-val">8<', cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta--info", drilldown_html)
        self.assertIn("10.112.129.0/24", drilldown_html)

    def test_ipa_cell_direct_leaf_prefix_renders_info_expand(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analysis.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
                    {
                        "name": "dm-addr-10-112-128-0-28",
                        "url": "/a/28/",
                        "ct": "10",
                        "pk": "28",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "prefix_display_cidr": "10.112.128.0/28",
                        "node_role": "nsm_prefix",
                        "ip_ref": {
                            "str": "10.112.128.0/28",
                            "url": "/ipam/prefixes/28/",
                            "type": "Prefix",
                        },
                        "ipa_drilldown_meta": {
                            "name": "dm-addr-10-112-128-0-28",
                            "url": "/a/28/",
                            "tenant_name": "Dunder Mifflin",
                            "tenant_url": "/tenancy/tenants/1/",
                            "count_subnets": 0,
                            "count_ranges": 0,
                            "count_ips": 4,
                        },
                        "children": [],
                    }
                ]
        _mark_ipa_cell_open_by_default(nodes)
        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": nodes,
                "depth": 1,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertIn("nsm-ipa-object-node", html)
        self.assertIn("nsm-addr-leaf-summary", html)
        self.assertIn("nsm-ipa-cell-object-summary--has-info", html)
        self.assertIn("nsm-ipa-drilldown-meta--info", html)
        self.assertIn("10.112.128.0/28", html)
        self.assertIn("Dunder Mifflin", html)
        self.assertRegex(html, r'<details class="[^"]*nsm-ipa-object-node[^"]*" open>')
        self.assertNotRegex(
            html,
            r'<div class="nsm-addr-leaf[^"]*">\s*<span class="nsm-ipa-cell-object-row"',
        )

    def test_ipa_cell_direct_nested_host_renders_parent_details_open(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analysis.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
            {
                "name": "dm-addr-10-112-134-0-24",
                "url": "/a/13/",
                "ct": "10",
                "pk": "13",
                "kind": "group",
                "prefix_display_cidr": "10.112.134.0/24",
                "children": [
                    {
                        "name": "h-10.112.134.44",
                        "url": "/a/44/",
                        "ct": "10",
                        "pk": "44",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "prefix_display_cidr": "10.112.134.44/32",
                        "children": [],
                    }
                ],
            }
        ]
        _mark_ipa_cell_open_by_default(nodes)
        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": nodes,
                "depth": 0,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertIn("nsm-ipa-cell-children", html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertRegex(html, r'<details class="[^"]*nsm-ipa-object-node[^"]*" open>')

    def test_ipa_cell_direct_drilldown_renders_open_by_default(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analysis.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
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
            }
        ]
        _mark_ipa_cell_open_by_default(nodes)
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": nodes},
        )
        self.assertIn("nsm-ipa-addr-drilldown", html)
        self.assertRegex(html, r'<details class="[^"]*nsm-ipa-object-node[^"]*" open>')
    def test_ipa_cell_direct_host_leaf_without_meta_stays_plain(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "name": "h-10.112.128.44",
                        "url": "/a/44/",
                        "ct": "10",
                        "pk": "44",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "prefix_display_cidr": "10.112.128.44/32",
                        "node_role": "nsm_host",
                        "children": [],
                    }
                ],
                "depth": 1,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertIn('<div class="nsm-addr-leaf', html)
        self.assertNotIn("nsm-addr-leaf-summary", html)
        self.assertNotIn("nsm-ipa-cell-object-summary--has-info", html)

    def test_ipa_cell_direct_summary_shows_cidr_and_typed_pills(self):
        html = self._render_object_tree_html()
        leaf_summary_start = html.index("nsm-ipa-object-node--cell-direct")
        leaf_summary_end = html.index("</summary>", leaf_summary_start)
        leaf_summary_html = html[leaf_summary_start:leaf_summary_end]
        self.assertIn("nsm-ipa-cell-cidr", leaf_summary_html)
        self.assertIn("10.128.143.0/24", leaf_summary_html)
        self.assertIn("nsm-ipa-cell-pill--address", leaf_summary_html)
        self.assertIn("bench-ip-0014328", leaf_summary_html)
        self.assertIn("ADDRESS", leaf_summary_html)
        self.assertLess(
            leaf_summary_html.index("nsm-ipa-cell-cidr"),
            leaf_summary_html.index("nsm-ipa-cell-pill--address"),
        )
        pill_start = leaf_summary_html.index("nsm-ipa-cell-pill--address")
        pill_end = leaf_summary_html.index("</span>", pill_start)
        pill_html = leaf_summary_html[pill_start:pill_end]
        self.assertIn("nsm-ipa-cell-pill-body", html)
        self.assertNotIn("→", leaf_summary_html)

    def test_ipa_cell_direct_host_leaf_subnet_containment_renders_parent_pill(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "name": "h-10.112.134.44",
                        "url": "/a/44/",
                        "ct": "10",
                        "pk": "44",
                        "kind": "leaf",
                        "is_cell_direct": True,
                        "prefix_display_cidr": "10.112.134.44/32",
                        "subnet_contained_in": "10.112.134.0/24",
                        "subnet_contained_in_name": "dm-addr-10-112-134-0-24",
                        "subnet_contained_in_url": "/a/13/",
                        "subnet_containment_display_net": "10.112.134.44",
                        "children": [],
                    }
                ],
                "depth": 1,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertIn('<div class="nsm-addr-leaf', html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertIn("nsm-ipa-cell-pill--parent", html)
        self.assertIn("nsm-ipa-cell-pill--parent", html)
        self.assertIn("10.112.134.0/24", html)
        self.assertIn('href="/a/13/"', html)
        self.assertNotIn("nsm-ipa-cell-object-leaf--has-info", html)
        self.assertNotIn("nsm-ipa-drilldown-meta--warning", html)
        self.assertNotIn("10.112.134.44 in 10.112.134.0/24", html)
        parent_pos = html.index("nsm-ipa-cell-pill--parent")
        address_pos = html.index("nsm-ipa-cell-pill--address")
        self.assertLess(address_pos, parent_pos)
        self.assertIn('<div class="nsm-ipa-cell-object-row-main">', html)

    def test_ipa_drilldown_placeholder_excludes_cell_pill(self):
        html = self._render_object_tree_html()
        drilldown_pos = html.index("nsm-ipa-addr-drilldown")
        self.assertNotIn("nsm-ipa-cell-pill", html[drilldown_pos:])

    def test_ipa_drilldown_fragment_omits_cell_pill_when_disabled(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "kind": "leaf",
                        "name": "bench-ip-drill",
                        "url": "/a/1/",
                        "children": [],
                    }
                ],
                "depth": 1,
                "prefix": "ipa",
                "show_copy": False,
                "ipa_cell_pill": False,
            },
        )
        self.assertIn("bench-ip-drill", html)
        self.assertNotIn("nsm-ipa-cell-pill", html)

    def test_diff_in_some_summary_renders_present_label_lines(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "kind": "group",
                        "name": "In some",
                        "url": "#",
                        "diff_group": "in-some",
                        "diff_present_labels": [
                            "Rule bench-rule-00038 (38) / destination",
                            "Rule bench-rule-03250 (3250) / destination",
                        ],
                        "children": [
                            {
                                "kind": "leaf",
                                "name": "bench-ip-0046354",
                                "url": "/a/1/",
                                "ip_ref": {"str": "10.129.207.55/32", "url": "#"},
                                "diff_status": "in_some",
                                "children": [],
                            }
                        ],
                    }
                ],
                "depth": 0,
                "prefix": "diff-ipam",
                "show_copy": False,
            },
        )
        self.assertIn("nsm-addr-diff-in-some-head", html)
        self.assertIn("− Rule bench-rule-00038 (38) / destination", html)
        self.assertIn("− Rule bench-rule-03250 (3250) / destination", html)
        self.assertNotIn("In some: Rule", html)

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
        self.assertNotIn("nsm-ipa-duplicate-indicator", html)
        self.assertNotIn("mdi-alert-circle-outline", html)
        self.assertIn('title="Duplicate cell entry — the same object is listed more than once in the rule cell"', html)
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
        self.assertIn("nsm-ipa-cell-pill--parent", html)
        self.assertNotIn("mdi-alert-circle-outline", html)
        self.assertNotIn("nsm-ipa-duplicate-indicator", html)
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertNotIn("nsm-ipa-expanded-warning--subnet", html)
        self.assertIn('title="warn duplicate → 10.0.0.0/8"', html)
        self.assertIn("nsm-ipa-cell-type", html)
        self.assertIn("ADDRESS", html)
        self.assertNotIn("nsm-addr-ip", html)
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

    def test_nested_group_member_renders_expandable_drilldown(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-addr-10-112-137-0-24",
                "url": "/a/2/",
                "ct": "10",
                "pk": "2",
                "kind": "group",
                "cell_groups": [{"name": "dm-grp-005", "url": "/g/5/"}],
                "ip_ref": {
                    "str": "10.112.137.0/24",
                    "url": "/ipam/prefixes/2/",
                    "type": "Prefix",
                },
                "prefix_display_cidr": "10.112.137.0/24",
                "addr_drilldown_lazy": True,
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("dm-addr-10-112-137-0-24", html)
        self.assertIn("10.112.137.0/24", html)
        self.assertIn("ADDRESS", html)
        self.assertIn("ADDRESS_GROUP", html)
        self.assertIn("dm-grp-005", html)
        self.assertIn('data-lazy-ct="10"', html)
        self.assertIn('data-lazy-pk="2"', html)
        self.assertIn("nsm-ipa-addr-drilldown", html)

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
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertIn('title="warn duplicate → 10.0.0.0/8 (g-10.0.0.0/8)"', html)
        self.assertIn("nsm-ipa-addr-drilldown", html)

    def test_object_tree_expanded_group_duplicate_warning(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-addr-10-112-148-0-28",
                "url": "/a/28/",
                "ct": "10",
                "pk": "28",
                "kind": "group",
                "cell_groups": [
                    {"name": "dm-grp-030", "url": "/g/30/"},
                    {"name": "dm-grp-015", "url": "/g/15/"},
                ],
                "cell_groups_multi": True,
                "prefix_display_cidr": "10.112.148.0/28",
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
        self.assertNotIn("nsm-ipa-duplicate-indicator", html)
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertIn('title="Address belongs to more than one address group in this cell"', html)

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
        self.assertNotIn("nsm-ipa-duplicate-indicator", html)
        self.assertNotIn("mdi-alert-circle-outline", html)
        self.assertIn("nsm-ipa-object-node--doppelt-warning", html)
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertIn('title="Duplicate cell entry — the same object is listed more than once in the rule cell"', html)
        self.assertNotIn("mdi-exclamation-thick", html)

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

    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_drilldown_has_visible_content", return_value=True)
    @patch("netbox_nsm.analysis.ipa_object_tree._ipa_object_has_addr_drilldown", return_value=True)
    @patch("netbox_nsm.analysis.addr_analysis_utils._build_ipa_object_tree_node")
    def test_build_ipa_cell_object_tree_marks_addr_drilldown_lazy(
        self, build_node_fn, drilldown_fn, _visible_fn
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
