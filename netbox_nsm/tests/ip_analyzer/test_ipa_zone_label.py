"""Tests for IP Analyzer zone/label column resolution."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.analyzers.ip_analyzer.ipa_zone_label import (
    attach_ipa_cell_zone_label_refs,
    resolve_ipa_label_refs,
    resolve_ipa_zone_refs,
)


class IpaZoneLabelResolveTests(SimpleTestCase):
    def test_direct_zone_beats_inherited_lookup(self):
        ipam_obj = object()
        direct_zone = SimpleNamespace(
            custom_object_type=SimpleNamespace(slug="nsm_zone"),
            pk=1,
            get_absolute_url=lambda: "/zone/trust/",
        )
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label._direct_refs_for_roles",
            return_value=[{"name": "TRUST", "url": "/zone/trust/"}],
        ) as direct_mock:
            zones = resolve_ipa_zone_refs(ipam_obj, tmpl_map={})
        self.assertEqual(zones[0]["name"], "TRUST")
        direct_mock.assert_called_once()
        self.assertEqual(direct_mock.call_args.kwargs["roles"], {"zone"})
        self.assertTrue(direct_mock.call_args.kwargs.get("include_found_on", False))

    def test_inherited_zone_used_when_direct_missing(self):
        ipam_obj = object()
        linked = SimpleNamespace(
            custom_object_type=SimpleNamespace(slug="nsm_zone"),
            pk=2,
            get_absolute_url=lambda: "/zone/dmz/",
        )
        ancestor = SimpleNamespace(prefix="10.0.0.0/8")
        inherited = SimpleNamespace(linked=linked, ancestor=ancestor)
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label._direct_refs_for_roles",
            return_value=[],
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label._role_for_linked_object",
            return_value="zone",
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label.render_object_display",
            return_value="DMZ",
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label.ContentType.objects.get_for_model",
            return_value=SimpleNamespace(pk=99),
        ), patch(
            "ipam.models.IPAddress",
            new=type("IPAddress", (), {}),
        ), patch(
            "ipam.models.IPRange",
            new=type("IPRange", (), {}),
        ), patch(
            "ipam.models.Prefix",
            new=type("Prefix", (), {}),
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label.isinstance",
            return_value=True,
        ), patch(
            "netbox_nsm.addresses.ipam_inheritance.iter_inherited_nsm_links",
            return_value=iter([inherited]),
        ):
            zones = resolve_ipa_zone_refs(ipam_obj, tmpl_map={})
        self.assertEqual(len(zones), 1)
        self.assertTrue(zones[0]["inherited"])
        self.assertEqual(zones[0]["inherited_from"], "10.0.0.0/8")
        self.assertEqual(zones[0]["found_on_prefix"], "10.0.0.0/8")

    def test_labels_are_direct_only(self):
        ipam_obj = object()
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label._direct_refs_for_roles",
            return_value=[{"name": "R:PROD", "url": "/label/prod/"}],
        ) as direct_mock:
            labels = resolve_ipa_label_refs(ipam_obj, tmpl_map={})
        self.assertEqual(labels[0]["name"], "R:PROD")
        direct_mock.assert_called_once()
        self.assertEqual(direct_mock.call_args.kwargs["roles"], {"label"})
        self.assertTrue(direct_mock.call_args.kwargs.get("include_found_on", False))


class IpaZoneLabelAttachTests(SimpleTestCase):
    def test_attach_sets_zone_and_label_refs_on_node(self):
        ipam_obj = object()
        with patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_tree_node_is_structural",
            return_value=False,
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_object_tree_node_key",
            return_value=(1, 2),
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._ipa_cell_tree_ipam_object_for_node",
            return_value=ipam_obj,
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label.resolve_ipa_zone_label_refs",
            return_value=(
                [{"name": "TRUST", "url": "/zone/trust/"}],
                [{"name": "R:APP", "url": "/label/app/"}],
            ),
        ), patch(
            "netbox_nsm.analyzers.ip_analyzer.ipa_zone_label.get_display_template_map",
            return_value={},
        ):
            nodes = [{"name": "host-1", "children": []}]
            obj_by_key = {(1, 2): object()}
            attach_ipa_cell_zone_label_refs(nodes, obj_by_key)
        self.assertEqual(nodes[0]["zone_refs"][0]["name"], "TRUST")
        self.assertEqual(nodes[0]["label_refs"][0]["name"], "R:APP")
