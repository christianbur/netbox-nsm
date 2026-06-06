"""HTTP tests for Object Analyzer and object-rules APIs."""

import json

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse
from ipam.models import Prefix

from netbox_nsm.analyzer.api_view import AnalyzerAPIView
from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RuleObjectItem,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.views.object_analyzer import ObjectAnalyzerView
from netbox_nsm.views.object_rules_api import ObjectRulesApiView
from utilities.testing import TestCase


class ObjectAnalyzerPageTests(TestCase):
    def test_object_analyzer_page_renders(self):
        url = reverse("plugins:netbox_nsm:object_analyzer")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(response, "Object Analyzer")


class AnalyzerApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.prefix = Prefix.objects.filter(prefix="10.80.0.0/24").first()
        if cls.prefix is None:
            cls.prefix = Prefix.objects.create(prefix="10.80.0.0/24", status="active")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)

    def test_analyzer_api_returns_node_for_prefix(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse("plugins:netbox_nsm:analyzer_api")
            + f"?ct={self.prefix_ct.pk}&pk={self.prefix.pk}"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = AnalyzerAPIView.as_view()(request)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertIn("node", data)
        self.assertIn("children", data)

    def test_analyzer_api_requires_ct_and_pk(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        request = RequestFactory().get(reverse("plugins:netbox_nsm:analyzer_api"))
        request.user = self.user
        response = AnalyzerAPIView.as_view()(request)
        self.assertEqual(response.status_code, 400, response.content)


class ObjectRulesApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="object-rules-rb",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="object-rules-rule",
            index=10,
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
        )
        cls.prefix = Prefix.objects.filter(prefix="10.81.0.0/24").first()
        if cls.prefix is None:
            cls.prefix = Prefix.objects.create(prefix="10.81.0.0/24", status="active")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        RuleObjectItem.objects.create(
            rule=cls.rule,
            field=cls.field,
            content_type=cls.prefix_ct,
            object_id=cls.prefix.pk,
        )

    def test_object_rules_api_lists_references(self):
        self.add_permissions("netbox_nsm.view_rule")
        url = (
            reverse("plugins:netbox_nsm:object_rules_api")
            + f"?ct_id={self.prefix_ct.pk}&obj_id={self.prefix.pk}"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = ObjectRulesApiView.as_view()(request)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["results"][0]["rule_name"], "object-rules-rule")

    def test_object_rules_api_requires_params(self):
        request = RequestFactory().get(reverse("plugins:netbox_nsm:object_rules_api"))
        response = ObjectRulesApiView.as_view()(request)
        self.assertEqual(response.status_code, 400, response.content)
