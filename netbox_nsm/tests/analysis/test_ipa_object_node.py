"""Tests for IP Analyzer object-tree presentation roles."""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analysis.addr_constants import FIELD_TYPE_LABELS
from netbox_nsm.objects.address_literal import format_network_nsm_config_comments
from netbox_nsm.analysis.ipa_object_node import (
    IPA_NODE_ROLE_GROUP,
    IPA_NODE_ROLE_HOST,
    IPA_NODE_ROLE_PREFIX,
    IPA_NODE_ROLE_RANGE,
    _ipa_object_node_apply_presentation,
    _ipa_object_node_presentation,
    _ipa_object_node_role_from_cidr_hint,
    _ipa_object_node_role_from_ip_ref,
    _ipa_object_node_role_from_obj,
    _ipa_object_node_should_drilldown,
)


class IpaObjectNodeRoleTests(SimpleTestCase):
    def test_role_from_ip_ref(self):
        self.assertEqual(
            _ipa_object_node_role_from_ip_ref({"type": FIELD_TYPE_LABELS["prefix"]}),
            IPA_NODE_ROLE_PREFIX,
        )
        self.assertEqual(
            _ipa_object_node_role_from_ip_ref({"type": FIELD_TYPE_LABELS["range"]}),
            IPA_NODE_ROLE_RANGE,
        )
        self.assertEqual(
            _ipa_object_node_role_from_ip_ref(
                {"type": FIELD_TYPE_LABELS["ip_address"]}
            ),
            IPA_NODE_ROLE_HOST,
        )

    def test_role_from_ip_ref_infers_prefix_without_type(self):
        self.assertEqual(
            _ipa_object_node_role_from_ip_ref({"str": "10.0.0.0/8"}),
            IPA_NODE_ROLE_PREFIX,
        )

    def test_role_from_cidr_hint_classifies_ipv6(self):
        self.assertEqual(
            _ipa_object_node_role_from_cidr_hint("2001:db8::/48"),
            IPA_NODE_ROLE_PREFIX,
        )
        self.assertEqual(
            _ipa_object_node_role_from_cidr_hint("2001:db8::1/128"),
            IPA_NODE_ROLE_HOST,
        )

    def test_role_from_cidr_hint_classifies_ipv4(self):
        self.assertEqual(
            _ipa_object_node_role_from_cidr_hint("10.0.0.0/24"),
            IPA_NODE_ROLE_PREFIX,
        )
        self.assertEqual(
            _ipa_object_node_role_from_cidr_hint("10.0.0.1/32"),
            IPA_NODE_ROLE_HOST,
        )

    @patch("netbox_nsm.analysis.ipa_object_node._hub._ipam_obj_from_ip_ref")
    def test_role_from_polymorphic_address_ref_resolves_prefix(self, ipam_fn):
        prefix = MagicMock()
        prefix._meta = MagicMock(app_label="ipam", model_name="prefix")
        ipam_fn.return_value = prefix
        with patch(
            "netbox_nsm.analysis.ipa_object_node._ipa_object_node_role_from_ipam_obj",
            return_value=IPA_NODE_ROLE_PREFIX,
        ):
            self.assertEqual(
                _ipa_object_node_role_from_ip_ref(
                    {
                        "str": "198.18.0.0/24",
                        "type": "Address",
                        "ct": 70,
                        "pk": 96,
                    }
                ),
                IPA_NODE_ROLE_PREFIX,
            )

    @patch("netbox_nsm.analysis.ipa_object_node._hub._addr_ip_ref", return_value=None)
    def test_role_from_literal_any_network(self, _ip_ref):
        obj = MagicMock()
        obj.comments = format_network_nsm_config_comments("0.0.0.0/0").rstrip()
        self.assertEqual(_ipa_object_node_role_from_obj(obj), IPA_NODE_ROLE_PREFIX)
        self.assertEqual(
            _ipa_object_node_role_from_ip_ref({"str": "10.0.0.1/32"}),
            IPA_NODE_ROLE_HOST,
        )

    def test_should_drilldown_prefix_node_without_type(self):
        node = {
            "kind": "group",
            "ip_ref": {"str": "10.0.0.0/8", "url": "#"},
        }
        self.assertTrue(_ipa_object_node_should_drilldown(node))

    def test_presentation_prefix_is_expandable_group(self):
        hints = _ipa_object_node_presentation(IPA_NODE_ROLE_PREFIX)
        self.assertEqual(hints["kind"], "group")
        self.assertTrue(hints["drilldown"])

    def test_presentation_host_is_leaf(self):
        hints = _ipa_object_node_presentation(IPA_NODE_ROLE_HOST)
        self.assertEqual(hints["kind"], "leaf")
        self.assertFalse(hints["drilldown"])

    @patch("netbox_nsm.analysis.ipa_object_node._hub._addr_ip_ref")
    def test_apply_presentation_prefix_node(self, ip_ref_fn):
        ip_ref_fn.return_value = {
            "str": "10.1.0.0/16",
            "url": "/ipam/prefixes/1/",
            "type": FIELD_TYPE_LABELS["prefix"],
            "ct": 14,
            "pk": 1,
        }
        obj = MagicMock()
        node = {"name": "dm-addr", "url": "#", "ct": "10", "pk": "5", "children": []}
        with patch(
            "netbox_nsm.analysis.ipa_object_node._hub._addr_ip_ref_node_dict",
            side_effect=lambda r: dict(r),
        ), patch(
            "netbox_nsm.analysis.ipa_object_node._hub._attach_addr_node_prefix_display",
            side_effect=lambda n, **k: n,
        ):
            _ipa_object_node_apply_presentation(node, obj)
        self.assertEqual(node["node_role"], IPA_NODE_ROLE_PREFIX)
        self.assertEqual(node["kind"], "group")

    def test_should_drilldown_prefix_node_with_ip_ref(self):
        node = {
            "node_role": IPA_NODE_ROLE_PREFIX,
            "kind": "group",
            "ip_ref": {"str": "10.0.0.0/8", "type": FIELD_TYPE_LABELS["prefix"]},
        }
        self.assertTrue(_ipa_object_node_should_drilldown(node))

    def test_should_not_drilldown_host_leaf(self):
        node = {
            "node_role": IPA_NODE_ROLE_HOST,
            "kind": "leaf",
            "ip_ref": {"str": "10.0.0.1/32", "type": FIELD_TYPE_LABELS["ip_address"]},
        }
        self.assertFalse(_ipa_object_node_should_drilldown(node))


