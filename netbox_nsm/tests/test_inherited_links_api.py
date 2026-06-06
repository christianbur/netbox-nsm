"""Tests for InheritedLinksApiView (inherit_links gating)."""

import json
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.ipam_inheritance import InheritedNsmLink
from netbox_nsm.views.inherited_links_api import InheritedLinksApiView


class InheritedLinksApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = InheritedLinksApiView.as_view()

    @patch("netbox_nsm.views.inherited_links_api.ContentType")
    @patch("netbox_nsm.views.inherited_links_api.iter_inherited_nsm_links")
    def test_skips_inherited_zone_when_inherit_links_disabled(
        self, iter_links_fn, content_type_cls
    ):
        from ipam.models import IPAddress

        ip = MagicMock(spec=IPAddress, pk=501)
        ip_ct = MagicMock()
        ip_ct.model_class.return_value = IPAddress
        content_type_cls.objects.get.return_value = ip_ct

        ip_model = ip_ct.model_class.return_value
        ip_model.objects.get.return_value = ip
        iter_links_fn.return_value = iter([])

        request = self.factory.get(
            "/plugins/netbox-nsm/api/inherited-links/?ct_id=5&obj_id=501"
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["groups"], [])
        iter_links_fn.assert_called_once_with(ip)

    @patch("netbox_nsm.views.inherited_links_api.render_object_display")
    @patch("netbox_nsm.views.inherited_links_api.tc_panel_label")
    @patch("netbox_nsm.views.inherited_links_api.get_display_template_map")
    @patch("netbox_nsm.views.inherited_links_api.ContentType")
    @patch("netbox_nsm.views.inherited_links_api.iter_inherited_nsm_links")
    def test_returns_inherited_groups_from_shared_iterator(
        self,
        iter_links_fn,
        content_type_cls,
        tmpl_map_fn,
        panel_label_fn,
        render_fn,
    ):
        from ipam.models import IPAddress, Prefix

        ip = MagicMock(spec=IPAddress, pk=501)
        ancestor = MagicMock(spec=Prefix, pk=1)
        ancestor.get_absolute_url.return_value = "/ipam/prefixes/1/"
        zone = MagicMock()
        zone.get_absolute_url.return_value = "/zones/1/"
        zone_ct = MagicMock(pk=99)

        ip_ct = MagicMock()
        ip_ct.model_class.return_value = IPAddress
        content_type_cls.objects.get.return_value = ip_ct
        ip_ct.model_class.return_value.objects.get.return_value = ip

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
        tmpl_map_fn.return_value = {}
        panel_label_fn.return_value = "Zones"
        render_fn.return_value = "DMZ"

        request = self.factory.get(
            "/plugins/netbox-nsm/api/inherited-links/?ct_id=5&obj_id=501"
        )
        response = self.view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["groups"]), 1)
        self.assertEqual(data["groups"][0]["type_label"], "Zones")
        self.assertEqual(data["groups"][0]["objects"][0]["name"], "DMZ")
