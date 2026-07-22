"""Tests for IpAnalyzerSubnetChildrenApiView."""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from netbox_nsm.analyzers.ip_analyzer.endpoints import IpAnalyzerSubnetChildrenApiView


class IpAnalyzerSubnetChildrenApiUrlTests(SimpleTestCase):
    def test_subnet_children_api_url_reverse(self):
        self.assertEqual(
            reverse("plugins:netbox_nsm:ip_analyzer_subnet_children_api"),
            "/plugins/netbox-nsm/api/ip-analyzer/subnet-children/",
        )


class IpAnalyzerSubnetChildrenApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = IpAnalyzerSubnetChildrenApiView.as_view()

    def _auth_request(self, path):
        request = self.factory.get(path)
        request.user = MagicMock(is_authenticated=True)
        return request

    def test_requires_prefix_pk(self):
        response = self.view(
            self._auth_request("/plugins/netbox-nsm/api/ip-analyzer/subnet-children/")
        )
        self.assertEqual(response.status_code, 400)

    @patch("netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api.render_to_string")
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._prune_to_selected_nodes"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._prune_lazy_batch_nodes"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._build_lazy_subnet_nodes"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._attach_ipa_dup_context_fields"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api.attach_ipa_cell_tenant_ref"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api.attach_ipa_cell_zone_label_refs"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._attach_ipa_dup_cell_statuses"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._mark_ipa_object_tree_duplicate_flags"
    )
    @patch(
        "netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._query_ipam_category_objects"
    )
    @patch("netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api._prefix_ipam_stats")
    @patch("netbox_nsm.analyzers.ip_analyzer.endpoints.subnet_children_api.ContentType")
    @patch("ipam.models.Prefix")
    def test_renders_lazy_subnet_children_with_depth_and_enrichment(
        self,
        prefix_cls,
        content_type_cls,
        prefix_stats_fn,
        query_child_prefixes_fn,
        build_lazy_nodes_fn,
        prune_lazy_batch_fn,
        prune_selected_fn,
        mark_duplicate_fn,
        attach_zone_label_refs_fn,
        attach_tenant_ref_fn,
        attach_dup_status_fn,
        attach_dup_context_fn,
        render_fn,
    ):
        prefix_obj = MagicMock()
        prefix_obj.pk = 7
        prefix_obj.prefix = "10.0.0.0/8"
        prefix_obj.__str__.return_value = "ANY"
        prefix_obj.get_absolute_url.return_value = "/ipam/prefixes/7/"
        prefix_cls.objects.filter.return_value.first.return_value = prefix_obj

        child_prefix_obj = MagicMock()
        child_prefix_obj.pk = 11
        query_child_prefixes_fn.return_value = [child_prefix_obj]
        prefix_stats_fn.return_value = {"child_prefixes": {"count": 1}}

        ct = MagicMock()
        ct.pk = 42
        content_type_cls.objects.get_for_model.return_value = ct

        nodes = [
            {
                "name": "10.0.1.0/24",
                "layer": "ipam_prefix",
                "pk": "11",
                "ct": "42",
                "children": [],
                "tenant_ref": {"name": "Tenant-A", "url": "/tenancy/tenants/1/"},
            }
        ]
        obj_by_key = {(42, 11): child_prefix_obj}
        build_lazy_nodes_fn.return_value = (nodes, obj_by_key)
        prune_lazy_batch_fn.return_value = nodes
        prune_selected_fn.return_value = nodes
        render_fn.return_value = "<tr>lazy-child</tr>"

        response = self.view(
            self._auth_request(
                "/plugins/netbox-nsm/api/ip-analyzer/subnet-children/?prefix_pk=7&offset=0&depth=2"
            )
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["html"], "<tr>lazy-child</tr>")

        build_lazy_nodes_fn.assert_called_once_with([child_prefix_obj], prefix_ct=42)
        prune_lazy_batch_fn.assert_called_once_with(nodes)
        prune_selected_fn.assert_called_once_with(nodes, {(42, 11)})

        self.assertTrue(nodes[0].get("subnet_contained_dup"))
        self.assertEqual(nodes[0].get("subnet_contained_in"), "10.0.0.0/8")
        self.assertEqual(nodes[0].get("subnet_contained_in_name"), "ANY")
        self.assertEqual(nodes[0].get("subnet_contained_in_url"), "/ipam/prefixes/7/")

        mark_duplicate_fn.assert_called_once_with(nodes, is_root=True)
        attach_zone_label_refs_fn.assert_called_once()
        attach_tenant_ref_fn.assert_called_once()
        attach_dup_status_fn.assert_called_once_with(nodes)
        attach_dup_context_fn.assert_called_once_with(nodes)

        zone_nodes, zone_obj_by_key = attach_zone_label_refs_fn.call_args[0]
        self.assertIs(zone_nodes, nodes)
        self.assertIn((42, 11), zone_obj_by_key)
        self.assertIs(zone_obj_by_key[(42, 11)], child_prefix_obj)

        tenant_nodes, tenant_obj_by_key = attach_tenant_ref_fn.call_args[0]
        self.assertIs(tenant_nodes, nodes)
        self.assertIn((42, 11), tenant_obj_by_key)
        self.assertIs(tenant_obj_by_key[(42, 11)], child_prefix_obj)

        render_ctx = render_fn.call_args[0][1]
        self.assertEqual(render_ctx["depth"], 3)
        self.assertIs(render_ctx["ipa_cell_pill"], False)
        self.assertEqual(
            render_fn.call_args[0][0],
            "netbox_nsm/inc/ipa_cell_tree_subnet_children_fragment.html",
        )
