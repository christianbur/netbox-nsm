"""Policy grid API validation (group_by restrictions)."""

import json

from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse

from netbox_nsm.models import (
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.views.all_rules_grid_api import AllRulesGridApiView
from netbox_nsm.views.rulebook_rules_grid_api import RulebookRulesGridApiView
from utilities.testing import TestCase


class PolicyGridApiGroupValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ct = ContentType.objects.order_by("pk").first()
        cls.tc, _ = TypeConfig.objects.get_or_create(
            content_type=cls.ct,
            defaults={"name": "Grid API Type"},
        )
        cls.rulebook = Rulebook.objects.create(
            name="Grid API RB",
            rulebook_type="security_rules",
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="source",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=10,
        )
        RulebookFieldType.objects.create(
            field=cls.field,
            type_config=cls.tc,
            visible=True,
        )

    def test_rules_grid_api_rejects_unknown_group_by(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_rules_grid_api",
                args=[self.rulebook.pk],
            )
            + "?group_by=col:source::ct_999"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookRulesGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_rules_grid_api_accepts_configured_group_by(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        col_key = f"source::ct_{self.ct.pk}"
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_rules_grid_api",
                args=[self.rulebook.pk],
            )
            + f"?group_by=col:{col_key}"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookRulesGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200)

    def test_all_rules_grid_api_rejects_unknown_group_by(self):
        self.add_permissions("netbox_nsm.view_rule")
        url = reverse("plugins:netbox_nsm:all_rules_grid_api") + "?group_by=col:missing"
        request = RequestFactory().get(url)
        request.user = self.user
        response = AllRulesGridApiView.as_view()(request)
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_all_rules_grid_api_accepts_rulebook_plus_column_grouping(self):
        self.add_permissions("netbox_nsm.view_rule")
        url = (
            reverse("plugins:netbox_nsm:all_rules_grid_api")
            + "?group_by=rulebook&group_by_2=tag:source"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = AllRulesGridApiView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("rowData", data)
