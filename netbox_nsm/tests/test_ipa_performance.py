"""Tests for IP Analyzer performance (lazy load, cache, settings)."""

from __future__ import annotations

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from netbox_nsm.analyzers.ip_analyzer.ipa_perf import (
    build_ipa_cache_key,
    cached_ipa_payload,
    get_ipa_analyzer_cache_timeout,
    get_ipa_analyzer_timeout_ms,
    ipa_lazy_context,
    ipa_lazy_load_enabled,
    parse_lazy_flag,
    parse_refresh_flag,
    should_bypass_ipa_cache,
)
from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
    _ipa_ipam_ip_keys_for_object,
)


class _FakeRequest:
    def __init__(self, params=None):
        self.GET = params or {}


class IpaPerfFlagTests(SimpleTestCase):
    def test_parse_lazy_flag(self):
        self.assertFalse(parse_lazy_flag(_FakeRequest({})))
        self.assertTrue(parse_lazy_flag(_FakeRequest({"lazy": "1"})))
        self.assertTrue(parse_lazy_flag(_FakeRequest({"lazy": "true"})))

    def test_parse_refresh_flag(self):
        self.assertFalse(parse_refresh_flag(_FakeRequest({})))
        self.assertTrue(parse_refresh_flag(_FakeRequest({"refresh": "1"})))

    def test_should_bypass_cache(self):
        self.assertTrue(should_bypass_ipa_cache(lazy=False, refresh=False, cache_timeout=300))
        self.assertTrue(should_bypass_ipa_cache(lazy=True, refresh=True, cache_timeout=300))
        self.assertFalse(should_bypass_ipa_cache(lazy=True, refresh=False, cache_timeout=300))
        self.assertTrue(should_bypass_ipa_cache(lazy=True, refresh=False, cache_timeout=0))


class IpaCacheKeyTests(SimpleTestCase):
    def test_merge_cache_key_sorts_object_refs(self):
        key_a = build_ipa_cache_key(
            user_id=7,
            mode="merge",
            lazy=True,
            selections=[
                {"ct": "10", "pk": "2"},
                {"ct": "9", "pk": "1"},
            ],
        )
        key_b = build_ipa_cache_key(
            user_id=7,
            mode="merge",
            lazy=True,
            selections=[
                {"ct": "9", "pk": "1"},
                {"ct": "10", "pk": "2"},
            ],
        )
        self.assertEqual(key_a, key_b)

    def test_cache_key_varies_by_user_mode_and_lazy(self):
        base = build_ipa_cache_key(
            user_id=1,
            mode="merge",
            lazy=True,
            selections=[{"ct": "1", "pk": "1"}],
        )
        other_user = build_ipa_cache_key(
            user_id=2,
            mode="merge",
            lazy=True,
            selections=[{"ct": "1", "pk": "1"}],
        )
        full_load = build_ipa_cache_key(
            user_id=1,
            mode="merge",
            lazy=False,
            selections=[{"ct": "1", "pk": "1"}],
        )
        diff_key = build_ipa_cache_key(
            user_id=1,
            mode="diff",
            lazy=True,
            sides=[
                {
                    "label": "A",
                    "selections": [{"ct": "1", "pk": "1"}],
                },
                {
                    "label": "B",
                    "selections": [{"ct": "2", "pk": "2"}],
                },
            ],
        )
        self.assertNotEqual(base, other_user)
        self.assertNotEqual(base, full_load)
        self.assertNotEqual(base, diff_key)


class IpaCachePayloadTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cached_payload_stores_and_returns(self):
        calls = {"count": 0}

        def builder():
            calls["count"] += 1
            return {"mode": "merge", "leaf_count": 3}

        payload, from_cache = cached_ipa_payload("nsm:test:ipa", 300, builder)
        self.assertFalse(from_cache)
        self.assertEqual(payload["leaf_count"], 3)
        self.assertEqual(calls["count"], 1)

        payload2, from_cache2 = cached_ipa_payload("nsm:test:ipa", 300, builder)
        self.assertTrue(from_cache2)
        self.assertEqual(payload2["leaf_count"], 3)
        self.assertEqual(calls["count"], 1)

    def test_cache_disabled_when_timeout_zero(self):
        calls = {"count": 0}

        def builder():
            calls["count"] += 1
            return {"mode": "merge"}

        cached_ipa_payload("nsm:test:ipa:zero", 0, builder)
        cached_ipa_payload("nsm:test:ipa:zero", 0, builder)
        self.assertEqual(calls["count"], 2)


@override_settings(
    PLUGINS_CONFIG={
        "netbox_nsm": {
            "ipa_analyzer_timeout_ms": 240000,
            "ipa_analyzer_cache_timeout": 600,
        }
    }
)
class IpaPluginSettingTests(SimpleTestCase):
    def test_timeout_and_cache_settings(self):
        self.assertEqual(get_ipa_analyzer_timeout_ms(), 240000)
        self.assertEqual(get_ipa_analyzer_cache_timeout(), 600)


class IpaLazyContextTests(SimpleTestCase):
    def test_lazy_context_toggles_flag(self):
        self.assertFalse(ipa_lazy_load_enabled())
        with ipa_lazy_context(True):
            self.assertTrue(ipa_lazy_load_enabled())
        self.assertFalse(ipa_lazy_load_enabled())


class IpaLazyBehaviorTests(SimpleTestCase):
    def test_lazy_skips_ipam_child_enumeration(self):
        ipam_obj = type("Prefix", (), {})()

        with ipa_lazy_context(True):
            keys, resolved = _ipa_ipam_ip_keys_for_object(ipam_obj)
        self.assertEqual(keys, set())
        self.assertFalse(resolved)


class IpaLazyFastPathTests(SimpleTestCase):
    def test_lazy_cell_tree_fast_path_skips_full_enrichment(self):
        from unittest.mock import patch

        from netbox_nsm.analyzers.ip_analyzer.ipa_object_tree import (
            _build_ipa_cell_object_tree,
        )

        raw = [{"ct": "1", "pk": "2", "name": "10.0.0.0/8"}]
        obj_by_key = {(1, 2): type("O", (), {"get_absolute_url": lambda self: "#", "_meta": type("M", (), {"model_name": "nsm_address"})()})()}
        with ipa_lazy_context(True):
            with patch(
                "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._reorganize_ipa_object_tree_by_ipam_prefix_hierarchy"
            ) as reorganize:
                with patch(
                    "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._enrich_ipa_object_tree_networks_from_objects"
                ):
                    with patch(
                        "netbox_nsm.analyzers.ip_analyzer.ipa_object_tree._flatten_cell_selections_to_address_nodes",
                        return_value=[{"name": "10.0.0.0/8", "ct": 1, "pk": 2}],
                    ):
                        nodes = _build_ipa_cell_object_tree(raw, obj_by_key)
        reorganize.assert_not_called()
        self.assertEqual(len(nodes), 1)
        self.assertNotIn("addr_drilldown_lazy", nodes[0])
