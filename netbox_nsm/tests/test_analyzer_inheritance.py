"""Tests for object analyzer inherited NSM link edges."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzer._helpers import inherited_nsm_link_edges
from netbox_nsm.ipam_inheritance import InheritedNsmLink


class AnalyzerInheritanceTests(SimpleTestCase):
    @patch("netbox_nsm.analyzer._helpers.iter_inherited_nsm_links")
    @patch("netbox_nsm.analyzer._helpers.node_from_object")
    def test_inherited_edges_use_shared_iterator(
        self, node_from_object_fn, iter_links_fn
    ):
        zone = MagicMock()
        zone_ct = MagicMock(pk=99)
        ancestor = MagicMock()
        zone_tc = MagicMock(inherit_links=True, inherit_stop_on_own=False)
        iter_links_fn.return_value = [
            InheritedNsmLink(
                linked=zone,
                linked_ct=zone_ct,
                type_key="netbox_custom_objects__nsmzone",
                ancestor=ancestor,
                tc=zone_tc,
            )
        ]
        node_from_object_fn.return_value = {"id": "zone-1"}

        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].label, "Inherited")
        self.assertEqual(edges[0].edge_type, "inherited_link")
        node_from_object_fn.assert_called_once_with(zone)

    @patch("netbox_nsm.analyzer._helpers.iter_inherited_nsm_links")
    def test_inherited_edges_empty_when_iterator_empty(self, iter_links_fn):
        iter_links_fn.return_value = iter([])

        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(edges, [])