class IpaNestedGroupTreeTests(SimpleTestCase):
    @patch("django.contrib.contenttypes.models.ContentType")
    @patch("netbox_nsm.analysis.addr_analysis_utils._attach_ipa_object_tree_ipam_stats")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_group_members")
    def test_nested_groups_assign_group_depth_and_expand_members(
        self, members_fn, ip_ref_fn, _stats_fn, content_type_cls
    ):
        from netbox_nsm.analysis.addr_analysis_utils import _build_ipa_cell_object_tree

        ct = MagicMock()
        ct.pk = 10
        content_type_cls.objects.get_for_model.return_value = ct
        ip_ref_fn.return_value = None

        inner_member = MagicMock()
        inner_member.pk = 3
        inner_member.name = "dm-addr-inner"
        inner_member.get_absolute_url.return_value = "/a/3/"
        inner_member.address_type = None

        inner_group = MagicMock()
        inner_group.pk = 2
        inner_group.name = "dm-grp-inner"
        inner_group.get_absolute_url.return_value = "/g/2/"
        inner_group.address_type = "address-group"

        outer_group = MagicMock()
        outer_group.pk = 1
        outer_group.name = "dm-grp-outer"
        outer_group.get_absolute_url.return_value = "/g/1/"
        outer_group.address_type = "address-group"

        members_fn.side_effect = lambda obj: {
            outer_group: [inner_group],
            inner_group: [inner_member],
        }.get(obj, [])

        raw = [{"ct": "10", "pk": "1", "name": "dm-grp-outer"}]
        nodes = _build_ipa_cell_object_tree(raw, {(10, 1): outer_group})

        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["name"], "dm-addr-inner")
        self.assertEqual(
            [g["name"] for g in nodes[0].get("cell_groups") or []],
            ["dm-grp-outer", "dm-grp-inner"],
        )
