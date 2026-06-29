"""Tests for IpAnalysisObjectDrilldownApiView."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.views.ip_analysis_object_api import IpAnalysisObjectDrilldownApiView


class IpAnalysisObjectApiUrlTests(SimpleTestCase):
    def test_object_drilldown_api_url_reverse(self):
        self.assertEqual(
            reverse("plugins:netbox_nsm:ip_analysis_object_api"),
            "/plugins/netbox-nsm/api/ip-analysis/object/",
        )


class IpAnalysisObjectDrilldownApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = IpAnalysisObjectDrilldownApiView.as_view()

    def _auth_request(self, path):
        request = self.factory.get(path)
        request.user = MagicMock(is_authenticated=True)
        return request

    def test_requires_ct_and_pk(self):
        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/object/")
        )
        self.assertEqual(response.status_code, 400)

    @patch("netbox_nsm.analyzers.ip.endpoints.object_api.render_to_string")
    @patch("netbox_nsm.analyzers.ip.endpoints.object_api._build_object_drilldown_nodes")
    @patch("netbox_nsm.analyzers.ip.endpoints.object_api.ContentType")
    def test_returns_drilldown_html(
        self, content_type_cls, build_nodes_fn, render_fn
    ):
        obj = MagicMock()
        obj.pk = 5

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.filter.return_value.first.return_value = ct

        build_nodes_fn.return_value = (
            [
                {
                    "name": "10.0.0.0/24",
                    "kind": "group",
                    "layer": "ipam_prefix",
                    "node_role": "ipam_prefix",
                    "children": [
                        {
                            "name": "10.0.0.1/32",
                            "kind": "leaf",
                            "node_role": "nsm_host",
                            "children": [],
                        }
                    ],
                }
            ],
            ["bench-ip,10.0.0.1/32"],
        )
        render_fn.return_value = "<div>drilldown</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/object/?ct=10&pk=5&depth=1"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>drilldown</div>")
        self.assertEqual(data["copy_lines"], ["bench-ip,10.0.0.1/32"])
        render_ctx = render_fn.call_args[0][1]
        self.assertEqual(render_ctx["depth"], 2)
        self.assertIs(render_ctx["ipa_cell_pill"], False)
        self.assertEqual(
            render_fn.call_args[0][0],
            "netbox_nsm/inc/ipa_cell_tree_drilldown_fragment.html",
        )
