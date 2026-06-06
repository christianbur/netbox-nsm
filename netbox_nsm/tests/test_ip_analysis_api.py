"""Tests for IpAnalysisApiView."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.views.ip_analysis_api import IpAnalysisApiView


class IpAnalysisApiUrlTests(SimpleTestCase):
    def test_ip_analysis_api_url_reverse(self):
        self.assertEqual(
            reverse("plugins:netbox_nsm:ip_analysis_api"),
            "/plugins/netbox-nsm/api/ip-analysis/",
        )


class IpAnalysisApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = IpAnalysisApiView.as_view()

    def _auth_request(self, path):
        request = self.factory.get(path)
        request.user = MagicMock(is_authenticated=True)
        return request

    def test_requires_ct_and_pk(self):
        response = self.view(self._auth_request("/plugins/netbox-nsm/api/ip-analysis/"))
        self.assertEqual(response.status_code, 400)

    @patch("netbox_nsm.views.ip_analysis_api.render_to_string")
    @patch("netbox_nsm.views.ip_analysis_api._build_multi_object_addr_analysis")
    @patch("netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable")
    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_returns_html_for_supported_object(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        obj = MagicMock()
        obj.pk = 42
        obj.name = "demo-addr"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {"field_name": "", "types": [{"leaf_count": 1, "nodes": []}]}
        ]
        render_fn.return_value = "<div>analysis</div>"

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=42")
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>analysis</div>")
        self.assertEqual(data["objects"][0]["pk"], "42")

    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_skips_unsupported_objects(self, content_type_cls):
        obj = MagicMock()
        obj.pk = 7
        obj.name = "zone-a"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        with patch(
            "netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable",
            return_value=False,
        ):
            response = self.view(
                self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=11&pk=7")
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "")
        self.assertIn("Keine analysierbaren", data["message"])

    @patch("netbox_nsm.views.ip_analysis_api.render_to_string")
    @patch("netbox_nsm.views.ip_analysis_api._build_multi_object_addr_analysis")
    @patch("netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable")
    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_merge_multiple_objects_single_analysis(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        """Simulates applet Merge: one API call with all tab objects."""
        obj_a = MagicMock()
        obj_a.pk = 1
        obj_a.name = "addr-a"
        obj_b = MagicMock()
        obj_b.pk = 2
        obj_b.name = "addr-b"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.side_effect = [obj_a, obj_b]

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {"field_name": "", "types": [{"leaf_count": 2, "nodes": []}]}
        ]
        render_fn.return_value = "<div>merged</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=1&ct=10&pk=2"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>merged</div>")
        self.assertEqual(len(data["objects"]), 2)
        build_fn.assert_called_once()
        merged_objs = build_fn.call_args[0][0]
        self.assertEqual(len(merged_objs), 2)

    @patch("netbox_nsm.views.ip_analysis_api.render_to_string")
    @patch("netbox_nsm.views.ip_analysis_api._build_multi_object_addr_analysis")
    @patch("netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable")
    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_deduplicates_duplicate_ct_pk_pairs(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        """Same object opened in multiple tabs is deduplicated on merge."""
        obj = MagicMock()
        obj.pk = 5
        obj.name = "addr-x"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {"field_name": "", "types": [{"leaf_count": 1, "nodes": []}]}
        ]
        render_fn.return_value = "<div>merged</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=5&ct=10&pk=5"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["objects"]), 1)
        build_fn.assert_called_once()
        self.assertEqual(len(build_fn.call_args[0][0]), 1)

    @patch(
        "netbox_nsm.views.ip_analysis_api._leaf_count_for_addr_analysis", return_value=0
    )
    @patch("netbox_nsm.views.ip_analysis_api._build_multi_object_addr_analysis")
    @patch("netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable")
    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_empty_resolved_tree_returns_no_ips_message(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        leaf_count_fn,
    ):
        obj = MagicMock()
        obj.pk = 5
        obj.name = "10.245.10.0/24"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = []

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=14&pk=5")
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "")
        self.assertEqual(data["leaf_count"], 0)
        self.assertIn("Keine IP-Adressen aufgelöst", data["message"])
        self.assertEqual(len(data["objects"]), 1)

    @patch("netbox_nsm.views.ip_analysis_api.render_to_string")
    @patch("netbox_nsm.views.ip_analysis_api._build_multi_object_addr_analysis")
    @patch("netbox_nsm.views.ip_analysis_api._object_is_addr_analyzable")
    @patch("netbox_nsm.views.ip_analysis_api.ContentType")
    def test_ipam_prefix_accepted_when_analyzable(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        prefix = MagicMock()
        prefix.pk = 5
        prefix.__str__ = lambda self: "10.245.10.0/24"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = prefix

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {
                "field_name": "",
                "types": [{"leaf_count": 1, "nodes": [{"name": "demo-addr"}]}],
            }
        ]
        render_fn.return_value = "<div>prefix-analysis</div>"

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=14&pk=5")
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>prefix-analysis</div>")
        self.assertEqual(data["leaf_count"], 1)
        self.assertEqual(len(data["objects"]), 1)
