"""Tests for Object Analyzer mode filtering (all vs security)."""

from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase

from ipam.models import IPAddress, Prefix
from utilities.testing import TestCase

from netbox_nsm.analyzers.object_analyzer.modes import (
    AnalyzerMode,
    clear_security_mode_cache,
    edge_allowed_in_security,
    filter_edges_for_mode,
    parse_analyzer_mode,
)
from netbox_nsm.analyzers.object_analyzer.registry import AnalyzerEdge, AnalyzerNode


def _node(i, ct=10, node_type="object"):
    return AnalyzerNode(
        id=f"{ct}:{i}",
        ct_id=ct,
        object_id=i,
        node_type=node_type,
        type_label="X",
        label=f"obj{i}",
        url="#",
    )


class ParseAnalyzerModeTests(SimpleTestCase):
    def test_defaults_to_all(self):
        self.assertEqual(parse_analyzer_mode(None), AnalyzerMode.ALL)
        self.assertEqual(parse_analyzer_mode(""), AnalyzerMode.ALL)
        self.assertEqual(parse_analyzer_mode("all"), AnalyzerMode.ALL)

    def test_security_mode(self):
        self.assertEqual(parse_analyzer_mode("security"), AnalyzerMode.SECURITY)


class EdgeAllowedInSecurityTests(SimpleTestCase):
    def test_denies_rule_edges(self):
        edge = AnalyzerEdge("Regel (field)", "in_rule", _node(1, node_type="rule"))
        self.assertFalse(edge_allowed_in_security(edge, frozenset({10})))

    def test_denies_cable_edge_type(self):
        edge = AnalyzerEdge("Cable", "cable", _node(2))
        self.assertFalse(edge_allowed_in_security(edge, frozenset({10})))

    def test_denies_console_port_label(self):
        edge = AnalyzerEdge("Console Port", "rev_consoleport", _node(3))
        self.assertFalse(edge_allowed_in_security(edge, frozenset({10})))

    def test_denies_label_node_type(self):
        edge = AnalyzerEdge("Member", "group_member", _node(4, node_type="label"))
        self.assertFalse(edge_allowed_in_security(edge, frozenset({10})))

    def test_allows_whitelisted_content_type(self):
        edge = AnalyzerEdge("Interface", "rev_interface", _node(5, node_type="interface"))
        self.assertTrue(edge_allowed_in_security(edge, frozenset({10})))

    def test_denies_non_whitelisted_content_type(self):
        edge = AnalyzerEdge("Interface", "rev_interface", _node(5, node_type="interface"))
        self.assertFalse(edge_allowed_in_security(edge, frozenset({99})))


class FilterEdgesForModeTests(SimpleTestCase):
    def test_all_mode_passes_through(self):
        edges = [
            AnalyzerEdge("Console Port", "rev_cp", _node(1)),
            AnalyzerEdge("Interface", "rev_if", _node(2)),
        ]
        self.assertEqual(filter_edges_for_mode(edges, AnalyzerMode.ALL), edges)

    @patch("netbox_nsm.analyzers.object_analyzer.modes.get_security_allowed_ct_ids", return_value=frozenset({10}))
    def test_security_mode_filters(self, _mock_allowed):
        edges = [
            AnalyzerEdge("Console Port", "rev_cp", _node(1, ct=10)),
            AnalyzerEdge("Interface", "rev_if", _node(2, ct=10)),
            AnalyzerEdge("Label", "rev_label", _node(3, ct=10, node_type="label")),
        ]
        filtered = filter_edges_for_mode(edges, AnalyzerMode.SECURITY)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].edge_label, "Interface")


class BuildPickerTreeModeTests(SimpleTestCase):
    def test_security_mode_filters_l1_and_l2(self):
        from netbox_nsm.analyzers.object_analyzer import picker as picker_mod

        root = MagicMock(name="root")
        child = MagicMock(name="child")
        l1 = [
            AnalyzerEdge("Interface", "if", _node(2, ct=10, node_type="interface")),
            AnalyzerEdge("Console Port", "cp", _node(3, ct=10)),
        ]
        l2 = [
            AnalyzerEdge("Console Port", "cp", _node(4, ct=10)),
            AnalyzerEdge("Linked", "nsm_link", _node(5, ct=10)),
        ]

        def filtered_edges(obj, mode):
            if obj is root:
                return l1[:1]  # security: only Interface
            if obj is child:
                return l2[1:]  # security: only Linked
            return []

        with patch("netbox_nsm.analyzers.object_analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={(10, 2): child}
        ), patch(
            "netbox_nsm.analyzers.object_analyzer.modes.get_filtered_edges", side_effect=filtered_edges
        ):
            tree = picker_mod.build_picker_tree(root, depth=2, mode="security")

        self.assertEqual(len(tree["children"]), 1)
        self.assertEqual(tree["children"][0]["edge_label"], "Interface")
        self.assertEqual(tree["children"][0]["l2_count"], 1)
        self.assertEqual(tree["children"][0]["l2"][0]["edge_label"], "Linked")


class AnalyzerApiModeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix = Prefix.objects.create(prefix="10.88.0.0/24", status="active")
        cls.ip = IPAddress.objects.create(address="10.88.0.8/24", status="active")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_analyzer_api_accepts_mode_param(self):
        from django.urls import reverse

        url = (
            reverse("plugins:netbox_nsm:analyzer_api")
            + f"?ct={self.prefix_ct.pk}&pk={self.prefix.pk}&mode=security"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)

    def test_picker_api_security_mode_returns_groups_without_console_port(self):
        from django.urls import reverse

        url = (
            reverse("plugins:netbox_nsm:analyzer_picker_api")
            + f"?ct={self.prefix_ct.pk}&pk={self.prefix.pk}&depth=1&mode=security"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        labels = {c["edge_label"] for c in data["children"]}
        self.assertIn("IP", labels)
        self.assertNotIn("Console Port", labels)

    def tearDown(self):
        clear_security_mode_cache()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        clear_security_mode_cache()
        super().tearDownClass()
