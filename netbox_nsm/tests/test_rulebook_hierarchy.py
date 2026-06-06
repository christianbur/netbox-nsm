"""Rulebook parent/child hierarchy."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.rulebook_hierarchy import (
    collect_descendant_pks,
    hierarchy_depth,
    render_hierarchy_marker,
    rulebook_tree_order,
    validate_parent_choice,
)


def _rb(pk, parent=None, name=""):
    return SimpleNamespace(pk=pk, parent=parent, name=name or f"rb-{pk}")


class RulebookHierarchyTests(SimpleTestCase):
    def test_hierarchy_depth(self):
        root = _rb(1)
        child = _rb(2, parent=root)
        grand = _rb(3, parent=child)
        self.assertEqual(hierarchy_depth(root), 0)
        self.assertEqual(hierarchy_depth(child), 1)
        self.assertEqual(hierarchy_depth(grand), 2)

    def test_validate_parent_self(self):
        root = _rb(1)
        self.assertIsNotNone(validate_parent_choice(root, root))

    @patch(
        "netbox_nsm.rulebook_hierarchy.collect_descendant_pks",
        return_value={2},
    )
    def test_validate_parent_cycle(self, _mock_descendants):
        root = _rb(1)
        child = _rb(2, parent=root)
        self.assertIsNone(validate_parent_choice(child, root))
        self.assertIsNotNone(validate_parent_choice(root, child))

    def test_render_hierarchy_marker_depths(self):
        self.assertEqual(render_hierarchy_marker(0), "")
        self.assertIn("record-depth", render_hierarchy_marker(1))
        self.assertEqual(render_hierarchy_marker(1).count("•"), 1)
        self.assertEqual(render_hierarchy_marker(2).count("•"), 2)
        self.assertEqual(render_hierarchy_marker(3).count("•"), 3)

    def test_rulebook_tree_order(self):
        root = _rb(1, name="A")
        child = _rb(2, parent=root, name="B")
        other = _rb(3, name="C")
        order = rulebook_tree_order([child, other, root])
        self.assertEqual(order, [1, 2, 3])

    def test_collect_descendant_pks_none(self):
        self.assertEqual(collect_descendant_pks(None), set())
