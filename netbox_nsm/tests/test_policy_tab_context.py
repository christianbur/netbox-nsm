"""Policy tab context helpers."""

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.policy_tab_context import (
    DEFAULT_GRID_LOAD_LIMIT,
    GRID_AUTO_LOAD_ALL_MAX,
    GRID_LOAD_MORE_STEP,
    POLICY_GRID_CLIENT_MAX,
    PROGRESSIVE_LOAD_STEPS,
    PROGRESSIVE_LOAD_STEPS_FINE,
    build_policy_group_grid_config,
    resolve_policy_grid_initial_load_target,
    resolve_policy_grid_load_target,
)


def _sample_policy_layout():
    return [
        {
            "kind": "object",
            "slug": "source",
            "label": "Source",
            "group": {
                "columns": [{"key": "source::ct_1", "label": "Zones"}],
            },
        },
    ]


class PolicyGridLoadTargetTests(SimpleTestCase):
    def test_loads_all_rows_up_to_client_max(self):
        self.assertEqual(resolve_policy_grid_load_target(4000), 4000)

    def test_caps_at_client_max_when_above(self):
        total = POLICY_GRID_CLIENT_MAX + 5000
        self.assertEqual(resolve_policy_grid_load_target(total), POLICY_GRID_CLIENT_MAX)

    def test_initial_load_matches_full_staged_target(self):
        total = POLICY_GRID_CLIENT_MAX + 13000
        self.assertEqual(
            resolve_policy_grid_load_target(total),
            POLICY_GRID_CLIENT_MAX,
        )
        self.assertEqual(
            resolve_policy_grid_initial_load_target(total),
            POLICY_GRID_CLIENT_MAX,
        )

    def test_initial_load_all_when_within_client_max(self):
        self.assertEqual(resolve_policy_grid_initial_load_target(4000), 4000)

    def test_progressive_steps_exponential(self):
        self.assertEqual(PROGRESSIVE_LOAD_STEPS[:3], (10, 20, 40))
        self.assertIn(POLICY_GRID_CLIENT_MAX, PROGRESSIVE_LOAD_STEPS)

    def test_progressive_steps_fine_for_small_sets(self):
        self.assertEqual(PROGRESSIVE_LOAD_STEPS_FINE[0], 5)
        self.assertIn(250, PROGRESSIVE_LOAD_STEPS_FINE)

    def test_load_more_step_constant(self):
        self.assertEqual(GRID_LOAD_MORE_STEP, 2000)

    def test_empty_total_uses_default_cap(self):
        self.assertEqual(resolve_policy_grid_load_target(0), DEFAULT_GRID_LOAD_LIMIT)
        self.assertEqual(
            resolve_policy_grid_initial_load_target(0),
            DEFAULT_GRID_LOAD_LIMIT,
        )

    def test_auto_load_max_matches_client_max(self):
        self.assertEqual(GRID_AUTO_LOAD_ALL_MAX, POLICY_GRID_CLIENT_MAX)


