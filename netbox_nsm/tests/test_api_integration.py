"""
REST API integration tests for netbox_nsm.

Run inside the NetBox environment, e.g.:
    python manage.py test netbox_nsm.tests.test_api_integration
"""

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status

from netbox_nsm.models import (
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    Rule,
    Rulebook,
    TypeConfig,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from netbox_nsm.tests.custom import APITestCase


def _api(name, **kwargs):
    return reverse(f"plugins-api:netbox_nsm-api:{name}", kwargs=kwargs)


class _RulebookPluginAPITestMixin:
    """Grant permissions and use plugin API routes."""

    def _grant(self, *codenames):
        self.add_permissions(*codenames)

    def _post_json(self, url, data):
        return self.client.post(url, data, format="json", **self.header)

    def _patch_json(self, url, data):
        return self.client.patch(url, data, format="json", **self.header)

    def _delete(self, url):
        return self.client.delete(url, **self.header)


class RulebookAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for rulebooks API."""

    def test_rulebook_crud(self):
        self._grant(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )
        list_url = _api("rulebook-list")

        response = self._post_json(
            list_url, {"name": "api-test-rulebook", "rulebook_type": "policy"}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        rb_id = response.data["id"]

        detail_url = _api("rulebook-detail", kwargs={"pk": rb_id})
        response = self.client.get(detail_url, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "api-test-rulebook")

        response = self._patch_json(
            detail_url, {"name": "api-test-rulebook-upd", "description": "via api"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "api-test-rulebook-upd")

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Rulebook.objects.filter(pk=rb_id).exists())


class RulebookFieldAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for rulebook-fields (writable rulebook FK)."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="api-field-rb", rulebook_type="policy"
        )
        ensure_system_rulebook_fields(cls.rulebook)

    def test_rulebook_field_crud(self):
        self._grant(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )
        list_url = _api("rulebookfield-list")

        response = self._post_json(
            list_url,
            {
                "rulebook": self.rulebook.pk,
                "slug": "api_source",
                "name": "API Source",
                "placement": "source",
                "sort_order": 50,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        field_id = response.data["id"]

        detail_url = _api("rulebookfield-detail", kwargs={"pk": field_id})
        response = self.client.get(detail_url, **self.header)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "api_source")

        response = self._patch_json(detail_url, {"name": "API Source Updated"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "API Source Updated")

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(RulebookField.objects.filter(pk=field_id).exists())


class RulebookFieldTypeAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """CRUD for rulebook-field-types."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="api-ft-rb", rulebook_type="policy"
        )
        cls.field = RulebookField.objects.create(
            rulebook=cls.rulebook,
            slug="services",
            name="Services",
            placement="fixed",
        )
        ct = ContentType.objects.order_by("pk").first()
        cls.type_config, _ = TypeConfig.objects.get_or_create(
            content_type=ct,
            defaults={"name": "API Test Type"},
        )

    def test_rulebook_field_type_crud(self):
        self._grant(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )
        list_url = _api("rulebookfieldtype-list")

        response = self._post_json(
            list_url,
            {
                "field": self.field.pk,
                "type_config": self.type_config.pk,
                "sort_order": 10,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        ft_id = response.data["id"]

        detail_url = _api("rulebookfieldtype-detail", kwargs={"pk": ft_id})
        response = self._patch_json(detail_url, {"max_items": 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["max_items"], 5)

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class RuleAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """Create, update, and delete rules API."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="api-rule-rb", rulebook_type="policy"
        )
        ensure_system_rulebook_fields(cls.rulebook)

    def test_rule_crud(self):
        self._grant(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )
        list_url = _api("rule-list")

        response = self._post_json(
            list_url,
            {
                "rulebook": self.rulebook.pk,
                "name": "api-test-rule",
                "index": 20,
                "enabled": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        rule_id = response.data["id"]

        detail_url = _api("rule-detail", kwargs={"pk": rule_id})
        response = self._patch_json(
            detail_url,
            {"name": "api-test-rule-upd", "enabled": False},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "api-test-rule-upd")
        self.assertFalse(response.data["enabled"])

        response = self._delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Rule.objects.filter(pk=rule_id).exists())


class RuleFieldSelectionsViewTest(_RulebookPluginAPITestMixin, APITestCase):
    """Plugin HTML view for lazy AG Grid cell saves (session + CSRF)."""

    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="field-sel-rb", rulebook_type="policy"
        )
        ensure_system_rulebook_fields(cls.rulebook)
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="field-sel-rule",
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
        cls.ct = ContentType.objects.order_by("pk").first()
        cls.tc, _ = TypeConfig.objects.get_or_create(
            content_type=cls.ct,
            defaults={"name": "Field Sel Type"},
        )
        RulebookFieldType.objects.create(field=cls.field, type_config=cls.tc)

    def test_field_selections_post_empty(self):
        self._grant(
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rule",
        )
        self.client.force_login(self.user)
        url = (
            reverse(
                "plugins:netbox_nsm:rule_field_selections_api",
                kwargs={"pk": self.rule.pk},
            )
            + f"?column=source::ct_{self.ct.content_type_id}"
        )
        response = self.client.post(
            url,
            {"selections": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("html", data)
        self.assertEqual(data.get("selections"), [])

    def test_field_selections_get_all_columns(self):
        self._grant("netbox_nsm.view_rule")
        self.client.force_login(self.user)
        url = reverse(
            "plugins:netbox_nsm:rule_field_selections_api",
            kwargs={"pk": self.rule.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("columns", data)
        self.assertIn("column_keys", data)

    def test_field_selections_post_bulk(self):
        self._grant(
            "netbox_nsm.view_rule",
            "netbox_nsm.change_rule",
        )
        self.client.force_login(self.user)
        col = f"source::ct_{self.tc.content_type_id}"
        url = reverse(
            "plugins:netbox_nsm:rule_field_selections_api",
            kwargs={"pk": self.rule.pk},
        )
        response = self.client.post(
            url,
            {"columns": {col: []}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertIn("cells", data)
        self.assertIn(col, data["cells"])


class RulebookWorkflowAPITest(_RulebookPluginAPITestMixin, APITestCase):
    """End-to-end: rulebook → field → field-type → rule → delete."""

    def test_full_rulebook_workflow(self):
        self._grant(
            "netbox_nsm.view_rulebook",
            "netbox_nsm.add_rulebook",
            "netbox_nsm.change_rulebook",
            "netbox_nsm.delete_rulebook",
        )

        rb_resp = self._post_json(
            _api("rulebook-list"),
            {"name": "workflow-rb", "rulebook_type": "policy"},
        )
        self.assertEqual(rb_resp.status_code, status.HTTP_201_CREATED)
        rb_id = rb_resp.data["id"]
        ensure_system_rulebook_fields(Rulebook.objects.get(pk=rb_id))

        field_resp = self._post_json(
            _api("rulebookfield-list"),
            {
                "rulebook": rb_id,
                "slug": "destination",
                "name": "Destination",
                "placement": "destination",
            },
        )
        self.assertEqual(field_resp.status_code, status.HTTP_201_CREATED)
        field_id = field_resp.data["id"]

        ct = ContentType.objects.order_by("pk").first()
        tc, _ = TypeConfig.objects.get_or_create(
            content_type=ct,
            defaults={"name": "Workflow Type"},
        )
        ft_resp = self._post_json(
            _api("rulebookfieldtype-list"),
            {"field": field_id, "type_config": tc.pk},
        )
        self.assertEqual(ft_resp.status_code, status.HTTP_201_CREATED)

        rule_resp = self._post_json(
            _api("rule-list"),
            {
                "rulebook": rb_id,
                "name": "workflow-rule",
                "index": 30,
            },
        )
        self.assertEqual(rule_resp.status_code, status.HTTP_201_CREATED)
        rule_id = rule_resp.data["id"]

        list_rules = self.client.get(
            _api("rule-list") + f"?rulebook_id={rb_id}",
            **self.header,
        )
        self.assertEqual(list_rules.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(list_rules.data["count"], 1)

        self._delete(_api("rule-detail", kwargs={"pk": rule_id}))
        self._delete(_api("rulebookfield-detail", kwargs={"pk": field_id}))
        self._delete(_api("rulebook-detail", kwargs={"pk": rb_id}))

        self.assertFalse(Rulebook.objects.filter(pk=rb_id).exists())


class APIListEndpointsTest(_RulebookPluginAPITestMixin, APITestCase):
    """Every registered list endpoint returns 200."""

    user_permissions = (
        "netbox_nsm.view_rulebook",
        "netbox_nsm.view_objectgroup",
        "netbox_nsm.view_objectlink",
        "netbox_nsm.view_typeconfig",
    )

    endpoints = (
        "rulebook-list",
        "rule-list",
        "rulebookassignment-list",
        "objectgroup-list",
        "objectlink-list",
        "typeconfig-list",
        "rulebookfield-list",
        "rulebookfieldtype-list",
        "ruleobjectitem-list",
        "rulegroupitem-list",
    )

    def test_all_list_endpoints(self):
        self._grant("netbox_nsm.view_rulebook")
        for name in self.endpoints:
            with self.subTest(endpoint=name):
                response = self.client.get(_api(name), **self.header)
                self.assertEqual(
                    response.status_code,
                    status.HTTP_200_OK,
                    f"{name}: {getattr(response, 'data', response.content)}",
                )
                self.assertIn("count", response.data)
