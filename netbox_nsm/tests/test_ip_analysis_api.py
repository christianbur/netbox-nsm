"""Tests for IpAnalysisApiView."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.analysis.ip.api import IpAnalysisApiView


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

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
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

    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
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
            "netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable",
            return_value=False,
        ):
            response = self.view(
                self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=11&pk=7")
            )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "")
        self.assertIn("No analyzable", data["message"])

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
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

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container",
        return_value=False,
    )
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_multi_object_cell_shows_object_tree_for_drilldown(
        self,
        content_type_cls,
        _group_container,
        addr_ip_ref_fn,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        """Rules cell with address + group: show NSM object tree (lazy IPAM drilldown)."""
        addr_ip_ref_fn.return_value = {"str": "10.0.0.0/8", "url": "#"}
        obj_a = MagicMock()
        obj_a.pk = 1
        obj_a.name = "g-10.0.0.0/8"
        obj_a.get_absolute_url.return_value = "/g/1/"
        obj_b = MagicMock()
        obj_b.pk = 2
        obj_b.name = "bench-ip"
        obj_b.get_absolute_url.return_value = "/a/2/"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.side_effect = [obj_a, obj_b]

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {
                "field_name": "",
                "types": [
                    {
                        "leaf_count": 2,
                        "count_ips": 2,
                        "nodes": [{"name": "merged-root", "kind": "group", "children": []}],
                    }
                ],
            }
        ]
        render_fn.return_value = "<div>logical-merge</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=1&ct=10&pk=2"
            )
        )

        self.assertEqual(response.status_code, 200)
        render_fn.assert_called_once()
        ctx = render_fn.call_args[0][1]
        self.assertTrue(ctx.get("object_tree"))
        self.assertTrue(ctx.get("addr_analysis"))

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container",
        return_value=False,
    )
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_object_tree_shown_for_single_unique_object(
        self,
        content_type_cls,
        _group_container,
        addr_ip_ref_fn,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        addr_ip_ref_fn.return_value = {"str": "10.0.0.1", "url": "#"}
        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        obj.get_absolute_url.return_value = "/a/5/"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {"field_name": "", "types": [{"leaf_count": 1, "nodes": []}]}
        ]
        render_fn.return_value = "<div>single</div>"

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=5")
        )

        self.assertEqual(response.status_code, 200)
        render_fn.assert_called_once()
        ctx = render_fn.call_args[0][1]
        self.assertTrue(ctx.get("object_tree"))

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.addr_analysis_utils._addr_ip_ref")
    @patch(
        "netbox_nsm.analysis.addr_analysis_utils._addr_is_group_container",
        return_value=False,
    )
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_object_tree_rendered_for_duplicate_cell_entries(
        self,
        content_type_cls,
        _group_container,
        addr_ip_ref_fn,
        analyzable_fn,
        build_fn,
        render_fn,
    ):
        addr_ip_ref_fn.return_value = {"str": "10.0.0.1", "url": "#"}
        obj = MagicMock()
        obj.pk = 5
        obj.name = "bench-ip"
        obj.get_absolute_url.return_value = "/a/5/"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.return_value = obj

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_fn.return_value = [
            {"field_name": "", "types": [{"leaf_count": 1, "nodes": []}]}
        ]
        render_fn.return_value = "<div>with-tree</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=5&ct=10&pk=5"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>with-tree</div>")
        render_fn.assert_called_once()
        ctx = render_fn.call_args[0][1]
        # Cell object tree (incl. doppelt markers) is always shown when nodes exist.
        self.assertTrue(ctx.get("object_tree"))
        self.assertEqual(len(data["objects"]), 1)
        build_fn.assert_called_once()
        self.assertEqual(len(build_fn.call_args[0][0]), 1)
        self.assertEqual(
            render_fn.call_args[0][0],
            "netbox_nsm/inc/addr_analysis_applet_body.html",
        )

    @patch(
        "netbox_nsm.analysis.ip_analysis_service._build_ipa_cell_object_tree",
        return_value=[],
    )
    @patch(
        "netbox_nsm.analysis.ip_analysis_service._leaf_count_for_addr_analysis", return_value=0
    )
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_empty_resolved_tree_returns_no_ips_message(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
        leaf_count_fn,
        _cell_tree_fn,
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
        self.assertIn("No IP addresses resolved", data["message"])
        self.assertEqual(len(data["objects"]), 1)

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
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
                "types": [
                    {
                        "leaf_count": 1,
                        "count_subnets": 1,
                        "count_ranges": 0,
                        "count_ips": 1,
                        "nodes": [{"name": "demo-addr"}],
                    }
                ],
            }
        ]
        render_fn.return_value = "<div>prefix-analysis</div>"

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=14&pk=5")
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>prefix-analysis</div>")
        self.assertEqual(data["leaf_count"], 2)
        self.assertEqual(data["count_subnets"], 1)
        self.assertEqual(data["count_ranges"], 0)
        self.assertEqual(data["count_ips"], 1)
        self.assertEqual(len(data["objects"]), 1)

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_addr_diff_analysis_from_sides")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_diff_mode_compares_two_sides(
        self,
        content_type_cls,
        analyzable_fn,
        build_diff_fn,
        render_fn,
    ):
        """Simulates applet Diff: one API call with side A and side B objects."""
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
        build_diff_fn.return_value = [
            {
                "field_name": "",
                "types": [
                    {
                        "leaf_count": 3,
                        "nodes": [],
                        "diff_summary": {
                            "only_a": 1,
                            "only_b": 1,
                            "both": 1,
                            "label_a": "Tab A",
                            "label_b": "Tab B",
                        },
                    }
                ],
            }
        ]
        render_fn.return_value = "<div>diff</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/"
                "?mode=diff&a_ct=10&a_pk=1&b_ct=10&b_pk=2"
                "&a_name=Tab%20A&b_name=Tab%20B"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>diff</div>")
        self.assertEqual(data["mode"], "diff")
        self.assertEqual(data["diff_summary"]["only_a"], 1)
        self.assertEqual(data["diff_summary"]["both"], 1)
        self.assertEqual(len(data["objects"]), 2)
        build_diff_fn.assert_called_once()
        side_specs = build_diff_fn.call_args[0][0]
        self.assertEqual(len(side_specs), 2)
        self.assertEqual(side_specs[0]["label"], "Tab A")
        self.assertEqual(side_specs[1]["label"], "Tab B")
        self.assertEqual(len(side_specs[0]["objs"]), 1)
        self.assertEqual(len(side_specs[1]["objs"]), 1)

    @patch("netbox_nsm.analysis.ip_analysis_service.render_to_string")
    @patch("netbox_nsm.analysis.ip_analysis_service._build_addr_diff_analysis_from_sides")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_diff_mode_compares_three_indexed_sides(
        self,
        content_type_cls,
        analyzable_fn,
        build_diff_fn,
        render_fn,
    ):
        obj_a = MagicMock()
        obj_a.pk = 1
        obj_a.name = "addr-a"
        obj_b = MagicMock()
        obj_b.pk = 2
        obj_b.name = "addr-b"
        obj_c = MagicMock()
        obj_c.pk = 3
        obj_c.name = "addr-c"

        model_cls = MagicMock()
        model_cls.objects.filter.return_value.first.side_effect = [
            obj_a,
            obj_b,
            obj_c,
        ]

        ct = MagicMock()
        ct.model_class.return_value = model_cls
        content_type_cls.objects.get.return_value = ct

        analyzable_fn.return_value = True
        build_diff_fn.return_value = [
            {
                "field_name": "",
                "types": [
                    {
                        "leaf_count": 3,
                        "nodes": [],
                        "diff_summary": {
                            "side_count": 3,
                            "in_all": 1,
                            "in_some": 0,
                            "only_by_side": [
                                {"label": "Tab 1", "count": 1},
                                {"label": "Tab 2", "count": 1},
                                {"label": "Tab 3", "count": 1},
                            ],
                            "fund": 0,
                        },
                    }
                ],
            }
        ]
        render_fn.return_value = "<div>diff-3</div>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/"
                "?mode=diff"
                "&s0_ct=10&s0_pk=1&s1_ct=10&s1_pk=2&s2_ct=10&s2_pk=3"
                "&s0_name=Tab%201&s1_name=Tab%202&s2_name=Tab%203"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<div>diff-3</div>")
        self.assertEqual(data["mode"], "diff")
        self.assertEqual(data["diff_summary"]["side_count"], 3)
        self.assertEqual(len(data["objects"]), 3)
        side_specs = build_diff_fn.call_args[0][0]
        self.assertEqual(len(side_specs), 3)
        self.assertEqual(side_specs[0]["label"], "Tab 1")
        self.assertEqual(side_specs[2]["label"], "Tab 3")

    @patch("netbox_nsm.analysis.ip_analysis_service._build_multi_object_addr_analysis")
    @patch("netbox_nsm.analysis.ip_analysis_service._object_is_addr_analyzable")
    @patch("netbox_nsm.analysis.ip_analysis_service.ContentType")
    def test_returns_yaml_attachment_for_format_yaml(
        self,
        content_type_cls,
        analyzable_fn,
        build_fn,
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
            {
                "field_name": "",
                "types": [
                    {
                        "leaf_count": 1,
                        "all_copy_lines": ["all,demo-addr,10.0.0.1"],
                        "nodes": [
                            {
                                "name": "demo-addr",
                                "kind": "leaf",
                                "ip_ref": {"str": "10.0.0.1"},
                                "copy_lines": ["all,demo-addr,10.0.0.1"],
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        ]

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analysis/"
                "?format=yaml&ct=10&pk=42&export_title=demo-addr"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/yaml; charset=utf-8")
        self.assertIn('filename="demo-addr-merge.yaml"', response["Content-Disposition"])
        self.assertIn(b"ipa_export_version:", response.content)
        self.assertIn(b"displayed:", response.content)
        self.assertIn(b"copy_lines:", response.content)
        self.assertIn(b"addr_analysis:", response.content)
        self.assertNotIn(b'"html"', response.content)

    @patch("netbox_nsm.analysis.ip.api.execute_ip_analysis_merge")
    @patch("netbox_nsm.analysis.ip.api.parse_selections_from_request")
    def test_returns_json_error_on_unhandled_exception(
        self, parse_fn, merge_fn
    ):
        parse_fn.return_value = ([], [], [], [], {}, [])
        merge_fn.side_effect = RuntimeError("boom")

        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analysis/?ct=10&pk=42")
        )

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertIn("error", data)
        self.assertIn("boom", data["error"])
        self.assertEqual(data.get("detail"), "boom")