class PolicyGroupGridConfigTests(SimpleTestCase):
    def test_group_config_without_group_by(self):
        request = RequestFactory().get("/rules/")
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertIn("groupByOptions", cfg)
        self.assertIn("groupByNotAllowedMessage", cfg)
        self.assertNotIn("groupModeLabels", cfg)
        self.assertNotIn("groupMode", cfg)
        self.assertNotIn("groupBy", cfg)
        self.assertNotIn("groupByEnabled", cfg)

    def test_group_config_with_collapsed_default(self):
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertEqual(cfg["groupBy"], "col:source::ct_1")
        self.assertTrue(cfg["groupByEnabled"])
        self.assertEqual(cfg["groupColumnLabel"], "Group")
        self.assertEqual(cfg["groupExpansionMode"], "all_collapsed")

    def test_group_config_source_column_collapsed_all(self):
        """Regression: exact production URL must not shadow gettext _."""
        layout = [
            {
                "kind": "object",
                "slug": "source",
                "label": "Source",
                "group": {
                    "columns": [{"key": "source::ct_236", "label": "Zones"}],
                },
            },
        ]
        request = RequestFactory().get(
            "/plugins/netbox-nsm/rulebooks/2/rules/"
            "?group_by=col%3Asource%3A%3Act_236"
            "&collapsed=all"
        )
        cfg = build_policy_group_grid_config(request, layout)
        self.assertEqual(cfg["groupBy"], "col:source::ct_236")
        self.assertEqual(cfg["groupColumnLabel"], "Group")
        self.assertEqual(cfg["groupExpansionMode"], "all_collapsed")
        self.assertNotIn("groupBy2", cfg)

    def test_group_config_resolves_legacy_area_header_alias(self):
        layout = [
            {
                "kind": "object",
                "slug": "source",
                "label": "Source",
                "group": {
                    "columns": [{"key": "source::ct_236", "label": "Zones"}],
                },
            },
        ]
        request = RequestFactory().get(
            "/rules/?group_by=col:Source::Zones&group_by_2=rulebook"
        )
        cfg = build_policy_group_grid_config(
            request,
            layout,
            include_rulebook=True,
        )
        self.assertEqual(cfg["groupBy"], "col:source::ct_236")
        self.assertEqual(cfg["groupBy2"], "rulebook")

    def test_group_config_destination_column_collapsed_all(self):
        """Regression: single-level group_by must not shadow gettext _."""
        layout = [
            {
                "kind": "object",
                "slug": "destination",
                "label": "Destination",
                "group": {
                    "columns": [{"key": "destination::ct_236", "label": "Zones"}],
                },
            },
        ]
        request = RequestFactory().get(
            "/plugins/netbox-nsm/rulebooks/19/rules/"
            "?group_by=col%3Adestination%3A%3Act_236"
            "&group_mode=value&collapsed=all"
        )
        cfg = build_policy_group_grid_config(request, layout)
        self.assertEqual(cfg["groupBy"], "col:destination::ct_236")
        self.assertNotIn("groupMode", cfg)
        self.assertEqual(cfg["groupColumnLabel"], "Group")
        self.assertEqual(cfg["groupExpansionMode"], "all_collapsed")
        self.assertNotIn("groupBy2", cfg)

    def test_group_config_with_expanded_keys(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&expanded=col:source::ct_1::prod"
        )
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertEqual(cfg["groupExpansionMode"], "expanded")
        self.assertEqual(cfg["groupExpandedKeys"], ["col:source::ct_1::prod"])

    def test_group_config_secondary_level(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&group_by_2=tag:source"
        )
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertEqual(cfg["groupBy2"], "tag:source")
        self.assertNotIn("groupMode", cfg)
        self.assertNotIn("groupMode2", cfg)

    def test_group_config_rulebook_plus_column(self):
        request = RequestFactory().get(
            "/rules/?group_by=rulebook&group_by_2=col:source::ct_1"
        )
        cfg = build_policy_group_grid_config(
            request,
            _sample_policy_layout(),
            include_rulebook=True,
        )
        self.assertEqual(cfg["groupBy"], "rulebook")
        self.assertEqual(cfg["groupBy2"], "col:source::ct_1")

    def test_group_config_ignores_legacy_group_mode_params(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&group_mode=value&group_by_2=tag:source&group_mode_2=value"
        )
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertEqual(cfg["groupBy"], "col:source::ct_1")
        self.assertEqual(cfg["groupBy2"], "tag:source")
        self.assertNotIn("groupMode", cfg)
        self.assertNotIn("groupMode2", cfg)

    def test_group_config_expand_all(self):
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1&expanded=all")
        cfg = build_policy_group_grid_config(request, _sample_policy_layout())
        self.assertEqual(cfg["groupExpansionMode"], "all_expanded")
