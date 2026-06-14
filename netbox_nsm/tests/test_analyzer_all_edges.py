"""Tests for object analyzer all-edge composition."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzer.all_edges import compose_all_edges, dcim_cable_edges


class AnalyzerAllEdgesTests(SimpleTestCase):
    @patch("netbox_nsm.analyzer.all_edges.forward_relation_edges", return_value=[])
    @patch("netbox_nsm.analyzer.all_edges.reverse_fk_edges", return_value=[])
    @patch("netbox_nsm.analyzer.all_edges.dcim_cable_edges")
    @patch("netbox_nsm.analyzer.all_edges.ContentType.objects.get_for_model")
    @patch("netbox_nsm.analyzer.edge_sources.nsm_link_edges", return_value=[])
    @patch("netbox_nsm.analyzer.edge_sources.rule_object_item_edges", return_value=[])
    @patch("netbox_nsm.analyzer.edge_sources.group_m2m_edges", return_value=[])
    @patch("netbox_nsm.analyzer.edge_sources.addr_fk_edges", return_value=[])
    @patch("netbox_nsm.analyzer.edge_sources.inherited_nsm_link_edges", return_value=[])
    def test_compose_deduplicates_edges(
        self,
        _inh,
        _addr,
        _group,
        _rule,
        _nsm,
        _ct,
        mock_cable,
        _rev,
        _fwd,
    ):
        from netbox_nsm.analyzer.registry import AnalyzerEdge, AnalyzerNode

        node = AnalyzerNode(
            id="1:2",
            ct_id=1,
            object_id=2,
            node_type="object",
            type_label="DCIM › Cable",
            label="Cable #4",
            url="#",
        )
        mock_cable.return_value = [AnalyzerEdge("Cable", "cable", node)]
        obj = MagicMock()
        edges = compose_all_edges(obj)
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_label, "Cable")

    def test_dcim_cable_edges_from_link_peers(self):
        from netbox_nsm.analyzer.registry import AnalyzerNode

        peer = MagicMock()
        peer.pk = 9
        peer.get_absolute_url.return_value = "/peer/9/"
        peer._meta.app_label = "dcim"
        peer._meta.model_name = "poweroutlet"
        peer._meta.verbose_name = "power outlet"

        obj = MagicMock()
        obj.cable = None
        obj.connected_endpoint = None
        obj.link_peers = [peer]

        with patch("netbox_nsm.analyzer.all_edges.node_from_object") as mock_node:
            mock_node.return_value = AnalyzerNode(
                id="3:9",
                ct_id=3,
                object_id=9,
                node_type="object",
                type_label="DCIM › Power Outlet",
                label="Outlet 1",
                url="/peer/9/",
            )
            edges = dcim_cable_edges(obj)

        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].edge_label, "Connected to")
