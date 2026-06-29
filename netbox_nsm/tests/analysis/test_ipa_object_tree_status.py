"""IPA object tree attaches NSM object status to cell pill refs."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip.ipa_object_tree import (
    _attach_ipa_dup_cell_statuses,
    _attach_ipa_object_tree_status,
    _build_ipa_cell_flat_address_node,
    _collect_ipa_dup_cell_statuses,
)


class IpaObjectTreeStatusTests(SimpleTestCase):
    def test_flat_address_node_carries_deprecated_status(self):
        obj = SimpleNamespace(
            pk=7,
            name="dm-addr-10-112-129-0-24",
            status="deprecated",
            get_absolute_url=lambda: "/a/7/",
            _meta=MagicMock(app_label="custom_objects", model_name="nsm_address"),
        )
        obj._meta.get_field = MagicMock(return_value=MagicMock())

        node = _build_ipa_cell_flat_address_node(obj, ct_id=10)
        self.assertEqual(node.get("status"), "deprecated")

    def test_attach_status_enriches_cell_groups(self):
        grp = SimpleNamespace(
            pk=14,
            name="dm-grp-014",
            status="reserved",
            get_absolute_url=lambda: "/g/14/",
            _meta=MagicMock(app_label="custom_objects", model_name="nsm_address_group"),
        )
        grp._meta.get_field = MagicMock(return_value=MagicMock())
        obj_by_key = {(11, 14): grp}
        nodes = [
            {
                "name": "dm-addr-10-112-134-0-24",
                "url": "/a/1/",
                "ct": "10",
                "pk": "1",
                "kind": "leaf",
                "cell_groups": [
                    {"name": "dm-grp-014", "url": "/g/14/"},
                ],
                "children": [],
            }
        ]
        _attach_ipa_object_tree_status(nodes, obj_by_key)
        self.assertEqual(nodes[0]["cell_groups"][0]["status"], "reserved")

    def test_collect_dup_cell_statuses_from_row_and_refs(self):
        node = {
            "status": "deprecated",
            "cell_address_primary": {"status": "deprecated"},
            "cell_addresses": [{"status": "reserved"}],
            "cell_groups": [
                {"name": "g1", "status": "reserved"},
                {"name": "none", "is_none": True, "status": "deprecated"},
            ],
        }
        self.assertEqual(
            _collect_ipa_dup_cell_statuses(node),
            ["deprecated", "reserved"],
        )

    def test_attach_dup_cell_statuses_sets_node_field(self):
        nodes = [
            {
                "name": "old-addr",
                "status": "deprecated",
                "children": [
                    {"name": "active-addr", "children": []},
                ],
            }
        ]
        _attach_ipa_dup_cell_statuses(nodes)
        self.assertEqual(nodes[0]["dup_cell_statuses"], ["deprecated"])
        self.assertNotIn("dup_cell_statuses", nodes[0]["children"][0])
