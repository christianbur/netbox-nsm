"""Tests for object analyzer inherited NSM link edges."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzer._helpers import inherited_nsm_link_edges


class AnalyzerInheritanceTests(SimpleTestCase):
    @patch("netbox_nsm.analyzer.registry.node_from_object")
    @patch("netbox_nsm.models.ObjectLink")
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.ipam_inheritance.ancestor_prefixes_for_ipam")
    def test_inherited_edges_use_prefix_links(
        self,
        ancestor_fn,
        content_type_cls,
        object_link_cls,
        node_from_object_fn,
    ):
        ancestor = MagicMock(pk=1)
        ancestor_fn.return_value = [ancestor]
        pfx_ct = MagicMock()
        content_type_cls.objects.get.return_value = pfx_ct

        zone = MagicMock(pk=42)
        link = MagicMock()
        link.object_b = zone
        link.object_b_type = MagicMock()
        fwd_qs = MagicMock()
        fwd_qs.select_related.return_value = [link]
        rev_qs = MagicMock()
        rev_qs.select_related.return_value = []
        object_link_cls.objects.filter.side_effect = [fwd_qs, rev_qs]
        node_from_object_fn.return_value = {"id": "zone-1"}

        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_label, "Inherited")
        self.assertEqual(edges[0].edge_type, "inherited_link")
        node_from_object_fn.assert_called_once_with(zone)

    @patch("netbox_nsm.ipam_inheritance.ancestor_prefixes_for_ipam", return_value=[])
    def test_inherited_edges_empty_when_no_ancestors(self, _ancestor_fn):
        edges = inherited_nsm_link_edges(MagicMock())

        self.assertEqual(edges, [])
