"""Tests for IP Analyzer applet helpers."""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.models.type_config import MatchingClassChoices
from netbox_nsm.rulebook_rules_cell_html import (
    render_rules_cell_ag as _render_rules_cell_ag,
)
from netbox_nsm.views.rulebook import (
    _build_addr_tree_node,
    _build_multi_object_addr_analysis,
    _collect_ipam_prefix_children,
    _object_is_addr_analyzable,
    _object_supports_addr_analysis,
    ipa_loupe_button_html,
)

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class ObjectIsAddrAnalyzableTests(SimpleTestCase):
    def test_nsm_object_requires_address_matching_class(self):
        addr = MagicMock()
        addr._meta.app_label = "netbox_custom_objects"
        addr._meta.model_name = "table1model"
        mc = {42: MatchingClassChoices.ZONE}
        self.assertFalse(_object_is_addr_analyzable(addr, 42, mc))

    @patch(
        "netbox_nsm.views.rulebook._object_supports_addr_analysis", return_value=True
    )
    def test_true_for_address_class(self, _supports):
        prefix = MagicMock()
        mc = {7: MatchingClassChoices.ADDRESS}
        self.assertTrue(_object_is_addr_analyzable(prefix, 7, mc))

    def test_ipam_prefix_analyzable_without_typeconfig(self):
        prefix = MagicMock()
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        self.assertTrue(_object_supports_addr_analysis(prefix))
        self.assertTrue(_object_is_addr_analyzable(prefix, 14, {}))


class IpamPrefixTreeTests(SimpleTestCase):
    @patch("netbox_nsm.views.rulebook._addr_is_group_container", return_value=False)
    @patch("netbox_nsm.views.rulebook._addr_ip_ref")
    @patch("netbox_nsm.views.rulebook._collect_ipam_prefix_children")
    def test_prefix_expands_to_linked_address_child(
        self, collect_children, ip_ref_fn, _group_container
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix._meta.app_label = "ipam"
        prefix._meta.model_name = "prefix"
        prefix.prefix = "10.245.10.0/24"
        prefix.__str__ = lambda self: "10.245.10.0/24"
        prefix.get_absolute_url.return_value = "/ipam/prefixes/5/"

        addr = MagicMock()
        addr.pk = 10
        addr.name = "demo-addr-0010"
        addr._meta.app_label = "netbox_custom_objects"
        addr._meta.model_name = "table1model"
        addr.get_absolute_url.return_value = "/custom-objects/10/"
        collect_children.return_value = [addr]

        def _ip_ref_side_effect(obj):
            if getattr(obj, "name", None) == "demo-addr-0010":
                return {
                    "str": "10.245.10.0/24",
                    "url": "/ipam/prefixes/5/",
                    "type": "Prefix",
                }
            return None

        ip_ref_fn.side_effect = _ip_ref_side_effect

        node = _build_addr_tree_node(prefix)

        self.assertIsNotNone(node)
        self.assertEqual(node["kind"], "group")
        self.assertEqual(len(node["children"]), 1)
        self.assertEqual(node["children"][0]["name"], "demo-addr-0010")

        analysis = _build_multi_object_addr_analysis([prefix])
        self.assertEqual(analysis[0]["types"][0]["leaf_count"], 1)

    @patch("netbox_nsm.address_ipam_fk.get_nsm_address_model")
    @patch("ipam.models.IPRange.objects")
    @patch("ipam.models.IPAddress.objects")
    @patch("ipam.models.Prefix.objects")
    def test_collect_ipam_prefix_children_queries_all_kinds(
        self, prefix_qs, ip_qs, range_qs, addr_model_fn
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix.prefix = "10.245.10.0/24"

        child_prefix = MagicMock()
        ip = MagicMock()
        rng = MagicMock()
        addr = MagicMock()

        prefix_qs.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = [
            child_prefix
        ]
        ip_qs.filter.return_value.order_by.return_value.__getitem__.return_value = [ip]
        range_qs.filter.return_value.order_by.return_value.__getitem__.return_value = [
            rng
        ]

        addr_model = MagicMock()
        addr_model.objects.filter.return_value.order_by.return_value.__getitem__.return_value = [
            addr
        ]
        addr_model_fn.return_value = addr_model

        children = _collect_ipam_prefix_children(prefix)

        self.assertEqual(children, [child_prefix, ip, rng, addr])


class RulesCellLoupeTests(SimpleTestCase):
    def test_cell_loupe_once_for_analyzable_objects(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                }
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertIn("nsm-ipa-cell-loupe", html)
        self.assertIn('data-addr-analyzable="1"', html)
        loupe_tag = re.search(r"<button[^>]*nsm-ipa-cell-loupe[^>]*>", html)
        self.assertIsNotNone(loupe_tag)
        self.assertNotIn("data-ct", loupe_tag.group(0))

    def test_cell_loupe_collects_all_objects_in_cell(self):
        html = _render_rules_cell_ag(
            [
                {
                    "url": "/a/1/",
                    "name": "net-a",
                    "color": "",
                    "ct": 1,
                    "pk": 2,
                    "addrAnalyzable": True,
                },
                {
                    "url": "/a/2/",
                    "name": "net-b",
                    "color": "",
                    "ct": 1,
                    "pk": 3,
                    "addrAnalyzable": True,
                },
            ]
        )
        self.assertEqual(html.count("nsm-ipa-loupe"), 1)
        self.assertEqual(html.count('data-addr-analyzable="1"'), 2)

    def test_cell_loupe_skipped_for_non_analyzable_object(self):
        html = _render_rules_cell_ag(
            [{"url": "/a/1/", "name": "net-a", "color": "", "ct": 1, "pk": 2}]
        )
        self.assertNotIn("nsm-ipa-loupe", html)

    def test_ipa_loupe_button_html_includes_identity(self):
        html = ipa_loupe_button_html(
            ct=5, pk=9, name="demo", title="Objekt analysieren"
        )
        self.assertIn('data-ct="5"', html)
        self.assertIn('data-pk="9"', html)
        self.assertIn("Objekt analysieren", html)


class IpAnalyzerMergeAssetsTests(SimpleTestCase):
    """Static checks for multi-tab Merge in the floating applet."""

    def test_applet_js_exposes_merge_ui(self):
        js = (_PLUGIN_ROOT / "plugin_assets/js/nsm_ip_analyzer_applet.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("nsm-ipa-applet-merge", js)
        self.assertIn("mergeTabs", js)
        self.assertIn("collectObjectsFromTabs", js)
        self.assertIn("Merged (", js)

    def test_applet_assets_cache_bust_bumped(self):
        assets = (
            _PLUGIN_ROOT / "templates/netbox_nsm/inc/nsm_ip_analyzer_applet_assets.html"
        ).read_text(encoding="utf-8")
        self.assertIn("nsm_ip_analyzer_applet.js", assets)
        self.assertIn("?v=202606073", assets)
