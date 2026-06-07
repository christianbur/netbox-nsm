"""CSV copy paths for address analysis trees."""

from django.test import SimpleTestCase

from netbox_nsm.views.rulebook import (
    _addr_path_line,
    _addr_path_parts_for_leaf,
    _enrich_addr_tree_copy_lines,
    _flatten_addr_tree_paths,
    _prefix_addr_copy_lines,
)


class AddrCopyPathTests(SimpleTestCase):
    def test_leaf_path_includes_object_name_and_ip(self):
        node = {
            "name": "branch-ip-demo",
            "kind": "leaf",
            "ip_ref": {"str": "10.129.129.0/24", "url": "/ipam/prefixes/1/"},
            "children": [],
        }
        line = _addr_path_line(_addr_path_parts_for_leaf(node, []))
        self.assertEqual(line, "branch-ip-demo,10.129.129.0/24")

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
