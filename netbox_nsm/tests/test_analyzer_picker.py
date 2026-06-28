"""Tests for the Object Analyzer batched link-picker tree.

Covers both the pure builder (``analyzer/picker.py``) and the JSON endpoint
(``AnalyzerPickerAPIView``) that replaced the old 1+N per-child request storm
behind the "+" link picker.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase
from django.urls import reverse

from ipam.models import IPAddress, Prefix
from utilities.testing import TestCase

from netbox_nsm.analysis.analyzer import picker as picker_mod
from netbox_nsm.analysis.analyzer.registry import AnalyzerEdge, AnalyzerNode


def _node(i, ct=10):
    return AnalyzerNode(
        id=f"{ct}:{i}",
        ct_id=ct,
        object_id=i,
        node_type="object",
        type_label="X",
        label=f"obj{i}",
        url="#",
    )


class BuildPickerTreeUnitTests(SimpleTestCase):
    """Pure-Python builder behaviour (mocked registry / object resolution)."""

    def test_depth1_returns_l1_only_and_skips_bulk_resolve(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Linked", "nsm_link", _node(2)),
            AnalyzerEdge("Linked", "nsm_link", _node(3)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve"
        ) as bulk, patch(
            "netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1
        ):
            tree = picker_mod.build_picker_tree(root, depth=1)

        bulk.assert_not_called()
        self.assertEqual(len(tree["children"]), 2)
        self.assertNotIn("l2", tree["children"][0])
        self.assertEqual(tree["node"]["id"], "10:1")

    def test_mode_all_uses_get_filtered_edges(self):
        root = MagicMock(name="root")
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch(
            "netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=[]
        ) as get_edges:
            picker_mod.build_picker_tree(root, depth=1, mode="all")
        get_edges.assert_called_once()
        self.assertEqual(get_edges.call_args[0][0], root)
        self.assertEqual(get_edges.call_args[0][1].value, "all")

    def test_depth2_embeds_l2_and_dedupes_targets(self):
        root = MagicMock(name="root")
        child2 = MagicMock(name="child2")
        child3 = MagicMock(name="child3")
        l1 = [
            AnalyzerEdge("Linked", "nsm_link", _node(2)),
            AnalyzerEdge("Linked", "nsm_link", _node(3)),
        ]
        # child2 has two edges to the SAME target id -> deduped to one
        l2_for_2 = [
            AnalyzerEdge("A", "a", _node(9)),
            AnalyzerEdge("B", "b", _node(9)),
        ]
        l2_for_3 = [AnalyzerEdge("C", "c", _node(8))]

        def edges_side_effect(obj, mode):
            if obj is root:
                return l1
            if obj is child2:
                return l2_for_2
            if obj is child3:
                return l2_for_3
            return []

        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod,
            "_bulk_resolve",
            return_value={(10, 2): child2, (10, 3): child3},
        ), patch(
            "netbox_nsm.analysis.analyzer.modes.get_filtered_edges", side_effect=edges_side_effect
        ):
            tree = picker_mod.build_picker_tree(root, depth=2)

        kids = tree["children"]
        self.assertEqual(kids[0]["l2_count"], 1)
        self.assertEqual(len(kids[0]["l2"]), 1)
        self.assertEqual(kids[1]["l2_count"], 1)

    def test_depth2_unresolved_child_yields_empty_l2(self):
        root = MagicMock(name="root")
        l1 = [AnalyzerEdge("Linked", "nsm_link", _node(2))]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=2)

        self.assertEqual(tree["children"][0]["l2_count"], 0)
        self.assertEqual(tree["children"][0]["l2"], [])

    def test_l1_targets_deduplicated(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Linked", "nsm_link", _node(2)),
            AnalyzerEdge("Other", "other", _node(2)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        self.assertEqual(len(tree["children"]), 1)

    def test_groups_by_edge_label(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Cable Termination", "rev_a", _node(2)),
            AnalyzerEdge("Cable Termination", "rev_b", _node(3)),
            AnalyzerEdge("Interface", "rev_c", _node(4)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        self.assertIn("groups", tree)
        self.assertEqual(len(tree["groups"]), 2)
        by_key = {g["key"]: g for g in tree["groups"]}
        self.assertIn("cable_termination", by_key)
        self.assertIn("interface", by_key)
        self.assertEqual(len(by_key["cable_termination"]["items"]), 2)
        self.assertEqual(len(by_key["interface"]["items"]), 1)
        self.assertEqual(by_key["cable_termination"]["label"], "Cable Termination")

    def test_groups_sorted_alphabetically(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Interface", "a", _node(2)),
            AnalyzerEdge("Console Port", "b", _node(3)),
            AnalyzerEdge("Cable Termination", "c", _node(4)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        labels = [g["label"] for g in tree["groups"]]
        self.assertEqual(labels, sorted(labels, key=str.lower))

    def test_group_items_sorted_by_node_label(self):
        root = MagicMock(name="root")

        def _node_with_label(i, label):
            return AnalyzerNode(
                id=f"10:{i}", ct_id=10, object_id=i, node_type="object",
                type_label="X", label=label, url="#",
            )

        l1 = [
            AnalyzerEdge("Interface", "a", _node_with_label(2, "zebra")),
            AnalyzerEdge("Interface", "b", _node_with_label(3, "alpha")),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        labels = [c["node"]["label"] for c in tree["groups"][0]["items"]]
        self.assertEqual(labels, ["alpha", "zebra"])

    def test_children_remain_flat_for_compat(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Interface", "a", _node(2)),
            AnalyzerEdge("Console Port", "b", _node(3)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        self.assertEqual(len(tree["children"]), 2)
        self.assertEqual(
            {c["edge_label"] for c in tree["children"]},
            {"Interface", "Console Port"},
        )


class AnalyzerPickerApiViewTests(TestCase):
    """Endpoint wiring + payload shape against real IPAM objects."""

    @classmethod
    def setUpTestData(cls):
        cls.prefix = Prefix.objects.create(prefix="10.77.0.0/24", status="active")
        cls.ip = IPAddress.objects.create(address="10.77.0.5/24", status="active")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def _url(self, **params):
        base = reverse("plugins:netbox_nsm:analyzer_picker_api")
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query}" if query else base

    def test_missing_ct_pk_returns_400(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 400)

    def test_depth1_returns_l1_without_l2(self):
        url = self._url(ct=self.prefix_ct.pk, pk=self.prefix.pk, depth=1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertIn("children", data)
        self.assertTrue(data["children"])
        for child in data["children"]:
            self.assertNotIn("l2", child)
        ip_ids = {c["node"]["object_id"] for c in data["children"]}
        self.assertIn(self.ip.pk, ip_ids)

    def test_depth2_embeds_l2_counts(self):
        url = self._url(ct=self.prefix_ct.pk, pk=self.prefix.pk, depth=2)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertTrue(data["children"])
        for child in data["children"]:
            self.assertIn("l2", child)
            self.assertIn("l2_count", child)
            self.assertEqual(child["l2_count"], len(child["l2"]))

    def test_response_includes_groups(self):
        url = self._url(ct=self.prefix_ct.pk, pk=self.prefix.pk, depth=1)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertIn("groups", data)
        self.assertIsInstance(data["groups"], list)
        total_in_groups = sum(len(g["items"]) for g in data["groups"])
        self.assertEqual(total_in_groups, len(data["children"]))
        for group in data["groups"]:
            self.assertIn("key", group)
            self.assertIn("label", group)
            self.assertIn("items", group)


class PickerGroupSelectionTests(SimpleTestCase):
    """Pure selection helpers mirrored by the link-picker frontend."""

    def _group(self, key, *node_ids):
        return {
            "key": key,
            "label": key.replace("_", " ").title(),
            "items": [{"node": {"id": nid}} for nid in node_ids],
        }

    def test_l1_row_key_format(self):
        self.assertEqual(picker_mod.picker_l1_row_key(42), "l1:42")
        self.assertEqual(picker_mod.picker_l1_row_key("10:5"), "l1:10:5")

    def test_l1_keys_for_group(self):
        group = self._group("cable_termination", 2, 3)
        self.assertEqual(
            picker_mod.picker_l1_keys_for_group(group),
            ["l1:2", "l1:3"],
        )

    def test_group_check_state_none_partial_all(self):
        keys = ["l1:1", "l1:2", "l1:3"]
        self.assertEqual(picker_mod.picker_group_check_state(set(), keys), "none")
        self.assertEqual(
            picker_mod.picker_group_check_state({"l1:2"}, keys),
            "partial",
        )
        self.assertEqual(
            picker_mod.picker_group_check_state(set(keys), keys),
            "all",
        )

    def test_toggle_group_selects_and_clears_all_members(self):
        keys = ["l1:1", "l1:2"]
        checked = picker_mod.picker_toggle_group(set(), keys, True)
        self.assertEqual(checked, {"l1:1", "l1:2"})
        checked = picker_mod.picker_toggle_group(checked, keys, False)
        self.assertEqual(checked, set())

    def test_toggle_group_leaves_other_groups_unchanged(self):
        keys_a = ["l1:1", "l1:2"]
        keys_b = ["l1:3"]
        checked = {"l1:3", "l1:99"}
        checked = picker_mod.picker_toggle_group(checked, keys_a, True)
        self.assertEqual(checked, {"l1:1", "l1:2", "l1:3", "l1:99"})
        checked = picker_mod.picker_toggle_group(checked, keys_b, False)
        self.assertEqual(checked, {"l1:1", "l1:2", "l1:99"})

    def test_sync_all_checkbox(self):
        all_keys = ["l1:1", "l1:2"]
        checked = picker_mod.picker_sync_all_checkbox({"l1:1", "l1:2"}, all_keys)
        self.assertIn("__all__", checked)
        checked = picker_mod.picker_sync_all_checkbox({"l1:1"}, all_keys)
        self.assertNotIn("__all__", checked)

    def test_group_keys_from_build_picker_tree_groups(self):
        root = MagicMock(name="root")
        l1 = [
            AnalyzerEdge("Cable Termination", "a", _node(2)),
            AnalyzerEdge("Cable Termination", "b", _node(3)),
            AnalyzerEdge("Interface", "c", _node(4)),
        ]
        with patch("netbox_nsm.analysis.analyzer.node_from_object", return_value=_node(1)), patch.object(
            picker_mod, "_bulk_resolve", return_value={}
        ), patch("netbox_nsm.analysis.analyzer.modes.get_filtered_edges", return_value=l1):
            tree = picker_mod.build_picker_tree(root, depth=1)

        by_key = {g["key"]: g for g in tree["groups"]}
        cable_keys = picker_mod.picker_l1_keys_for_group(by_key["cable_termination"])
        self.assertEqual(cable_keys, ["l1:10:2", "l1:10:3"])
        checked = picker_mod.picker_toggle_group(set(), cable_keys, True)
        self.assertEqual(picker_mod.picker_group_check_state(checked, cable_keys), "all")
        self.assertEqual(
            picker_mod.picker_group_check_state(checked, picker_mod.picker_l1_keys_for_group(by_key["interface"])),
            "none",
        )


class PickerCanvasFilterTests(SimpleTestCase):
    """Hide picker rows when parent→target edge is already on canvas."""

    def _child(self, node_id, edge_label="Linked", l2=None):
        payload = {
            "edge_label": edge_label,
            "edge_type": "nsm_link",
            "node": {"id": node_id, "label": f"obj{node_id}"},
        }
        if l2 is not None:
            payload["l2"] = l2
            payload["l2_count"] = len(l2)
        return payload

    def test_edge_cases_l1_existing_edge(self):
        children = [
            self._child("10:2"),
            self._child("10:3"),
            self._child("10:4"),
        ]
        existing = {picker_mod.picker_edge_key("10:1", "10:3")}
        filtered = picker_mod.filter_picker_children_for_canvas(children, "10:1", existing)
        self.assertEqual([c["node"]["id"] for c in filtered], ["10:2", "10:4"])

    def test_keeps_other_parent_edges_when_target_visible_elsewhere(self):
        """Target on canvas via another parent must not hide the row."""
        children = [self._child("10:5")]
        existing = {picker_mod.picker_edge_key("10:99", "10:5")}
        filtered = picker_mod.filter_picker_children_for_canvas(children, "10:1", existing)
        self.assertEqual(len(filtered), 1)

    def test_filter_l2_embedded_links(self):
        l2_keep = self._child("10:8", edge_label="Interface")
        l2_drop = self._child("10:9", edge_label="Interface")
        children = [
            self._child(
                "10:2",
                l2=[l2_keep, l2_drop],
            ),
        ]
        existing = {picker_mod.picker_edge_key("10:2", "10:9")}
        filtered = picker_mod.filter_picker_children_for_canvas(children, "10:1", existing)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(len(filtered[0]["l2"]), 1)
        self.assertEqual(filtered[0]["l2"][0]["node"]["id"], "10:8")
        self.assertEqual(filtered[0]["l2_count"], 1)

    def test_filter_l2_hides_reverse_canvas_edge(self):
        """L2 row hidden when only target→parent exists on canvas (e.g. Device→Interface)."""
        l2_device = self._child("10:99", edge_label="Device")
        children = [self._child("10:2", edge_label="Interface", l2=[l2_device])]
        existing = {picker_mod.picker_edge_key("10:99", "10:2")}
        filtered = picker_mod.filter_picker_children_for_canvas(children, "10:1", existing)
        self.assertEqual(filtered[0]["l2"], [])
        self.assertEqual(filtered[0]["l2_count"], 0)

    def test_picker_edge_exists_on_canvas_bidirectional(self):
        existing = {picker_mod.picker_edge_key("10:5", "10:9")}
        self.assertTrue(picker_mod.picker_edge_exists_on_canvas("10:9", "10:5", existing))
        self.assertTrue(picker_mod.picker_edge_exists_on_canvas("10:5", "10:9", existing))
        self.assertFalse(picker_mod.picker_edge_exists_on_canvas("10:1", "10:9", existing))

    def test_filter_tree_rebuilds_groups_and_counts(self):
        tree = {
            "node": {"id": "10:1"},
            "children": [
                self._child("10:2", edge_label="Interface"),
                self._child("10:3", edge_label="Interface"),
                self._child("10:4", edge_label="Cable Termination"),
            ],
            "groups": [],
        }
        existing = {picker_mod.picker_edge_key("10:1", "10:3")}
        out = picker_mod.filter_picker_tree_for_canvas(tree, "10:1", existing)
        self.assertEqual([c["node"]["id"] for c in out["children"]], ["10:2", "10:4"])
        iface = next(g for g in out["groups"] if g["key"] == "interface")
        self.assertEqual(len(iface["items"]), 1)
        self.assertEqual(iface["items"][0]["node"]["id"], "10:2")

    def test_filter_l2_hides_parent_linked_neighbor(self):
        """L2 row hidden when target is already a direct neighbor of the parent."""
        l2_device = self._child("10:99", edge_label="Device")
        l2_keep = self._child("10:8", edge_label="IP")
        children = [
            self._child(
                "10:2",
                edge_label="Interface",
                l2=[l2_device, l2_keep],
            ),
        ]
        filtered = picker_mod.filter_picker_children_for_canvas(
            children,
            "10:1",
            set(),
            linked_neighbor_ids=frozenset({"10:99"}),
        )
        self.assertEqual(len(filtered[0]["l2"]), 1)
        self.assertEqual(filtered[0]["l2"][0]["node"]["id"], "10:8")
        self.assertEqual(filtered[0]["l2_count"], 1)

    def test_filter_tree_uses_linked_neighbor_ids_from_payload(self):
        tree = {
            "node": {"id": "10:1"},
            "linked_neighbor_ids": ["10:99"],
            "children": [
                self._child(
                    "10:2",
                    l2=[self._child("10:99"), self._child("10:8")],
                ),
            ],
            "groups": [],
        }
        out = picker_mod.filter_picker_tree_for_canvas(tree, "10:1", set())
        self.assertEqual([c["node"]["id"] for c in out["children"][0]["l2"]], ["10:8"])


class PickerAlreadyLinkedFilterTests(SimpleTestCase):
    """Hide picker targets already linked in NetBox (not only on canvas)."""

    def _node(self, i, ct=10):
        return AnalyzerNode(
            id=f"{ct}:{i}",
            ct_id=ct,
            object_id=i,
            node_type="object",
            type_label="X",
            label=f"obj{i}",
            url="#",
        )

    def test_interface_hides_parent_device(self):
        device = MagicMock(name="device", pk=99)
        iface = MagicMock(name="iface", pk=2)
        iface._meta.label_lower = "dcim.interface"
        iface.device = device
        edges = [
            AnalyzerEdge("Device", "device", self._node(99, ct=11)),
            AnalyzerEdge("Connected to", "connected_endpoint", self._node(8)),
        ]
        with patch(
            "netbox_nsm.analysis.analyzer.node_from_object",
            side_effect=lambda o: self._node(o.pk, ct=11 if o is device else 10),
        ):
            filtered = picker_mod.filter_already_linked_picker_edges(iface, edges)
        self.assertEqual([e.node.object_id for e in filtered], [8])

    def test_vm_interface_hides_parent_vm(self):
        vm = MagicMock(name="vm", pk=7)
        iface = MagicMock(name="vminterface", pk=3)
        iface._meta.label_lower = "virtualization.vminterface"
        iface.virtual_machine = vm
        edges = [AnalyzerEdge("Virtual Machine", "virtual_machine", self._node(7, ct=12))]
        with patch(
            "netbox_nsm.analysis.analyzer.node_from_object",
            side_effect=lambda o: self._node(o.pk, ct=12),
        ):
            filtered = picker_mod.filter_already_linked_picker_edges(iface, edges)
        self.assertEqual(filtered, [])

    def test_ip_address_hides_assigned_object(self):
        iface = MagicMock(name="iface", pk=5)
        ip = MagicMock(name="ip", pk=1)
        ip.assigned_object = iface
        edges = [
            AnalyzerEdge("Assigned to", "assigned_to", self._node(5)),
            AnalyzerEdge("Subnet", "in_prefix", self._node(9)),
        ]
        with patch(
            "netbox_nsm.analysis.analyzer.node_from_object",
            side_effect=lambda o: self._node(o.pk),
        ):
            filtered = picker_mod.filter_already_linked_picker_edges(ip, edges)
        self.assertEqual([e.node.object_id for e in filtered], [9])

    def test_build_picker_tree_filters_l2_parent_device(self):
        root = MagicMock(name="root")
        child_iface = MagicMock(name="child_iface", pk=2)
        child_iface._meta.label_lower = "dcim.interface"
        device = MagicMock(name="device", pk=99)
        child_iface.device = device
        l1 = [AnalyzerEdge("Interface", "rev_interfaces", self._node(2))]
        l2_for_iface = [
            AnalyzerEdge("Device", "device", self._node(99, ct=11)),
            AnalyzerEdge("IP", "rev_ip", self._node(8)),
        ]

        def edges_side_effect(obj, mode):
            if obj is root:
                return l1
            if obj is child_iface:
                return l2_for_iface
            return []

        with patch(
            "netbox_nsm.analysis.analyzer.node_from_object",
            side_effect=lambda o: self._node(1)
            if o is root
            else self._node(o.pk, ct=11 if getattr(o, "pk", None) == 99 else 10),
        ), patch.object(
            picker_mod,
            "_bulk_resolve",
            return_value={(10, 2): child_iface},
        ), patch(
            "netbox_nsm.analysis.analyzer.modes.get_filtered_edges", side_effect=edges_side_effect
        ):
            tree = picker_mod.build_picker_tree(root, depth=2)

        l2 = tree["children"][0]["l2"]
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0]["node"]["object_id"], 8)
        self.assertEqual(tree["children"][0]["l2_count"], 1)

    def test_build_picker_tree_filters_l2_root_parent_device(self):
        """When root is an interface, L2 must not repeat its parent device."""
        device = MagicMock(name="device", pk=99)
        root_iface = MagicMock(name="root_iface", pk=1)
        root_iface._meta.label_lower = "dcim.interface"
        root_iface.device = device
        peer_iface = MagicMock(name="peer_iface", pk=2)
        peer_iface._meta.label_lower = "dcim.interface"
        peer_iface.device = device
        l1 = [
            AnalyzerEdge("Connected to", "connected_endpoint", self._node(2)),
            AnalyzerEdge("Device", "device", self._node(99, ct=11)),
        ]
        l2_for_peer = [
            AnalyzerEdge("Device", "device", self._node(99, ct=11)),
            AnalyzerEdge("IP", "rev_ip", self._node(8)),
        ]

        def edges_side_effect(obj, mode):
            if obj is root_iface:
                return l1
            if obj is peer_iface:
                return l2_for_peer
            return []

        with patch(
            "netbox_nsm.analysis.analyzer.node_from_object",
            side_effect=lambda o: self._node(1)
            if o is root_iface
            else self._node(o.pk, ct=11 if getattr(o, "pk", None) == 99 else 10),
        ), patch.object(
            picker_mod,
            "_bulk_resolve",
            return_value={(10, 2): peer_iface},
        ), patch(
            "netbox_nsm.analysis.analyzer.modes.get_filtered_edges", side_effect=edges_side_effect
        ):
            tree = picker_mod.build_picker_tree(root_iface, depth=2)

        self.assertIn("11:99", tree["linked_neighbor_ids"])
        self.assertEqual(
            [c["node"]["object_id"] for c in tree["children"]],
            [2],
        )
        l2 = tree["children"][0]["l2"]
        self.assertEqual(len(l2), 1)
        self.assertEqual(l2[0]["node"]["object_id"], 8)
        self.assertEqual(tree["children"][0]["l2_count"], 1)
