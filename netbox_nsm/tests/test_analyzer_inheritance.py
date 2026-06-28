"""Tests for object analyzer inherited NSM link edges."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analysis.analyzer.edge_sources import inherited_nsm_link_edges, rule_object_item_edges


class AnalyzerInheritanceTests(SimpleTestCase):
    @patch("netbox_nsm.analysis.analyzer.registry.node_from_object")
    @patch("netbox_nsm.addresses.ipam_inheritance.iter_inherited_nsm_links")
    def test_inherited_edges_use_prefix_links(
        self,
        iter_inherited_fn,
        node_from_object_fn,
    ):
        zone = MagicMock(pk=42)
        inherited = MagicMock(linked=zone, linked_ct=MagicMock())
        iter_inherited_fn.return_value = [inherited]
        node_from_object_fn.return_value = {"id": "zone-1"}

        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_label, "Inherited")
        self.assertEqual(edges[0].edge_type, "inherited_link")
        node_from_object_fn.assert_called_once_with(zone)

    @patch("netbox_nsm.addresses.ipam_inheritance.iter_inherited_nsm_links", return_value=[])
    def test_inherited_edges_empty_when_no_ancestors(self, _iter_fn):
        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(edges, [])

    @patch("netbox_nsm.analysis.analyzer.registry.node_from_object")
    @patch("netbox_nsm.security.references.cot_rule_references.scan_cot_security_references")
    def test_rule_edges_use_rule_instance_not_panel_wrapper(
        self,
        scan_fn,
        node_from_object_fn,
    ):
        rule_instance = MagicMock(pk=7)
        panel_rule = MagicMock(_instance=rule_instance)
        scan_fn.return_value = [
            {"rule": panel_rule, "field_name": "source"},
        ]
        node_from_object_fn.return_value = MagicMock()

        edges = rule_object_item_edges(MagicMock(pk=1), MagicMock())

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_label, "Regel (source)")
        node_from_object_fn.assert_called_once_with(rule_instance)
