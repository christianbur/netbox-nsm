"""Tests for Security Panel enforcement-point section builder."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.enforcement_point_panel import build_enforcement_point_panel


def _host(*, pk=42):
    host = SimpleNamespace(pk=pk)
    host._meta = SimpleNamespace(label_lower="dcim.device")
    host.get_absolute_url = lambda: f"/dcim/devices/{pk}/"
    return host


def _iface(*, pk=7, host=None):
    iface = SimpleNamespace(pk=pk, device=host or _host())
    iface._meta = SimpleNamespace(label_lower="dcim.interface")
    return iface


class BuildEnforcementPointPanelTests(SimpleTestCase):
    @patch("netbox_nsm.security.enforcement_point_panel.iter_rulebook_links_for_object")
    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_enforcement_point_links_for_object"
    )
    @patch("netbox_nsm.security.enforcement_point_panel.ContentType")
    def test_builds_rows_from_enforcement_point_host_links(
        self,
        ct_cls,
        iter_ep_links,
        iter_rb_links,
    ):
        ct_cls.objects.get_for_model.return_value = SimpleNamespace(pk=7)

        rulebook = SimpleNamespace(
            name="Firewall Demo",
            get_absolute_url=lambda: "/plugins/netbox-nsm/rulebooks/nsm_rb_zone_matrix/",
        )
        ep_link = SimpleNamespace(
            pk=11,
            rulebook_slug="nsm_rb_zone_matrix",
            rulebook=rulebook,
        )
        iter_ep_links.return_value = [ep_link]
        iter_rb_links.return_value = []

        request = RequestFactory().get("/dcim/devices/42/")
        request.user = MagicMock(is_authenticated=True, has_perm=lambda _perm: False)

        panel = build_enforcement_point_panel(
            _host(),
            request=request,
            panel_url=lambda url: url,
            return_url="/dcim/devices/42/",
        )

        self.assertIsNotNone(panel)
        self.assertEqual(panel["count"], 1)
        self.assertEqual(panel["rulebooks"][0]["name"], "Firewall Demo")
        self.assertIn("nsm_rb_zone_matrix", panel["rulebooks"][0]["url"])

    @patch("netbox_nsm.security.enforcement_point_panel.iter_rulebook_links_for_object")
    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_enforcement_point_links_for_object"
    )
    @patch("netbox_nsm.security.enforcement_point_panel.reverse")
    def test_falls_back_to_slug_when_rulebook_unresolved(
        self,
        reverse_fn,
        iter_ep_links,
        iter_rb_links,
    ):
        reverse_fn.return_value = "/plugins/netbox-nsm/rulebooks/nsm_rb_zone_matrix/"

        ep_link = SimpleNamespace(
            pk=11,
            rulebook_slug="nsm_rb_zone_matrix",
            rulebook=None,
        )
        iter_ep_links.return_value = [ep_link]
        iter_rb_links.return_value = []

        panel = build_enforcement_point_panel(
            _host(),
            request=None,
            panel_url=lambda url: url,
            return_url="/dcim/devices/42/",
        )

        self.assertIsNotNone(panel)
        self.assertEqual(panel["count"], 1)
        self.assertEqual(panel["rulebooks"][0]["name"], "nsm_rb_zone_matrix")
        self.assertEqual(
            panel["rulebooks"][0]["url"],
            "/plugins/netbox-nsm/rulebooks/nsm_rb_zone_matrix/",
        )
        reverse_fn.assert_called_once_with(
            "plugins:netbox_nsm:cot_rulebook",
            kwargs={"slug": "nsm_rb_zone_matrix"},
        )

    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_enforcement_point_links_for_object",
        return_value=[],
    )
    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_rulebook_links_for_object",
        return_value=[],
    )
    def test_returns_none_when_no_links(self, _iter_rb, _iter_ep):
        panel = build_enforcement_point_panel(
            _host(),
            request=None,
            panel_url=lambda url: url,
            return_url="/",
        )
        self.assertIsNone(panel)

    def test_returns_none_for_unrelated_objects(self):
        panel = build_enforcement_point_panel(
            SimpleNamespace(pk=1),
            request=None,
            panel_url=lambda url: url,
            return_url="/",
        )
        self.assertIsNone(panel)

    @patch("netbox_nsm.security.enforcement_point_panel.get_interface_parent_host")
    @patch("netbox_nsm.security.enforcement_point_panel.iter_rulebook_links_for_object")
    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_enforcement_point_links_stored_on_object",
        return_value=[],
    )
    @patch(
        "netbox_nsm.security.enforcement_point_panel.iter_enforcement_point_links_for_object"
    )
    def test_interface_inherits_parent_host_rulebooks(
        self,
        iter_ep_links,
        _iter_iface_links,
        iter_rb_links,
        get_parent,
    ):
        host = _host(pk=99)
        iface = _iface(host=host)
        get_parent.return_value = host

        rulebook = SimpleNamespace(
            name="Demo",
            get_absolute_url=lambda: "/plugins/netbox-nsm/rulebooks/nsm_rb_zone_matrix/",
        )
        ep_link = SimpleNamespace(
            pk=21,
            rulebook_slug="nsm_rb_zone_matrix",
            rulebook=rulebook,
        )
        iter_ep_links.return_value = [ep_link]
        iter_rb_links.return_value = []

        panel = build_enforcement_point_panel(
            iface,
            request=None,
            panel_url=lambda url: url,
            return_url="/dcim/interfaces/7/",
        )

        self.assertIsNotNone(panel)
        self.assertTrue(panel["is_interface"])
        self.assertEqual(panel["count"], 1)
        self.assertEqual(panel["rulebooks"][0]["name"], "Demo")
        iter_ep_links.assert_called_once_with(host)
