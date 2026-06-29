"""Template integration tests for IPA object tree."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip.addr_analysis_utils import (
    _build_ipa_cell_object_tree,
    _flatten_ipa_object_tree_copy_lines,
    _ordered_ipam_stats,
    _resolve_summary_type_counts,
)
from netbox_nsm.analyzers.ip.ipa_object_tree import _attach_ipa_cell_display_hints

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
            "ip_ref": {"str": "198.18.143.0/24", "url": "#"},
            "prefix_display_cidr": "198.18.143.0/24",
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

    def test_ipa_nested_leaf_renders_cell_object_link(self):
        html = self._render_object_tree_html()
        child_name_pos = html.index("n-10.1.0.0/16")
        child_row_start = html.rfind('<tr class="nsm-ipa-cell-tree-row', 0, child_name_pos)
        child_row_end = html.index("</tr>", child_name_pos)
        child_row_html = html[child_row_start:child_row_end]
        self.assertIn("nsm-addr-obj-link", child_row_html)
        self.assertIn("nsm-ipa-object-node--cell-indirect", child_row_html)
        self.assertNotIn("nsm-ipa-object-node--cell-direct", child_row_html)
        self.assertNotIn("nsm-ipa-cell-pill", child_row_html)

    def test_diff_cell_tree_rows_keep_filterable_classes(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "In all",
                "kind": "group",
                "diff_group": "in-all",
                "children": [
                    {
                        "name": "bench-ip-0000001",
                        "url": "/a/1/",
                        "kind": "leaf",
                        "diff_status": "both",
                        "diff_suppress_status": True,
                        "prefix_display_cidr": "198.18.0.1/32",
                        "children": [],
                    }
                ],
            },
            {
                "name": "Only in A",
                "kind": "group",
                "diff_group": "only-a",
                "children": [
                    {
                        "name": "bench-ip-0000002",
                        "url": "/a/2/",
                        "kind": "leaf",
                        "diff_status": "only_a",
                        "prefix_display_cidr": "198.18.0.2/32",
                        "subnet_contained_in": "198.18.0.0/24",
                        "children": [],
                    }
                ],
            },
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )

        self.assertIn("nsm-addr-diff-group--in-all", html)
        self.assertIn("nsm-addr-diff-group--only-a", html)
        self.assertIn("nsm-addr-diff-leaf--only_a", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)

    def test_network_cell_renders_explain_tooltip(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0000000",
                    "url": "/a/1/",
                    "ct": "10",
                    "pk": "1",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.0.1/32",
                    "ipa_explain_title": "Why: direct in rule cell | group member: bench-grp-00000",
                    "children": [],
                },
                "depth": 0,
            },
        )

        self.assertIn('title="Why: direct in rule cell | group member: bench-grp-00000"', html)

    def test_group_coverage_panel_renders_group_states(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_group_coverage_panel.html",
            {
                "group_coverage": {
                    "summary": {
                        "total": 2,
                        "visible": 1,
                        "membership": 1,
                        "missing": 0,
                    },
                    "groups": [
                        {
                            "name": "bench-grp-00001",
                            "url": "/g/1/",
                            "state": "visible",
                            "state_label": "visible row",
                            "member_count": 101,
                            "anchor_cidr": "198.18.1.0/24",
                        },
                        {
                            "name": "bench-grp-00002",
                            "url": "/g/2/",
                            "state": "membership",
                            "state_label": "merged into member row",
                            "member_count": 101,
                            "anchor_cidr": "198.18.2.0/24",
                        },
                    ],
                }
            },
        )

        self.assertIn("Group coverage", html)
        self.assertIn("Total: 2", html)
        self.assertIn("bench-grp-00001", html)
        self.assertIn("merged into member row", html)

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
        self.assertIn("nsm-ipa-cell-tree-groups--multi", html)
        self.assertNotIn("nsm-ipa-cell-pill--multi", html)
        self.assertIn("nsm-addr-group-duplicate-summary", html)
        self.assertIn("Duplicates: 1", html)
        self.assertEqual(html.count("nsm-ipa-cell-tree-groups--multi"), 1)
        self.assertNotIn("ADDRESS_GROUP", html)
        self.assertIn("dm-grp-030", html)
        self.assertIn("dm-grp-015", html)
        self.assertIn("nsm-ipa-cell-tree-group-entry", html)
        self.assertNotIn("nsm-ipa-cell-pill-body--stack", html)
        self.assertNotIn("nsm-ipa-cell-pill-sep", html)
        self.assertNotIn("nsm-ipa-cell-pill--group-none", html)
        self.assertNotIn(">none<", html)

    def test_address_group_row_renders_address_group_type_label(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "bench-grp-00346",
                "url": "/g/500/",
                "ct": "10",
                "pk": "500",
                "kind": "group",
                "node_role": "nsm_group",
                "is_cell_direct": True,
                "in_cell": True,
                "cell_pill_group": True,
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("bench-grp-00346", html)
        self.assertNotIn("ADDRESS_GROUP", html)
        self.assertNotIn("nsm-ipa-cell-pill--self-group", html)
        address_group_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address-group">'
        )
        address_group_col_end = html.index("</td>", address_group_col_start)
        self.assertIn("bench-grp-00346", html[address_group_col_start:address_group_col_end])
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        self.assertIn("—", html[address_col_start:address_col_end])

    def test_collapsed_group_row_renders_anchor_member_in_address_column(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "bench-grp-00346",
                "url": "/g/500/",
                "ct": "10",
                "pk": "500",
                "kind": "group",
                "node_role": "nsm_group",
                "is_cell_direct": True,
                "in_cell": True,
                "cell_pill_group": True,
                "prefix_display_cidr": "198.19.90.0/24",
                "cell_group_anchor_address": {
                    "name": "bench-net-00346",
                    "url": "/plugins/netbox-nsm/objects/nsm_address/347/",
                },
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {"node": object_tree[0], "depth": 0},
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn("bench-net-00346", address_col_html)
        self.assertNotIn("—", address_col_html)

    def test_group_member_renders_address_name_via_cell_groups(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0000099",
                    "url": "/a/99/",
                    "ct": "10",
                    "pk": "99",
                    "kind": "leaf",
                    "node_role": "nsm_host",
                    "prefix_display_cidr": "198.18.0.99/32",
                    "cell_groups": [
                        {
                            "name": "bench-grp-00098",
                            "url": "/g/98/",
                        }
                    ],
                    "children": [],
                },
                "depth": 0,
            },
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn("bench-ip-0000099", address_col_html)
        self.assertNotIn("—", address_col_html)

    def test_address_group_row_membership_excludes_self_duplicate(self):
        from django.template.loader import render_to_string

        object_tree = [
            {
                "name": "dm-grp-inner",
                "url": "/g/2/",
                "ct": "10",
                "pk": "2",
                "kind": "group",
                "node_role": "nsm_group",
                "is_cell_direct": True,
                "in_cell": True,
                "cell_pill_group": True,
                "cell_groups": [{"name": "dm-grp-outer", "url": "/g/1/"}],
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("dm-grp-inner", html)
        self.assertIn("dm-grp-outer", html)
        groups_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address-group">'
        )
        groups_col_end = html.index("</td>", groups_col_start)
        groups_col_html = html[groups_col_start:groups_col_end]
        self.assertIn("dm-grp-inner", groups_col_html)
        self.assertIn("dm-grp-outer", groups_col_html)
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        self.assertIn("—", html[address_col_start:address_col_end])

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
        self.assertNotIn("nsm-ipa-cell-tree-groups", html)
        self.assertNotIn("nsm-ipa-cell-pill--group", html)
        self.assertNotIn("nsm-ipa-cell-pill--group-none", html)
        self.assertNotIn("nsm-ipa-cell-pill-link--none", html)
        self.assertNotIn("ADDRESS_GROUP", html)
        self.assertNotIn(">none<", html)
        self.assertNotIn("nsm-ipa-cell-tree-groups--multi", html)

    def test_cell_group_labels_append_none_for_cell_direct_multi_group(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import _apply_node_cell_groups

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
        self.assertIn("nsm-ipa-cell-tree-groups--multi", html)
        self.assertNotIn("nsm-ipa-cell-pill--multi", html)
        self.assertIn("dm-grp-001", html)
        self.assertIn("dm-grp-014", html)
        self.assertIn(">none<", html)
        self.assertNotIn("nsm-ipa-cell-pill-link--none", html)

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
        compact_tree = [dict(object_tree[1])]
        _attach_ipa_cell_display_hints(compact_tree)
        html_compact_addresses = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": compact_tree},
        )
        self.assertIn("nsm-ipa-cell-tree-groups--multi", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-cell-tree-object--multi", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-cell-tree-address--multi", html_multi_groups_only)
        self.assertIn("nsm-ipa-cell-tree-address--multi", html_multi_addresses)
        self.assertIn("nsm-ipa-cell-tree-group-entry", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-cell-pill-body--stack", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-cell-pill-sep", html_multi_groups_only)
        self.assertNotIn("nsm-ipa-duplicate-indicator", html_multi_addresses)
        self.assertNotIn("mdi-alert-circle-outline", html_multi_addresses)
        self.assertIn('title="Multiple address names share this network in the rule cell"', html_multi_addresses)
        self.assertIn("diff-addr-10-112-139-0-24", html_multi_addresses)
        merge_multi_start = html_multi_addresses.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--merge">'
        )
        merge_multi_end = html_multi_addresses.index("</td>", merge_multi_start)
        merge_multi_html = html_multi_addresses[merge_multi_start:merge_multi_end]
        self.assertIn("nsm-ipa-cell-merge", merge_multi_html)
        self.assertIn("merge", merge_multi_html)
        self.assertNotIn("nsm-ipa-cell-secondary-hint--aliases", html_compact_addresses)
        self.assertNotIn("nsm-ipa-cell-secondary-expand-summary", html_compact_addresses)
        self.assertIn("nsm-ipa-cell-tree-address--multi", html_compact_addresses)
        address_col_start = html_compact_addresses.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html_compact_addresses.index("</td>", address_col_start)
        address_col_html = html_compact_addresses[address_col_start:address_col_end]
        us_col_start = html_compact_addresses.index("nsm-ipa-cell-tree-col--us")
        us_col_end = html_compact_addresses.index("</td>", us_col_start)
        us_col_html = html_compact_addresses[us_col_start:us_col_end]
        self.assertNotIn("nsm-ipa-cell-secondary-hint--aliases", address_col_html)
        self.assertIn("nsm-ipa-cell-tree-address--multi", address_col_html)
        self.assertIn("diff-addr-10-112-139-0-24", address_col_html)
        self.assertNotIn("nsm-ipa-cell-tree-address--compact", address_col_html)
        self.assertNotIn("nsm-ipa-cell-secondary-hint--aliases", us_col_html)
        self.assertNotIn("diff-addr-10-112-139-0-24", us_col_html)
        merge_start = html_compact_addresses.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--merge">'
        )
        merge_end = html_compact_addresses.index("</td>", merge_start)
        merge_col_html = html_compact_addresses[merge_start:merge_end]
        self.assertIn("nsm-ipa-cell-merge", merge_col_html)
        self.assertIn("merge", merge_col_html)

    def test_multi_address_peers_render_vertically_in_address_column(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import _attach_ipa_cell_display_hints

        nodes = [
            {
                "name": "bench-ip-0000012",
                "url": "/a/12/",
                "ct": "10",
                "pk": "12",
                "kind": "leaf",
                "is_cell_direct": True,
                "cell_addresses_multi": True,
                "cell_addresses": [
                    {"name": "bench-ip-0000012", "url": "/a/12/"},
                    {"name": "bench-dup-0000012", "url": "/a/13/"},
                    {"name": "bench-alias-0000012", "url": "/a/14/"},
                ],
                "prefix_display_cidr": "198.18.0.12/32",
                "children": [],
            }
        ]
        _attach_ipa_cell_display_hints(nodes)
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {"node": nodes[0], "depth": 1},
        )
        address_start = html.index("nsm-ipa-cell-tree-col--address")
        address_end = html.index("</td>", address_start)
        address_html = html[address_start:address_end]
        us_start = html.index('<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--us">')
        us_end = html.index("</td>", us_start)
        us_html = html[us_start:us_end]
        self.assertIn("bench-ip-0000012", address_html)
        self.assertIn("nsm-ipa-cell-tree-address--multi", address_html)
        self.assertIn('title="Multiple address names share this network in the rule cell"', address_html)
        self.assertNotIn("+2 aliases", address_html)
        self.assertNotIn("nsm-ipa-cell-secondary-expand-summary", address_html)
        self.assertNotIn("nsm-ipa-cell-secondary-hint--aliases", address_html)
        self.assertIn("bench-dup-0000012", address_html)
        self.assertIn("bench-alias-0000012", address_html)
        self.assertNotIn("bench-dup-0000012", us_html)
        self.assertNotIn("bench-alias-0000012", us_html)
        self.assertNotIn("nsm-ipa-cell-secondary-hint--aliases", us_html)
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("dup", dup_html)
        self.assertIn(
            'title="Multiple address names share this network in the rule cell"',
            dup_html,
        )
        self.assertNotIn("nsm-ipa-cell-duplicate", address_html)

    def test_cell_addresses_multi_dup_badge_renders_in_duplicate_column_only(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0000012",
                    "url": "/a/12/",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "cell_addresses_multi": True,
                    "cell_addresses": [
                        {"name": "bench-ip-0000012", "url": "/a/12/"},
                        {"name": "bench-dup-0000012", "url": "/a/13/"},
                    ],
                    "prefix_display_cidr": "198.18.0.12/32",
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        address_start = html.index("nsm-ipa-cell-tree-col--address")
        address_end = html.index("</td>", address_start)
        address_html = html[address_start:address_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertNotIn("nsm-ipa-cell-duplicate", address_html)
        self.assertIn("nsm-ipa-cell-tree-address--multi", address_html)

    def test_doppelt_warning_badge_renders_in_duplicate_column_only(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip",
                    "url": "/a/5/",
                    "ct": "10",
                    "pk": "5",
                    "kind": "leaf",
                    "is_doppelt": True,
                    "prefix_display_cidr": "10.0.0.5/32",
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        us_start = html.index('<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--us">')
        us_end = html.index("</td>", us_start)
        us_html = html[us_start:us_end]
        address_start = html.index("nsm-ipa-cell-tree-col--address")
        address_end = html.index("</td>", address_start)
        address_html = html[address_start:address_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("dup", dup_html)
        self.assertNotIn("nsm-ipa-cell-secondary-hint--doppelt", html)
        self.assertNotIn("nsm-ipa-cell-duplicate", us_html)
        self.assertNotIn("nsm-ipa-cell-duplicate", address_html)

    def test_deprecated_status_badge_renders_in_duplicate_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "old-addr",
                    "url": "/a/9/",
                    "kind": "leaf",
                    "prefix_display_cidr": "10.112.200.0/24",
                    "dup_cell_statuses": ["deprecated"],
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-status--deprecated", dup_html)
        self.assertIn("deprecated", dup_html)
        self.assertNotIn("nsm-ipa-cell-duplicate", dup_html)

    def test_reserved_status_badge_renders_in_duplicate_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "hold-grp",
                    "url": "/g/3/",
                    "kind": "group",
                    "cell_pill_group": True,
                    "dup_cell_statuses": ["reserved"],
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-status--reserved", dup_html)
        self.assertIn("reserved", dup_html)

    def test_dup_and_deprecated_badges_render_together_in_duplicate_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "old-dup",
                    "url": "/a/5/",
                    "kind": "leaf",
                    "is_doppelt": True,
                    "status": "deprecated",
                    "dup_cell_statuses": ["deprecated"],
                    "prefix_display_cidr": "10.0.0.5/32",
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-dup-stack", dup_html)
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("nsm-ipa-cell-status--deprecated", dup_html)

    def test_subnet_containment_dup_badge_renders_in_duplicate_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip",
                    "url": "/a/5/",
                    "kind": "leaf",
                    "prefix_display_cidr": "10.1.0.0/16",
                    "subnet_contained_in": "10.0.0.0/8",
                    "subnet_contained_in_name": "g-10.0.0.0/8",
                    "children": [],
                },
                "depth": 1,
            },
        )
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        us_start = html.index('<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--us">')
        us_end = html.index("</td>", us_start)
        us_html = html[us_start:us_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("Redundant — contained in parent prefix 10.0.0.0/8", dup_html)
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        self.assertNotIn("nsm-ipa-cell-duplicate", us_html)

    def test_ipam_filler_row_is_not_rendered_in_cell_tree(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "198.18.0.0/20",
                    "prefix_display_cidr": "198.18.0.0/20",
                    "node_role": "nsm_prefix",
                    "is_ipam_filler": True,
                    "ipam_synthetic": True,
                    "ipa_tree_node_type": "ipam_filler",
                    "subnet_contained_in": "10.0.0.0/8",
                    "children": [],
                },
                "depth": 1,
            },
        )
        self.assertEqual(html.strip(), "")
        self.assertNotIn("198.18.0.0/20", html)
        self.assertNotIn("nsm-ipa-tree-node--ipam-filler", html)

    def test_info_gap_row_is_not_rendered_in_cell_tree(self):
        from django.template.loader import render_to_string

        gap_label = "[99 used / 155 unused ip]"
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "kind": "ipa_info_gap",
                    "ipa_tree_node_type": "info_gap",
                    "info_summary": True,
                    "ipa_gap_display_label": gap_label,
                    "ipa_gap_label": gap_label,
                    "name": gap_label,
                    "children": [],
                },
                "depth": 2,
            },
        )
        self.assertEqual(html.strip(), "")
        self.assertNotIn("nsm-ipa-tree-node--info-gap", html)
        self.assertNotIn("99 used / 155 unused ip", html)

    def test_ipam_stats_renders_in_ipam_column_not_us(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipam_drilldown import _attach_ipam_stats_meta

        node = {
            "name": "10.0.0.0/24",
            "kind": "group",
            "prefix_display_cidr": "10.0.0.0/24",
            "children": [],
        }
        _attach_ipam_stats_meta(
            node,
            {
                "child_prefixes": {"count": 0},
                "ip_addresses": {"count": 1},
                "ip_ranges": {"count": 0},
            },
        )
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {"node": node, "depth": 1},
        )
        ipam_start = html.index("nsm-ipa-cell-tree-col--ipam")
        ipam_end = html.index("</td>", ipam_start)
        ipam_html = html[ipam_start:ipam_end]
        us_start = html.index('<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--us">')
        us_end = html.index("</td>", us_start)
        us_html = html[us_start:us_end]
        self.assertIn("nsm-addr-ipam-short", ipam_html)
        self.assertIn("0/1/0", ipam_html)
        self.assertNotIn("nsm-addr-ipam-short", us_html)

    def test_ipa_drilldown_meta_stats_renders_in_ipam_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "dm-addr-10-112-129-0-24",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "10.112.129.0/24",
                    "ipa_drilldown_meta": {
                        "name": "dm-addr-10-112-129-0-24",
                        "count_subnets": 2,
                        "count_ranges": 1,
                        "count_ips": 8,
                    },
                    "children": [],
                },
                "depth": 1,
            },
        )
        ipam_start = html.index("nsm-ipa-cell-tree-col--ipam")
        ipam_end = html.index("</td>", ipam_start)
        ipam_html = html[ipam_start:ipam_end]
        self.assertIn("2/1/8", ipam_html)
        self.assertIn("nsm-addr-ipam-short", ipam_html)

    def test_ipa_drilldown_meta_prefix_599_renders_netbox_child_counts(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-net-super-00000",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.0.0/16",
                    "ipa_drilldown_meta": {
                        "name": "bench-net-super-00000",
                        "count_subnets": 259,
                        "count_ranges": 0,
                        "count_ips": 0,
                    },
                    "children": [
                        {
                            "name": "bench-ip-0000000",
                            "prefix_display_cidr": "198.18.0.1/32",
                            "node_role": "nsm_host",
                            "children": [],
                        }
                    ],
                },
                "depth": 0,
            },
        )
        ipam_start = html.index("nsm-ipa-cell-tree-col--ipam")
        ipam_end = html.index("</td>", ipam_start)
        ipam_html = html[ipam_start:ipam_end]
        self.assertIn("259/0/0", ipam_html)
        self.assertNotIn("0/0/1", ipam_html)

    def test_ipa_drilldown_meta_slash24_renders_ip_count(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "198.18.228.0/24",
                    "kind": "group",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.228.0/24",
                    "subnet_contained_in": "198.18.0.0/16",
                    "ipa_drilldown_meta": {
                        "count_subnets": 0,
                        "count_ranges": 0,
                        "count_ips": 100,
                    },
                    "children": [],
                },
                "depth": 1,
            },
        )
        ipam_start = html.index("nsm-ipa-cell-tree-col--ipam")
        ipam_end = html.index("</td>", ipam_start)
        ipam_html = html[ipam_start:ipam_end]
        self.assertIn("0/0/100", ipam_html)
        self.assertNotIn("—", ipam_html)
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("Redundant — contained in parent prefix 198.18.0.0/16", dup_html)
        network_start = html.index("nsm-ipa-cell-tree-col--network")
        network_end = html.index("</td>", network_start)
        network_html = html[network_start:network_end]
        self.assertNotIn("nsm-ipa-subnet-contained", network_html)
        self.assertNotIn("warn duplicate", network_html)

    def test_subnet_contained_network_cell_stays_teal_not_orange(self):
        """Regression: /24 under /16 must not orange the Network CIDR (Dup column warns)."""
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-net-00000",
                    "url": "/a/1/",
                    "ct": "10",
                    "pk": "1",
                    "kind": "group",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.0.0/24",
                    "subnet_contained_in": "198.18.0.0/16",
                    "subnet_contained_in_name": "198.18.0.0/16",
                    "children": [],
                },
                "depth": 1,
            },
        )
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        network_start = html.index("nsm-ipa-cell-tree-col--network")
        network_end = html.index("</td>", network_start)
        network_html = html[network_start:network_end]
        self.assertIn("198.18.0.0/24", network_html)
        self.assertNotIn("nsm-ipa-subnet-contained", network_html)
        self.assertNotIn("warn duplicate", network_html)
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn("Redundant — contained in parent prefix 198.18.0.0/16", dup_html)

    def test_empty_info_gap_row_is_not_rendered(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "kind": "ipa_info_gap",
                    "ipa_tree_node_type": "info_gap",
                    "info_summary": True,
                    "children": [],
                },
                "depth": 2,
            },
        )
        self.assertEqual(html.strip(), "")

    def test_deprecated_and_reserved_status_icons_in_applet(self):
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
        self.assertIn("fst-italic", html)
        self.assertIn("text-muted", html)
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
        self.assertIn('title="diff-test-10-112-134-0-24 · 10.112.134.0/24"', html)
        self.assertIn('title="dm-addr-10-112-134-0-24 · 10.112.134.0/24"', html)
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
        self.assertIn("nsm-ipa-cell-tree-address", cell_html)
        self.assertNotIn("nsm-ipa-cell-pill--address", cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta--info", cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta-info-stat", cell_html)
        self.assertNotIn("Info", cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta-pill--name", cell_html)
        self.assertIn("dm-addr-10-112-129-0-24", cell_html)
        self.assertNotIn("Dunder Mifflin", cell_html)
        self.assertNotIn("nsm-ipa-drilldown-meta--info", drilldown_html)
        self.assertIn("10.112.129.0/24", drilldown_html)

    def test_ipa_cell_direct_leaf_prefix_renders_info_expand(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import _mark_ipa_cell_open_by_default

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
        self.assertIn("nsm-ipa-cell-tree-row", html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertNotIn("nsm-ipa-drilldown-meta--info", html)
        self.assertIn("10.112.128.0/28", html)
        self.assertNotIn("Dunder Mifflin", html)
        self.assertNotIn("nsm-addr-leaf-summary", html)

    def test_ipa_cell_direct_nested_host_renders_parent_details_open(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import _mark_ipa_cell_open_by_default

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
        self.assertIn("nsm-ipa-cell-tree-row", html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertIn("10.112.134.44/32", html)
        self.assertNotIn("nsm-ipa-cell-children", html)

    def test_ipa_cell_direct_drilldown_renders_open_by_default(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import _mark_ipa_cell_open_by_default

        nodes = [
            {
                "name": "bench-ip-0014328",
                "url": "/a/5/",
                "ct": "10",
                "pk": "5",
                "kind": "leaf",
                "is_cell_direct": True,
                "ip_ref": {"str": "198.18.143.0/24", "url": "#"},
                "prefix_display_cidr": "198.18.143.0/24",
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
        self.assertRegex(html, r'<details class="[^"]*nsm-ipa-drilldown-details[^"]*" open>')
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
        self.assertIn('<tr class="nsm-ipa-cell-tree-row', html)
        self.assertNotIn("nsm-addr-leaf-summary", html)
        self.assertNotIn("nsm-ipa-cell-object-summary--has-info", html)

    def test_ipa_cell_direct_summary_shows_cidr_and_object_link(self):
        html = self._render_object_tree_html()
        row_start = html.index("nsm-ipa-object-node--cell-direct")
        row_end = html.index("</tr>", row_start)
        row_html = html[row_start:row_end]
        self.assertIn("nsm-ipa-cell-cidr", row_html)
        self.assertIn("198.18.143.0/24", row_html)
        self.assertIn("nsm-ipa-cell-tree-address", row_html)
        self.assertIn("bench-ip-0014328", row_html)
        network_pos = row_html.index("nsm-ipa-cell-tree-col--network")
        address_pos = row_html.index("nsm-ipa-cell-tree-col--address")
        self.assertLess(network_pos, address_pos)
        self.assertNotIn("nsm-ipa-cell-pill-body", html)
        self.assertNotIn("→", row_html)

    def test_ipa_cell_direct_host_leaf_subnet_containment_renders_parent_hint(self):
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
        self.assertIn('<tr class="nsm-ipa-cell-tree-row', html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertIn("10.112.134.0/24", html)
        self.assertIn("dm-addr-10-112-134-0-24", html)
        self.assertNotIn("nsm-ipa-cell-cidr-hint", html)
        self.assertNotIn("nsm-ipa-cell-object-leaf--has-info", html)
        self.assertNotIn("nsm-ipa-drilldown-meta--warning", html)
        self.assertNotIn("10.112.134.44 in 10.112.134.0/24", html)
        self.assertNotIn("nsm-ipa-cell-pill--parent", html)
        self.assertIn("nsm-ipa-cell-tree-address", html)
        self.assertIn("record-depth", html)
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        address_start = html.index("nsm-ipa-cell-tree-col--address")
        address_end = html.index("</td>", address_start)
        address_html = html[address_start:address_end]
        self.assertNotIn("nsm-ipa-cell-parent-hint", address_html)

    def test_flat_cell_tree_row_omits_parent_column_for_subnet_contained_in(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0000001",
                    "url": "/a/1/",
                    "ct": "10",
                    "pk": "1",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "10.0.0.1/32",
                    "subnet_contained_in": "10.0.0.0/24",
                    "subnet_contained_in_name": "bench-net-00000",
                    "subnet_contained_in_url": "/a/2/",
                    "children": [],
                },
                "depth": 1,
            },
        )
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        self.assertNotIn("nsm-ipa-cell-parent-hint", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)

    def test_flat_cell_tree_row_omits_parent_column_for_tree_parent_cidr(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-00000010",
                    "url": "/a/10/",
                    "ct": "10",
                    "pk": "10",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.0.10/32",
                    "cell_groups_multi": True,
                    "ipa_tree_parent_cidr": "198.18.0.0/24",
                    "ipa_tree_parent_name": "198.18.0.0/24",
                    "ipa_tree_parent_url": "/ipam/prefixes/24/",
                    "children": [],
                },
                "depth": 3,
            },
        )
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        self.assertNotIn("nsm-ipa-cell-parent-hint", html)

    def test_bench_alias_overlap_row_renders_ipa_tree_parent_without_subnet_contained_in(
        self,
    ):
        """Regression: bench-alias-0000000 overlap rows must not crash template render."""
        from django.template.loader import render_to_string

        node = {
            "name": "bench-alias-0000000",
            "url": "/plugins/netbox-nsm/objects/nsm_address/605/",
            "ct": "276",
            "pk": "605",
            "kind": "leaf",
            "children": [],
            "node_role": "nsm_host",
            "ip_ref": {
                "str": "198.18.0.1/32",
                "url": "/ipam/ip-addresses/181/",
                "type": "Address",
                "ct": 69,
                "pk": 181,
            },
            "is_cell_direct": True,
            "in_cell": True,
            "cell_addresses": [
                {
                    "name": "bench-alias-0000000",
                    "url": "/plugins/netbox-nsm/objects/nsm_address/605/",
                },
                {
                    "name": "bench-dup-0000000",
                    "url": "/plugins/netbox-nsm/objects/nsm_address/630/",
                },
                {
                    "name": "bench-ip-0000000",
                    "url": "/plugins/netbox-nsm/objects/nsm_address/505/",
                },
            ],
            "cell_addresses_multi": True,
            "cell_groups": [
                {
                    "name": "bench-grp-00000",
                    "url": "/plugins/netbox-nsm/objects/nsm_address_group/1/",
                }
            ],
            "ipa_tree_parent_cidr": "198.18.0.0/24",
            "ipa_tree_parent_name": "bench-net-00000",
            "ipa_tree_parent_url": "/plugins/netbox-nsm/objects/nsm_address/1/",
            "ipa_depth": 3,
            "prefix_display_cidr": "198.18.0.1/32",
        }
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {"node": node, "depth": 3},
        )
        self.assertIn("nsm-ipa-cell-tree-address--multi", html)
        self.assertNotIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        self.assertNotIn("nsm-ipa-cell-parent-hint", html)
        dup_start = html.index("nsm-ipa-cell-tree-col--duplicate")
        dup_end = html.index("</td>", dup_start)
        dup_html = html[dup_start:dup_end]
        self.assertIn("nsm-ipa-cell-duplicate", dup_html)
        self.assertIn(
            'title="Multiple address names share this network in the rule cell"',
            dup_html,
        )

        body_html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": [node]},
        )
        self.assertNotIn("Analysis failed", body_html)

    def test_ipam_filler_skipped_in_flat_cell_tree_but_child_renders(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": [
                    {
                        "name": "10.0.0.0/16",
                        "url": "/ipam/prefixes/16/",
                        "kind": "group",
                        "is_ipam_filler": True,
                        "ipam_synthetic": True,
                        "ipa_tree_node_type": "ipam_filler",
                        "prefix_display_cidr": "10.0.0.0/16",
                        "node_role": "nsm_prefix",
                        "children": [
                            {
                                "name": "198.18.0.0/24",
                                "url": "/a/24/",
                                "ct": "10",
                                "pk": "24",
                                "kind": "group",
                                "in_cell": True,
                                "is_cell_direct": True,
                                "prefix_display_cidr": "198.18.0.0/24",
                                "node_role": "nsm_prefix",
                                "children": [],
                            }
                        ],
                    }
                ],
                "depth": 0,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertNotIn("10.0.0.0/16", html)
        self.assertNotIn("nsm-ipa-tree-node--ipam-filler", html)
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertIn("198.18.0.0/24", html)

    def test_ipa_ipam_synthetic_prefix_renders_grey_row_class(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_tree_node.html",
            {
                "node": {
                    "name": "10.0.0.0/16",
                    "url": "/ipam/prefixes/16/",
                    "kind": "group",
                    "is_ipam_filler": True,
                    "ipam_synthetic": True,
                    "prefix_display_cidr": "10.0.0.0/16",
                    "node_role": "nsm_prefix",
                    "children": [
                        {
                            "name": "198.18.0.0/24",
                            "url": "/a/24/",
                            "ct": "10",
                            "pk": "24",
                            "kind": "group",
                            "in_cell": True,
                            "is_cell_direct": True,
                            "prefix_display_cidr": "198.18.0.0/24",
                            "node_role": "nsm_prefix",
                            "children": [],
                        }
                    ],
                },
                "depth": 0,
                "prefix": "ipa",
                "show_copy": False,
            },
        )
        self.assertIn("nsm-ipa-tree-node--ipam-filler", html)
        self.assertIn("nsm-ipa-object-node--ipam-synthetic", html)
        self.assertIn("10.0.0.0/16", html)
        self.assertNotIn("nsm-ipa-cell-tree-address", html.split("10.0.0.0/16")[1].split("198.18.0.0/24")[0])

    def test_cell_direct_row_has_cell_direct_class_not_indirect(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0014328",
                    "url": "/a/5/",
                    "ct": "10",
                    "pk": "5",
                    "kind": "leaf",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.143.0/24",
                    "children": [],
                },
                "depth": 0,
            },
        )
        self.assertIn("nsm-ipa-object-node--cell-direct", html)
        self.assertNotIn("nsm-ipa-object-node--cell-indirect", html)

    def test_network_cell_links_via_node_url_without_ip_ref(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-net-00001",
                    "url": "/plugins/netbox-nsm/addresses/1/",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.19.90.0/24",
                    "children": [],
                },
                "depth": 0,
            },
        )
        self.assertIn('href="/plugins/netbox-nsm/addresses/1/"', html)
        self.assertIn("nsm-ipa-cell-cidr-link", html)
        self.assertIn("198.19.90.0/24", html)

    def test_address_column_link_exposes_name_and_cidr_tooltip(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-net-00002",
                    "url": "/plugins/netbox-nsm/objects/nsm_address/2/",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.19.90.0/24",
                    "children": [],
                },
                "depth": 0,
            },
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn("bench-net-00002", address_col_html)
        self.assertIn(
            'title="bench-net-00002 · 198.19.90.0/24"',
            address_col_html,
        )

    def test_address_column_group_anchor_tooltip_includes_group_context(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-grp-00346",
                    "url": "/g/500/",
                    "is_cell_direct": True,
                    "in_cell": True,
                    "cell_pill_group": True,
                    "prefix_display_cidr": "198.19.90.0/24",
                    "cell_group_anchor_address": {
                        "name": "bench-net-00346",
                        "url": "/plugins/netbox-nsm/objects/nsm_address/347/",
                    },
                    "children": [],
                },
                "depth": 0,
            },
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn(
            'title="Anchor address bench-net-00346 for group bench-grp-00346 · 198.19.90.0/24"',
            address_col_html,
        )

    def test_address_column_indirect_link_appends_indirect_hint(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip-0000099",
                    "url": "/a/99/",
                    "prefix_display_cidr": "198.18.0.99/32",
                    "cell_groups": [{"name": "bench-grp-00098", "url": "/g/98/"}],
                    "children": [],
                },
                "depth": 0,
            },
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn(
            'title="bench-ip-0000099 · 198.18.0.99/32 | Indirect (not directly in rule cell)"',
            address_col_html,
        )

    def test_address_column_non_active_status_in_tooltip(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "old-net",
                    "url": "/a/1/",
                    "status": "deprecated",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "10.0.0.0/24",
                    "children": [],
                },
                "depth": 0,
            },
        )
        address_col_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--address">'
        )
        address_col_end = html.index("</td>", address_col_start)
        address_col_html = html[address_col_start:address_col_end]
        self.assertIn(
            'title="old-net · 10.0.0.0/24 (deprecated)"',
            address_col_html,
        )

    def test_cell_addresses_multi_does_not_add_subnet_warning_row_class(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-alias-00001",
                    "url": "/a/1/",
                    "is_cell_direct": True,
                    "prefix_display_cidr": "198.18.0.0/24",
                    "cell_addresses_multi": True,
                    "cell_addresses": [
                        {"name": "bench-alias-00001", "url": "/a/1/"},
                        {"name": "bench-ip-00001", "url": "/a/2/"},
                    ],
                    "children": [],
                },
                "depth": 0,
            },
        )
        self.assertIn("nsm-ipa-cell-tree-address--multi", html)
        self.assertNotIn("nsm-ipa-object-node--subnet-warning", html)

    def test_indirect_prefix_ipam_column_uses_drilldown_meta(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "198.18.0.0/16",
                    "prefix_display_cidr": "198.18.0.0/16",
                    "node_role": "nsm_prefix",
                    "ipa_drilldown_meta": {
                        "count_subnets": 259,
                        "count_ranges": 0,
                        "count_ips": 0,
                    },
                    "children": [],
                },
                "depth": 1,
            },
        )
        ipam_start = html.index("nsm-ipa-cell-tree-col--ipam")
        ipam_end = html.index("</td>", ipam_start)
        ipam_html = html[ipam_start:ipam_end]
        self.assertIn("259/0/0", ipam_html)
        self.assertNotIn(">—<", ipam_html)

    def test_indirect_drilldown_member_row_has_cell_indirect_class(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "h-198.18.0.10",
                    "url": "/a/10/",
                    "ct": "10",
                    "pk": "10",
                    "kind": "leaf",
                    "prefix_display_cidr": "198.18.0.10/32",
                    "children": [],
                },
                "depth": 2,
            },
        )
        self.assertIn("nsm-ipa-object-node--cell-indirect", html)
        self.assertNotIn("nsm-ipa-object-node--cell-direct", html)

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

        from netbox_nsm.analyzers.ip.ipa_object_tree import (
            _build_ipa_cell_object_tree_from_diff,
        )

        addr_analysis = [
            {
                "field_slug": "diff",
                "types": [
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
                                        "ip_ref": {"str": "198.19.207.55/32", "url": "#"},
                                        "prefix_display_cidr": "198.19.207.55/32",
                                        "diff_status": "in_some",
                                        "children": [],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        object_tree = _build_ipa_cell_object_tree_from_diff(addr_analysis)
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": addr_analysis, "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-cell-tree-table", html)
        self.assertIn("nsm-addr-diff-in-some-head", html)
        self.assertIn("− Rule bench-rule-00038 (38) / destination", html)
        self.assertIn("− Rule bench-rule-03250 (3250) / destination", html)
        self.assertNotIn("In some: Rule", html)
        self.assertNotIn("nsm-addr-details nsm-addr-category", html)

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
        self.assertIn("table table-hover object-list", html)
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
        _attach_ipa_cell_display_hints(object_tree)
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertNotIn("nsm-ipa-tree-dots", html)
        self.assertIn("record-depth", html)
        self.assertNotIn("nsm-ipa-subnet-contained", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertNotIn("nsm-ipa-cell-tree-col--parent", html)
        self.assertNotIn("nsm-ipa-cell-parent-hint", html)
        self.assertIn("nsm-ipa-cell-duplicate", html)
        self.assertNotIn("nsm-ipa-cell-pill--parent", html)
        self.assertNotIn("nsm-ipa-cell-cidr-hint", html)
        self.assertNotIn("mdi-alert-circle-outline", html)
        self.assertNotIn("nsm-ipa-duplicate-indicator", html)
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertNotIn("nsm-ipa-expanded-warning--subnet", html)
        self.assertIn(
            'title="Redundant — contained in parent prefix 10.0.0.0/8"',
            html,
        )
        self.assertNotIn("warn duplicate →", html)
        self.assertNotIn(">ADDRESS<", html)
        self.assertNotIn("ADDRESS_GROUP", html)
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
        self.assertIn("table table-hover object-list", html)
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
                "ip_ref": {"str": "198.18.130.0/24", "url": "#"},
                "prefix_display_cidr": "198.18.130.0/24",
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
        self.assertNotRegex(html, r'<details[^>]*open[^>]*nsm-ipa-drilldown-details')

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
        self.assertIn("nsm-ipa-cell-tree-groups", html)
        self.assertNotIn("ADDRESS_GROUP", html)
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
                "ip_ref": {"str": "198.18.143.0/24", "url": "#"},
                "prefix_display_cidr": "198.18.143.0/24",
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
        self.assertNotIn("nsm-ipa-subnet-contained", html)
        self.assertIn("nsm-ipa-object-node--subnet-warning", html)
        self.assertNotIn("nsm-ipa-expanded-warnings", html)
        self.assertIn(
            'title="Redundant — contained in parent prefix 10.0.0.0/8 (g-10.0.0.0/8)"',
            html,
        )
        self.assertNotIn("warn duplicate →", html)
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
                "ip_ref": {"str": "198.18.130.0/24"},
                "prefix_display_cidr": "198.18.130.0/24",
                "subnet_contained_in": "10.0.0.0/8",
                "children": [],
            }
        ]
        lines = _flatten_ipa_object_tree_copy_lines(nodes)
        self.assertEqual(
            lines,
            ["bench-ip,198.18.130.0/24,warn duplicate→10.0.0.0/8"],
        )

    @patch(
        "netbox_nsm.analyzers.ip.ipa_object_tree._ipa_object_drilldown_has_visible_content",
        return_value=True,
    )
    @patch("netbox_nsm.analyzers.ip.ipa_object_tree._ipa_object_has_addr_drilldown", return_value=True)
    @patch("netbox_nsm.analyzers.ip.ipa_object_tree._build_ipa_object_tree_node")
    def test_build_ipa_cell_object_tree_marks_addr_drilldown_lazy(
        self, build_node_fn, _drilldown_fn, _visible_fn
    ):
        from netbox_nsm.analyzers.ip.ipa_object_tree import _build_ipa_cell_object_tree

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

    def test_object_tree_renders_column_header(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": self._OBJECT_TREE_FIXTURE},
        )
        self.assertIn("nsm-ipa-cell-tree-header", html)
        self.assertIn("toggle-depth", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--network", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--ipam", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--address", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--address-group", html)
        self.assertNotIn("nsm-ipa-cell-tree-header-col--parent", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--merge", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--diff", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--duplicate", html)
        self.assertIn("nsm-ipa-cell-tree-header-col--us", html)
        ipam_pos = html.index("nsm-ipa-cell-tree-header-col--ipam")
        dup_pos = html.index("nsm-ipa-cell-tree-header-col--duplicate")
        address_pos = html.index("nsm-ipa-cell-tree-header-col--address")
        self.assertLess(ipam_pos, dup_pos)
        self.assertLess(dup_pos, address_pos)
        self.assertIn('colspan="8"', html)
        self.assertIn("<colgroup>", html)
        self.assertIn("nsm-ipa-cell-tree-col--ipam", html)
        self.assertIn("nsm-ipa-cell-tree-col--merge", html)
        self.assertIn("nsm-ipa-cell-tree-col--diff", html)
        self.assertIn("nsm-ipa-cell-tree-col--duplicate", html)
        self.assertIn("nsm-ipa-cell-tree-col--address-group", html)
        self.assertNotIn("nsm-ipa-cell-tree-header-col--object", html)
        self.assertNotIn("nsm-ipa-cell-tree-header-col--meta", html)

    def test_diff_present_labels_render_in_diff_column_not_us(self):
        from django.template.loader import render_to_string

        labels = [
            "Rule bench-rule-00038 (38) / destination",
            "Rule bench-rule-03250 (3250) / destination",
        ]
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "kind": "group",
                    "name": "In some",
                    "url": "#",
                    "diff_group": "in-some",
                    "diff_present_labels": labels,
                    "children": [],
                },
                "depth": 0,
            },
        )
        diff_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--diff">'
        )
        diff_end = html.index("</td>", diff_start)
        diff_html = html[diff_start:diff_end]
        us_start = html.index('<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--us">')
        us_end = html.index("</td>", us_start)
        us_html = html[us_start:us_end]
        self.assertIn("nsm-ipa-cell-diff--in-some", diff_html)
        self.assertIn("some", diff_html)
        self.assertIn("− Rule bench-rule-00038 (38) / destination", diff_html)
        self.assertNotIn("nsm-addr-diff-present-label", us_html)
        self.assertIn("nsm-addr-diff-group--in-some", html)

    def test_diff_status_leaf_renders_compact_badge_in_diff_column(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "host-a",
                    "url": "#",
                    "ip_ref": {"str": "10.0.0.1", "url": "#"},
                    "diff_status": "only_a",
                    "diff_label": "Rule 1/5",
                    "diff_name_a": "host-a",
                    "diff_url_a": "#",
                    "children": [],
                },
                "depth": 1,
            },
        )
        diff_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--diff">'
        )
        diff_end = html.index("</td>", diff_start)
        diff_html = html[diff_start:diff_end]
        self.assertIn("nsm-addr-diff--only_a", diff_html)
        self.assertIn("Rule 1/5", diff_html)
        self.assertIn("nsm-addr-diff-leaf--only_a", html)
        self.assertIn("nsm-ipa-diff-name-a", html)

    def test_diff_fund_renders_in_diff_and_address_columns(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "kind": "leaf",
                    "name": "host-a",
                    "url": "#",
                    "diff_fund": True,
                    "diff_name_a": "host-a",
                    "diff_name_b": "host-b",
                    "diff_url_a": "#",
                    "diff_url_b": "#",
                    "ip_ref": {"str": "10.0.0.1", "url": "#"},
                    "prefix_display_cidr": "10.0.0.1/32",
                    "children": [],
                },
                "depth": 1,
            },
        )
        diff_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--diff">'
        )
        diff_end = html.index("</td>", diff_start)
        diff_html = html[diff_start:diff_end]
        self.assertIn("nsm-ipa-cell-diff--fund", diff_html)
        self.assertIn("nsm-addr-diff-fund-row", html)
        self.assertIn("nsm-addr-diff-leaf--fund", html)

    def test_merge_column_empty_for_single_address_row(self):
        from django.template.loader import render_to_string

        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_row.html",
            {
                "node": {
                    "name": "bench-ip",
                    "url": "/a/5/",
                    "kind": "leaf",
                    "prefix_display_cidr": "10.0.0.5/32",
                    "children": [],
                },
                "depth": 1,
            },
        )
        merge_start = html.index(
            '<td class="nsm-ipa-cell-tree-col nsm-ipa-cell-tree-col--merge">'
        )
        merge_end = html.index("</td>", merge_start)
        merge_html = html[merge_start:merge_end]
        self.assertIn("—", merge_html)
        self.assertNotIn("nsm-ipa-cell-merge", merge_html)

    def test_collapsed_group_membership_renders_summary_details(self):
        from django.template.loader import render_to_string

        groups = [{"name": f"bench-grp-{idx:05d}", "url": f"/g/{idx}/"} for idx in range(5)]
        object_tree = [
            {
                "name": "bench-net-0000001",
                "url": "/a/1/",
                "ct": "10",
                "pk": "1",
                "kind": "leaf",
                "cell_groups": groups,
                "cell_groups_multi": True,
                "cell_groups_collapsed": True,
                "collapsed_group_count": 5,
                "prefix_display_cidr": "198.18.0.1/32",
                "children": [],
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-cell-groups-collapsed", html)
        self.assertNotIn("nsm-ipa-cell-pill--group-summary", html)
        self.assertIn("5 groups", html)
        self.assertIn("nsm-ipa-cell-groups-collapsed-body", html)

    def test_collapsed_root_groups_wrapper_renders_summary_section(self):
        from django.template.loader import render_to_string

        children = [
            {
                "name": f"bench-grp-{idx:05d}",
                "url": f"/g/{idx}/",
                "ct": "10",
                "pk": str(idx),
                "kind": "group",
                "node_role": "nsm_group",
                "cell_pill_group": True,
                "is_cell_direct": True,
                "children": [],
            }
            for idx in range(1, 5)
        ]
        object_tree = [
            {
                "kind": "group",
                "ipa_tree_node_type": "collapsed_root_groups",
                "collapsed_group_count": 4,
                "children": children,
            }
        ]
        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("nsm-ipa-root-groups-collapsed", html)
        self.assertIn("4 address groups", html)
        self.assertIn("bench-grp-00001", html)
        self.assertNotRegex(html, r'<details[^>]*open[^>]*nsm-ipa-root-groups-collapsed')

    def test_collapsed_root_groups_survive_display_hints_and_render(self):
        from django.template.loader import render_to_string

        from netbox_nsm.analyzers.ip.ipa_object_tree import (
            _attach_ipa_cell_display_hints,
            _wrap_collapsed_root_group_nodes,
        )

        children = [
            {
                "name": f"bench-grp-{idx:05d}",
                "url": f"/g/{idx}/",
                "ct": "10",
                "pk": str(idx),
                "kind": "group",
                "node_role": "nsm_group",
                "cell_pill_group": True,
                "is_cell_direct": True,
                "children": [],
            }
            for idx in range(1, 5)
        ]
        object_tree = _wrap_collapsed_root_group_nodes(children)
        _attach_ipa_cell_display_hints(object_tree)
        self.assertEqual(object_tree[-1].get("collapsed_group_count"), 4)

        html = render_to_string(
            "netbox_nsm/inc/addr_analysis_applet_body.html",
            {"addr_analysis": [], "object_tree": object_tree},
        )
        self.assertIn("4 address groups", html)
        self.assertNotIn("Analysis failed", html)
