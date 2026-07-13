"""Tests for the DRF IP Analyzer REST API."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from netbox_nsm.api.ip_analyzer import IpAnalyzerRestApiView
from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service import parse_object_refs


class IpAnalyzerRestApiUrlTests(SimpleTestCase):
    def test_ip_analyzer_rest_api_url_reverse(self):
        self.assertEqual(
            reverse("plugins-api:netbox_nsm-api:ip-analyzer"),
            "/api/plugins/netbox-nsm/ip-analyzer/",
        )


class IpAnalyzerRestApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = IpAnalyzerRestApiView.as_view()
        self.user = MagicMock(is_authenticated=True)

    def _get(self, path, data=None):
        request = self.factory.get(path, data=data or {})
        force_authenticate(request, user=self.user)
        return self.view(request)

    def _post(self, path, payload):
        request = self.factory.post(path, payload, format="json")
        force_authenticate(request, user=self.user)
        return self.view(request)

    def test_get_requires_ct_and_pk(self):
        response = self._get("/api/plugins/netbox-nsm/ip-analyzer/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("ct and pk", response.data["detail"])

    @patch("netbox_nsm.api.ip_analyzer.execute_ip_analyzer_merge")
    @patch("netbox_nsm.api.ip_analyzer.parse_selections_from_request")
    def test_get_merge_returns_json_without_html(self, parse_fn, execute_fn):
        parse_fn.return_value = ([{"ct": "10", "pk": "42", "name": "demo"}], [MagicMock()], [], [{"ct": "10", "pk": "42", "name": "demo"}], {(10, 42): MagicMock()}, [])
        execute_fn.return_value = {
            "mode": "merge",
            "leaf_count": 2,
            "count_subnets": 1,
            "count_ranges": 0,
            "count_ips": 2,
            "count_duplicates": 0,
            "objects": [{"ct": "10", "pk": "42", "name": "demo"}],
            "unsupported": [],
            "addr_analyzer": [{"field_name": "", "types": [{"nodes": []}]}],
            "object_tree": None,
        }

        response = self._get("/api/plugins/netbox-nsm/ip-analyzer/?ct=10&pk=42")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("html", response.data)
        self.assertEqual(response.data["leaf_count"], 2)
        self.assertIn("addr_analyzer", response.data)
        execute_fn.assert_called_once()
        self.assertFalse(execute_fn.call_args.kwargs["include_html"])

    @patch("netbox_nsm.api.ip_analyzer.execute_ip_analyzer_merge")
    @patch("netbox_nsm.api.ip_analyzer.parse_selections_from_request")
    def test_get_merge_includes_dup_tooltip_in_response(self, parse_fn, execute_fn):
        parse_fn.return_value = ([{"ct": "10", "pk": "42", "name": "demo"}], [MagicMock()], [], [{"ct": "10", "pk": "42", "name": "demo"}], {(10, 42): MagicMock()}, [])
        execute_fn.return_value = {
            "mode": "merge",
            "leaf_count": 1,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 1,
            "count_duplicates": 1,
            "objects": [{"ct": "10", "pk": "42", "name": "demo"}],
            "unsupported": [],
            "addr_analyzer": [
                {
                    "field_name": "",
                    "types": [
                        {
                            "nodes": [
                                {
                                    "name": "demo",
                                    "dup_tooltip": "contained in parent prefix: g-10.0.0.0/8",
                                }
                            ]
                        }
                    ],
                }
            ],
            "object_tree": [
                {
                    "name": "demo",
                    "dup_tooltip": "contained in parent prefix: g-10.0.0.0/8",
                }
            ],
        }

        response = self._get("/api/plugins/netbox-nsm/ip-analyzer/?ct=10&pk=42")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["addr_analyzer"][0]["types"][0]["nodes"][0]["dup_tooltip"],
            "contained in parent prefix: g-10.0.0.0/8",
        )
        self.assertEqual(
            response.data["object_tree"][0]["dup_tooltip"],
            "contained in parent prefix: g-10.0.0.0/8",
        )

    @patch("netbox_nsm.api.ip_analyzer.execute_ip_analyzer_diff")
    @patch("netbox_nsm.api.ip_analyzer.parse_diff_sides_from_request")
    def test_get_diff_mode(self, parse_sides_fn, execute_fn):
        parse_sides_fn.return_value = [
            {"label": "A", "selections": [], "objs": [MagicMock()], "unsupported": []},
            {"label": "B", "selections": [], "objs": [MagicMock()], "unsupported": []},
        ]
        execute_fn.return_value = {
            "mode": "diff",
            "leaf_count": 1,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 1,
            "count_duplicates": 0,
            "objects": [],
            "unsupported": [],
            "addr_analyzer": [{"field_name": "", "types": [{"nodes": [], "diff_summary": {"both": 1}}]}],
            "diff_summary": {"both": 1},
        }

        response = self._get(
            "/api/plugins/netbox-nsm/ip-analyzer/?mode=diff&a_ct=10&a_pk=1&b_ct=10&b_pk=2"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "diff")
        self.assertEqual(response.data["diff_summary"]["both"], 1)

    @patch("netbox_nsm.api.ip_analyzer.parse_selections_from_request")
    def test_get_merge_reports_unauthorized_objects(self, parse_fn):
        # User cannot view the object -> excluded from analysis, surfaced separately.
        parse_fn.return_value = ([], [], [], [], {}, [{"ct": "10", "pk": "42"}])

        response = self._get("/api/plugins/netbox-nsm/ip-analyzer/?ct=10&pk=42")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["objects"], [])
        self.assertEqual(response.data["unauthorized"], [{"ct": "10", "pk": "42"}])
        self.assertNotIn("html", response.data)
        # The request user is threaded into resolution for permission checks.
        self.assertIs(parse_fn.call_args.kwargs["user"], self.user)

    def test_post_merge_requires_objects(self):
        response = self._post("/api/plugins/netbox-nsm/ip-analyzer/", {"mode": "merge"})
        self.assertEqual(response.status_code, 400)

    @patch("netbox_nsm.api.ip_analyzer.execute_ip_analyzer_merge")
    @patch("netbox_nsm.api.ip_analyzer.parse_object_refs")
    def test_post_merge_accepts_object_list(self, parse_refs_fn, execute_fn):
        parse_refs_fn.return_value = ([{"ct": "10", "pk": "5", "name": "bench-ip"}], [MagicMock()], [], [{"ct": "10", "pk": "5", "name": "bench-ip"}], {(10, 5): MagicMock()}, [])
        execute_fn.return_value = {
            "mode": "merge",
            "leaf_count": 1,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 1,
            "count_duplicates": 0,
            "objects": [{"ct": "10", "pk": "5", "name": "bench-ip"}],
            "unsupported": [],
            "addr_analyzer": [{"field_name": "", "types": [{"nodes": [{"name": "bench-ip"}]}]}],
        }

        response = self._post(
            "/api/plugins/netbox-nsm/ip-analyzer/",
            {
                "mode": "merge",
                "objects": [{"content_type": 10, "id": 5}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["objects"][0]["name"], "bench-ip")
        parse_refs_fn.assert_called_once()

    @patch("netbox_nsm.api.ip_analyzer.execute_ip_analyzer_diff")
    def test_post_diff_accepts_sides(self, execute_fn):
        execute_fn.return_value = {
            "mode": "diff",
            "leaf_count": 0,
            "count_subnets": 0,
            "count_ranges": 0,
            "count_ips": 0,
            "count_duplicates": 0,
            "objects": [],
            "unsupported": [],
            "addr_analyzer": [],
            "message": "No valid objects selected for diff.",
        }

        response = self._post(
            "/api/plugins/netbox-nsm/ip-analyzer/",
            {
                "mode": "diff",
                "sides": [
                    {"label": "Left", "objects": [{"content_type": 10, "id": 1}]},
                    {"label": "Right", "objects": [{"content_type": 10, "id": 2}]},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        execute_fn.assert_called_once()


class ParseObjectRefsTests(SimpleTestCase):
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service._object_is_addr_analyzable", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service.ContentType")
    def test_parse_object_refs_accepts_content_type_and_id(self, content_type_cls, analyzable_fn):
        obj = MagicMock()
        obj.pk = 9
        obj.name = "bench-ip-0018231"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        selections, objs, unsupported, raw_selections, obj_by_key, unauthorized = (
            parse_object_refs([{"content_type": 10, "id": 9}])
        )

        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0]["name"], "bench-ip-0018231")
        self.assertEqual(len(objs), 1)
        self.assertEqual(unsupported, [])
        self.assertEqual(len(raw_selections), 1)
        self.assertIn((10, 9), obj_by_key)
        self.assertEqual(unauthorized, [])

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service._object_is_addr_analyzable", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service.ContentType")
    def test_parse_object_refs_skips_object_without_view_permission(
        self, content_type_cls, analyzable_fn
    ):
        obj = MagicMock()
        obj.pk = 9
        obj.name = "secret-ip"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj
        # No object-level restrict() -> falls back to Django model permission.
        del model_cls.objects.restrict
        model_cls._meta.app_label = "ipam"
        model_cls._meta.model_name = "ipaddress"

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        user = MagicMock()
        user.has_perm.return_value = False

        selections, objs, unsupported, raw_selections, obj_by_key, unauthorized = (
            parse_object_refs([{"content_type": 10, "id": 9}], user=user)
        )

        self.assertEqual(selections, [])
        self.assertEqual(objs, [])
        self.assertEqual(raw_selections, [])
        self.assertEqual(obj_by_key, {})
        self.assertEqual(unauthorized, [{"ct": "10", "pk": "9"}])
        user.has_perm.assert_called_once_with("ipam.view_ipaddress")

    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service._object_is_addr_analyzable", return_value=True)
    @patch("netbox_nsm.analyzers.ip_analyzer.ip_analyzer_service.ContentType")
    def test_parse_object_refs_uses_object_level_restrict(
        self, content_type_cls, analyzable_fn
    ):
        obj = MagicMock()
        obj.pk = 9
        obj.name = "visible-ip"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj
        model_cls.objects.restrict.return_value.filter.return_value.exists.return_value = True

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        user = MagicMock()

        selections, objs, unsupported, raw_selections, obj_by_key, unauthorized = (
            parse_object_refs([{"content_type": 10, "id": 9}], user=user)
        )

        self.assertEqual(len(selections), 1)
        self.assertEqual(unauthorized, [])
        model_cls.objects.restrict.assert_called_once_with(user, "view")
