"""Tests for Assign Link element picker API (ObjectTypeElementsApiView)."""

import json

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from ipam.models import Prefix

from netbox_nsm.models import MatchingClassChoices, TypeConfig
from utilities.testing import TestCase


def _prefix(value):
    prefix = Prefix.objects.filter(prefix=value).first()
    if prefix is None:
        prefix = Prefix.objects.create(prefix=value, status="active")
    return prefix


class ObjectTypeElementsApiViewTests(TestCase):
    """Browse on empty query loads first page (aligned with rule picker)."""

    @classmethod
    def setUpTestData(cls):
        cls.prefix_a = _prefix("10.60.0.0/24")
        cls.prefix_b = _prefix("10.60.1.0/24")
        cls.prefix_ct = ContentType.objects.get_for_model(Prefix)
        cls.type_config = TypeConfig.objects.create(
            name="Picker Prefix Zones",
            content_type=cls.prefix_ct,
            matching_class=MatchingClassChoices.ZONE,
            display_template="{prefix}",
        )

    def _api_url(self, **params):
        base = reverse("plugins:netbox_nsm:object_type_elements_api")
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query}" if query else base

    def test_empty_query_returns_first_page(self):
        url = self._api_url(ct_id=self.prefix_ct.pk, q="")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertNotIn("error", data)
        self.assertGreater(data.get("count", 0), 0)
        self.assertTrue(data["results"])
        ids = {item["id"] for item in data["results"]}
        self.assertIn(self.prefix_a.pk, ids)
        self.assertIn(self.prefix_b.pk, ids)

    def test_single_char_query_not_rejected(self):
        url = self._api_url(ct_id=self.prefix_ct.pk, q="1")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        data = json.loads(response.content)
        self.assertNotEqual(data.get("error"), "min_query")
