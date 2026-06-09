"""Tests for lazy-loaded Security Panel object-rules API."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.security.views.object_rules_api import ObjectRulesApiView


class ObjectRulesFieldApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = ObjectRulesApiView.as_view()

    @patch("netbox_nsm.security.views.object_rules_api.ContentType.objects.get")
    @patch("netbox_nsm.security.views.object_rules_api.fetch_cot_security_field_rules")
    def test_field_filter_returns_batch(self, mock_fetch, mock_ct_get):
        mock_ct_get.return_value = SimpleNamespace(pk=12)
        rulebook = SimpleNamespace(
            pk=16,
            slug="nsm_rb_bench_addresses",
            name="Bench Addresses",
            get_rules_tab_url=lambda: "/rulebooks/cot/nsm_rb_bench_addresses/rules/",
        )
        field = SimpleNamespace(pk=114, name="Services & Applications")
        rule = SimpleNamespace(pk=1, name="bench-rule-00001")
        rule.get_absolute_url = lambda: "/plugins/custom-objects/nsm_rb_bench_addresses/1/"
        mock_fetch.return_value = (
            [
                {
                    "rulebook": rulebook,
                    "field": field,
                    "rule": rule,
                }
            ],
            3250,
        )

        request = self.factory.get(
            "/plugins/netbox-nsm/api/object-rules/",
            {
                "ct_id": "12",
                "obj_id": "42",
                "rulebook_pk": "16",
                "field_pk": "114",
                "offset": "0",
            },
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["total"], 3250)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["rule_name"], "bench-rule-00001")
        self.assertEqual(payload["results"][0]["field_pk"], 114)
        self.assertTrue(payload["has_more"])
        mock_fetch.assert_called_once_with(
            mock_ct_get.return_value,
            42,
            rulebook_pk=16,
            field_pk=114,
            offset=0,
            limit=20,
        )

    @patch("netbox_nsm.security.views.object_rules_api.ContentType.objects.get")
    def test_invalid_field_params_return_400(self, mock_ct_get):
        mock_ct_get.return_value = SimpleNamespace(pk=12)
        request = self.factory.get(
            "/plugins/netbox-nsm/api/object-rules/",
            {
                "ct_id": "12",
                "obj_id": "42",
                "rulebook_pk": "bad",
                "field_pk": "114",
            },
        )
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
