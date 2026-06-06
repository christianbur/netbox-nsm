"""Policy grid filtered-rules cache (10-minute TTL, regroup reuse)."""

import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse

from netbox_nsm.policy_grid_service import (
    POLICY_GRID_RULES_CACHE_TTL,
    all_rules_grid_rules_cache_key,
    policy_grid_rules_cache_key,
    resolve_policy_grid_filtered_rules,
)
from netbox_nsm.views.all_rules_grid_api import AllRulesGridApiView
from netbox_nsm.views.policy_grid_api import RulebookPolicyGridApiView
from utilities.testing import TestCase


class PolicyGridRulesCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.contenttypes.models import ContentType

        from netbox_nsm.models import Rulebook, TypeConfig
        from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields

        cls.ct = ContentType.objects.order_by("pk").first()
        cls.tc, _ = TypeConfig.objects.get_or_create(
            content_type=cls.ct,
            defaults={"name": "Rules Cache Type"},
        )
        cls.rulebook = Rulebook.objects.create(
            name="Rules Cache RB",
            rulebook_type="policy",
        )
        ensure_system_rulebook_fields(cls.rulebook)

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_policy_grid_rules_cache_key_ignores_grouping(self):
        key_a = policy_grid_rules_cache_key(self.rulebook.pk, None)
        key_b = policy_grid_rules_cache_key(self.rulebook.pk, {"name": {"filter": "x"}})
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(
            key_a,
            policy_grid_rules_cache_key(self.rulebook.pk, None),
        )

    def test_all_rules_grid_rules_cache_key_scopes_rulebook(self):
        key_all = all_rules_grid_rules_cache_key(None, None)
        key_scoped = all_rules_grid_rules_cache_key(self.rulebook.pk, None)
        self.assertNotEqual(key_all, key_scoped)

    def test_resolve_policy_grid_filtered_rules_populates_cache(self):
        import netbox_nsm.views.rulebook as rulebook_views

        cache_key = policy_grid_rules_cache_key(self.rulebook.pk, None)
        self.assertIsNone(cache.get(cache_key))

        resolve_policy_grid_filtered_rules(
            self.rulebook,
            None,
            rulebook_views,
            use_cached=False,
        )

        cached_pks = cache.get(cache_key)
        self.assertIsNotNone(cached_pks)
        self.assertEqual(cached_pks, [])

    def test_resolve_policy_grid_filtered_rules_use_cached_skips_db_filter(self):
        import netbox_nsm.views.rulebook as rulebook_views

        cache_key = policy_grid_rules_cache_key(self.rulebook.pk, None)
        cache.set(cache_key, [101, 102, 103], POLICY_GRID_RULES_CACHE_TTL)

        with patch(
            "netbox_nsm.policy_grid_service.policy_grid_filtered_rules"
        ) as mock_filtered:
            with patch(
                "netbox_nsm.policy_grid_service._rules_from_cached_pks",
                return_value=["cached-rules"],
            ) as mock_from_cache:
                rules = resolve_policy_grid_filtered_rules(
                    self.rulebook,
                    None,
                    rulebook_views,
                    use_cached=True,
                )

        mock_filtered.assert_not_called()
        mock_from_cache.assert_called_once_with(self.rulebook, [101, 102, 103])
        self.assertEqual(rules, ["cached-rules"])

    def test_resolve_policy_grid_filtered_rules_refresh_deletes_cache(self):
        import netbox_nsm.views.rulebook as rulebook_views

        cache_key = policy_grid_rules_cache_key(self.rulebook.pk, None)
        cache.set(cache_key, [101, 102, 103], POLICY_GRID_RULES_CACHE_TTL)

        resolve_policy_grid_filtered_rules(
            self.rulebook,
            None,
            rulebook_views,
            refresh_cache=True,
        )

        cached_pks = cache.get(cache_key)
        self.assertIsNotNone(cached_pks)
        self.assertEqual(cached_pks, [])

    def test_resolve_policy_grid_filtered_rules_refresh_ignores_use_cached(self):
        import netbox_nsm.views.rulebook as rulebook_views

        cache_key = policy_grid_rules_cache_key(self.rulebook.pk, None)
        cache.set(cache_key, [101, 102, 103], POLICY_GRID_RULES_CACHE_TTL)

        with patch(
            "netbox_nsm.policy_grid_service.policy_grid_filtered_rules",
            return_value=[],
        ) as mock_filtered:
            resolve_policy_grid_filtered_rules(
                self.rulebook,
                None,
                rulebook_views,
                use_cached=True,
                refresh_cache=True,
            )

        mock_filtered.assert_called_once()

    def test_policy_grid_api_accepts_use_cached_param(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_policy_grid_api",
                args=[self.rulebook.pk],
            )
            + "?use_cached=1"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookPolicyGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("rowData", data)

    def test_policy_grid_api_accepts_refresh_param(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = (
            reverse(
                "plugins:netbox_nsm:rulebook_policy_grid_api",
                args=[self.rulebook.pk],
            )
            + "?refresh=1"
        )
        request = RequestFactory().get(url)
        request.user = self.user
        response = RulebookPolicyGridApiView.as_view()(request, pk=self.rulebook.pk)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("rowData", data)

    def test_all_rules_grid_api_accepts_use_cached_param(self):
        self.add_permissions("netbox_nsm.view_rule")
        url = reverse("plugins:netbox_nsm:all_rules_grid_api") + "?use_cached=1"
        request = RequestFactory().get(url)
        request.user = self.user
        response = AllRulesGridApiView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("rowData", data)
