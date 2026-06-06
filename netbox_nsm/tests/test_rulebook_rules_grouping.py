"""Policy rule grouping by object column or field tag."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebook_rules_grouping import (
    COLLAPSE_ALL,
    GROUP_MODE_SET,
    GROUP_MODE_VALUE,
    UNGROUPED_GROUP_KEY,
    assign_rules_to_groups,
    assign_rules_to_groups_for_union,
    build_rulebook_rules_group_options,
    build_rule_display_items,
    filter_collapsed_display_items,
    filter_group_display_items,
    parse_collapsed_keys,
    parse_expanded_keys,
    parse_group_by_mode,
    parse_rulebook_rules_group_modes,
    parse_rulebook_rules_group_by,
    parse_rulebook_rules_group_levels,
    rules_grouping_enabled,
    resolve_group_by_value,
    resolve_group_expansion,
    resolve_request_group_expansion,
    validate_rulebook_rules_group_request,
)


def _bucket(key, label):
    return {"key": key, "label": label, "url": "#"}


class PolicyRuleGroupingTests(SimpleTestCase):
    def _layout(self):
        return [
            {
                "kind": "object",
                "slug": "source",
                "label": "Source",
                "group": {
                    "columns": [
                        {"key": "source::ct_1", "label": "Zones"},
                    ]
                },
            },
            {
                "kind": "object",
                "slug": "destination",
                "label": "Destination",
                "group": {"columns": [{"key": "destination::ct_1", "label": "Zones"}]},
            },
        ]

    def test_build_rulebook_rules_group_options(self):
        opts = build_rulebook_rules_group_options(self._layout())
        values = [o["value"] for o in opts]
        self.assertIn("", values)
        self.assertIn("tag:source", values)
        self.assertIn("tag:destination", values)
        self.assertIn("col:source::ct_1", values)
        self.assertIn("col:destination::ct_1", values)

    def test_parse_rulebook_rules_group_by_validates_layout(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        self.assertEqual(
            parse_rulebook_rules_group_by(request, rules_layout=layout),
            "col:source::ct_1",
        )
        bad = RequestFactory().get("/rules/?group_by=zone")
        self.assertEqual(parse_rulebook_rules_group_by(bad, rules_layout=layout), "")

    def test_resolve_group_by_value_maps_area_header_alias(self):
        layout = self._layout()
        self.assertEqual(
            resolve_group_by_value("col:Source::Zones", layout),
            "col:source::ct_1",
        )
        request = RequestFactory().get("/rules/?group_by=col:Source::Zones")
        self.assertEqual(
            parse_rulebook_rules_group_by(request, rules_layout=layout),
            "col:source::ct_1",
        )

    def test_parse_rulebook_rules_group_levels_resolves_secondary_alias(self):
        layout = self._layout()
        request = RequestFactory().get(
            "/rules/?group_by=rulebook&group_by_2=col:Source::Zones"
        )
        levels = parse_rulebook_rules_group_levels(
            request,
            rules_layout=layout,
            include_rulebook=True,
        )
        self.assertEqual(levels, ["rulebook", "col:source::ct_1"])

    def test_assign_rules_to_groups_for_union_remaps_bucket_keys(self):
        rule = SimpleNamespace(pk=1, rulebook_id=10)
        rb_maps = {10: {"Source::Zones": "source::ct_1"}}
        with patch(
            "netbox_nsm.rulebook_rules_grouping._assign_by_column",
            return_value={
                1: [_bucket("col:source::ct_1::prod", "prod")],
            },
        ):
            assigned = assign_rules_to_groups_for_union(
                [rule],
                "col:Source::Zones",
                rb_maps,
            )
        self.assertEqual(
            assigned[1][0]["key"],
            "col:Source::Zones::prod",
        )

    def test_assign_rules_to_groups_for_union_batches_by_local_key(self):
        rules = [
            SimpleNamespace(pk=1, rulebook_id=10),
            SimpleNamespace(pk=2, rulebook_id=10),
        ]
        rb_maps = {10: {"Source::Zones": "source::ct_1"}}
        batch_sizes = []

        def fake_assign(batch, mode, *, group_mode=GROUP_MODE_SET, rulebook=None):
            del group_mode, rulebook
            batch_sizes.append(len(batch))
            return {
                rule.pk: [_bucket(f"{mode}::{rule.pk}", str(rule.pk))] for rule in batch
            }

        with patch(
            "netbox_nsm.rulebook_rules_grouping.assign_rules_to_groups",
            side_effect=fake_assign,
        ):
            assigned = assign_rules_to_groups_for_union(
                rules,
                "col:Source::Zones",
                rb_maps,
            )
        self.assertEqual(batch_sizes, [2])
        self.assertEqual(assigned[1][0]["key"], "col:Source::Zones::1")
        self.assertEqual(assigned[2][0]["key"], "col:Source::Zones::2")

    def test_resolve_request_group_expansion_skips_preview_when_collapsed_default(self):
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        expanded, collapsed, level = resolve_request_group_expansion(
            request,
            group_levels=["col:source::ct_1"],
        )
        self.assertIsNone(expanded)
        self.assertEqual(collapsed, {COLLAPSE_ALL})
        self.assertIsNone(level)

    def test_resolve_request_group_expansion_honors_collapsed_param(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&collapsed=col:source::ct_1::prod"
        )
        expanded, collapsed, level = resolve_request_group_expansion(
            request,
            group_levels=["col:source::ct_1"],
        )
        self.assertIsNone(expanded)
        self.assertEqual(collapsed, {"col:source::ct_1::prod"})
        self.assertIsNone(level)

    def test_validate_rulebook_rules_group_request_rejects_unknown_field(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=col:source::ct_999")
        self.assertIsNotNone(
            validate_rulebook_rules_group_request(request, rules_layout=layout)
        )

    def test_validate_rulebook_rules_group_request_accepts_configured_column(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        self.assertIsNone(
            validate_rulebook_rules_group_request(request, rules_layout=layout)
        )

    def test_validate_rulebook_rules_group_request_rejects_rulebook_without_flag(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=rulebook")
        self.assertIsNotNone(
            validate_rulebook_rules_group_request(request, rules_layout=layout)
        )

    def test_validate_rulebook_rules_group_request_accepts_rulebook_when_enabled(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=rulebook")
        self.assertIsNone(
            validate_rulebook_rules_group_request(
                request,
                rules_layout=layout,
                include_rulebook=True,
            )
        )

    def test_build_rulebook_rules_group_options_excludes_system_columns(self):
        layout = self._layout() + [
            {"kind": "system", "slug": "name", "label": "Name"},
        ]
        values = {opt["value"] for opt in build_rulebook_rules_group_options(layout)}
        self.assertNotIn("col:name", values)
        self.assertNotIn("name", values)

    def test_parse_group_by_mode_always_set(self):
        self.assertEqual(
            parse_group_by_mode(RequestFactory().get("/rules/?group_mode=set")),
            GROUP_MODE_SET,
        )
        self.assertEqual(
            parse_group_by_mode(RequestFactory().get("/rules/?group_mode=value")),
            GROUP_MODE_SET,
        )
        self.assertEqual(
            parse_group_by_mode(RequestFactory().get("/rules/")),
            GROUP_MODE_SET,
        )

    def test_parse_rulebook_rules_group_modes_always_set(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&group_mode=value&group_by_2=tag:source&group_mode_2=value"
        )
        primary, secondary = parse_rulebook_rules_group_modes(request)
        self.assertEqual(primary, GROUP_MODE_SET)
        self.assertEqual(secondary, GROUP_MODE_SET)

    def test_parse_rulebook_rules_group_levels_max_two(self):
        layout = self._layout()
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1"
            "&group_by_2=tag:source"
            "&group_by_3=tag:destination"
        )
        levels = parse_rulebook_rules_group_levels(request, rules_layout=layout)
        self.assertEqual(levels, ["col:source::ct_1", "tag:source"])

    def test_parse_rulebook_rules_group_levels_single(self):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        levels = parse_rulebook_rules_group_levels(request, rules_layout=layout)
        self.assertEqual(levels, ["col:source::ct_1"])

    def test_parse_rulebook_rules_group_levels_rulebook_plus_column(self):
        layout = self._layout()
        request = RequestFactory().get(
            "/rules/?group_by=rulebook&group_by_2=col:source::ct_1"
        )
        levels = parse_rulebook_rules_group_levels(
            request,
            rules_layout=layout,
            include_rulebook=True,
        )
        self.assertEqual(levels, ["rulebook", "col:source::ct_1"])

    def test_parse_rulebook_rules_group_levels_rulebook_ignores_duplicate_secondary(
        self,
    ):
        layout = self._layout()
        request = RequestFactory().get("/rules/?group_by=rulebook&group_by_2=rulebook")
        levels = parse_rulebook_rules_group_levels(
            request,
            rules_layout=layout,
            include_rulebook=True,
        )
        self.assertEqual(levels, ["rulebook"])

    def test_validate_rulebook_rules_group_request_accepts_two_levels(self):
        layout = self._layout()
        request = RequestFactory().get(
            "/rules/?group_by=rulebook&group_by_2=col:source::ct_1"
        )
        self.assertIsNone(
            validate_rulebook_rules_group_request(
                request,
                rules_layout=layout,
                include_rulebook=True,
            )
        )

    def test_assign_by_object_column_value_mode(self):
        source_field = SimpleNamespace(slug="source")
        zone = SimpleNamespace(name="prod", color="#111", pk=1)
        item = SimpleNamespace(
            exclude=False,
            field=source_field,
            content_type_id=1,
            assigned_object=zone,
        )
        rule = SimpleNamespace(
            pk=10,
            _cached_object_items=[item],
            _cached_group_items=[],
        )
        with patch(
            "netbox_nsm.display_utils.get_display_template_map",
            return_value={},
        ):
            with patch(
                "netbox_nsm.display_utils.render_object_display",
                return_value="prod",
            ):
                mapping = assign_rules_to_groups(
                    [rule], "col:source::ct_1", group_mode=GROUP_MODE_VALUE
                )
        self.assertEqual(len(mapping[10]), 1)
        self.assertEqual(mapping[10][0]["label"], "prod")

    def test_assign_value_mode_multiple_groups(self):
        source_field = SimpleNamespace(slug="source")
        zones = [
            SimpleNamespace(name="prod", color="#111", pk=1),
            SimpleNamespace(name="dev-3", color="#222", pk=2),
        ]
        items = [
            SimpleNamespace(
                exclude=False,
                field=source_field,
                content_type_id=1,
                assigned_object=zone,
            )
            for zone in zones
        ]
        rule = SimpleNamespace(
            pk=10,
            _cached_object_items=items,
            _cached_group_items=[],
        )
        with patch(
            "netbox_nsm.display_utils.get_display_template_map",
            return_value={},
        ):
            with patch(
                "netbox_nsm.display_utils.render_object_display",
                side_effect=lambda obj, *_args: obj.name,
            ):
                mapping = assign_rules_to_groups(
                    [rule], "col:source::ct_1", group_mode=GROUP_MODE_VALUE
                )
        labels = sorted(bucket["label"] for bucket in mapping[10])
        self.assertEqual(labels, ["dev-3", "prod"])

        items = build_rule_display_items(
            [rule],
            rule_to_buckets=mapping,
            enabled=True,
        )
        rule_rows = [item for item in items if item["kind"] == "rule"]
        self.assertEqual(len(rule_rows), 2)

    def test_assign_set_mode_combined_group(self):
        source_field = SimpleNamespace(slug="source")
        zones = [
            SimpleNamespace(name="prod", color="#111", pk=1),
            SimpleNamespace(name="dev-3", color="#222", pk=2),
        ]
        items = [
            SimpleNamespace(
                exclude=False,
                field=source_field,
                content_type_id=1,
                assigned_object=zone,
            )
            for zone in zones
        ]
        rule = SimpleNamespace(
            pk=10,
            _cached_object_items=items,
            _cached_group_items=[],
        )
        with patch(
            "netbox_nsm.display_utils.get_display_template_map",
            return_value={},
        ):
            with patch(
                "netbox_nsm.display_utils.render_object_display",
                side_effect=lambda obj, *_args: obj.name,
            ):
                mapping = assign_rules_to_groups(
                    [rule], "col:source::ct_1", group_mode=GROUP_MODE_SET
                )
        self.assertEqual(len(mapping[10]), 1)
        self.assertEqual(mapping[10][0]["label"], "dev-3\nprod")
        self.assertEqual(
            mapping[10][0]["key"],
            "col:source::ct_1::set::dev-3|prod",
        )

        items = build_rule_display_items(
            [rule],
            rule_to_buckets=mapping,
            enabled=True,
        )
        rule_rows = [item for item in items if item["kind"] == "rule"]
        self.assertEqual(len(rule_rows), 1)

    def test_assign_default_uses_set_mode(self):
        source_field = SimpleNamespace(slug="source")
        zones = [
            SimpleNamespace(name="prod", color="#111", pk=1),
            SimpleNamespace(name="dev-3", color="#222", pk=2),
        ]
        items = [
            SimpleNamespace(
                exclude=False,
                field=source_field,
                content_type_id=1,
                assigned_object=zone,
            )
            for zone in zones
        ]
        rule = SimpleNamespace(
            pk=10,
            _cached_object_items=items,
            _cached_group_items=[],
        )
        with patch(
            "netbox_nsm.display_utils.get_display_template_map",
            return_value={},
        ):
            with patch(
                "netbox_nsm.display_utils.render_object_display",
                side_effect=lambda obj, *_args: obj.name,
            ):
                mapping = assign_rules_to_groups([rule], "col:source::ct_1")
        self.assertEqual(len(mapping[10]), 1)
        self.assertEqual(mapping[10][0]["label"], "dev-3\nprod")

    def test_filter_collapsed(self):
        items = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={
                1: [_bucket("col:source::ct_1::prod", "prod")],
                2: [_bucket("col:source::ct_1::prod", "prod")],
            },
            enabled=True,
        )
        filtered = filter_collapsed_display_items(items, {"col:source::ct_1::prod"})
        self.assertEqual([item["kind"] for item in filtered], ["group"])

    def test_collapse_all(self):
        items = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={
                1: [_bucket("col:source::ct_1::prod", "prod")],
                2: [_bucket("col:source::ct_1::dev", "dev")],
            },
            enabled=True,
        )
        filtered = filter_group_display_items(items, collapsed_keys={COLLAPSE_ALL})
        self.assertEqual([item["kind"] for item in filtered], ["group", "group"])

    def test_parse_collapsed_all(self):
        self.assertEqual(parse_collapsed_keys("all"), {COLLAPSE_ALL})
        self.assertEqual(parse_collapsed_keys("*"), {COLLAPSE_ALL})

    def test_expanded_whitelist(self):
        items = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={
                1: [_bucket("col:source::ct_1::prod", "prod")],
                2: [_bucket("col:source::ct_1::dev", "dev")],
            },
            enabled=True,
        )
        filtered = filter_group_display_items(
            items,
            expanded_keys={"col:source::ct_1::dev"},
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds.count("group"), 2)
        self.assertEqual(kinds.count("rule"), 1)
        rule_items = [item for item in filtered if item["kind"] == "rule"]
        self.assertEqual(rule_items[0]["group_key"], "col:source::ct_1::dev")

    def test_resolve_group_expansion_defaults_collapsed(self):
        request = RequestFactory().get("/rules/?group_by=col:source::ct_1")
        expanded, collapsed, default_level = resolve_group_expansion(
            request, group_by="col:source::ct_1"
        )
        self.assertIsNone(expanded)
        self.assertEqual(collapsed, {COLLAPSE_ALL})
        self.assertIsNone(default_level)

    def test_resolve_group_expansion_expanded_param(self):
        request = RequestFactory().get(
            "/rules/?group_by=col:source::ct_1&expanded=col:source::ct_1::dev"
        )
        expanded, collapsed, default_level = resolve_group_expansion(
            request, group_by="col:source::ct_1"
        )
        self.assertEqual(expanded, {"col:source::ct_1::dev"})
        self.assertIsNone(collapsed)
        self.assertIsNone(default_level)

    def test_resolve_group_expansion_expand_all(self):
        from netbox_nsm.rulebook_rules_grouping import EXPAND_ALL

        request = RequestFactory().get("/rules/?group_by=col:source::ct_1&expanded=all")
        expanded, collapsed, _default = resolve_group_expansion(
            request, group_by="col:source::ct_1"
        )
        self.assertEqual(expanded, {EXPAND_ALL})

    def test_parse_group_default_expanded(self):
        from netbox_nsm.rulebook_rules_grouping import parse_group_default_expanded

        self.assertEqual(parse_group_default_expanded(RequestFactory().get("/")), 0)
        self.assertEqual(
            parse_group_default_expanded(RequestFactory().get("/?group_expanded=1")),
            1,
        )
        self.assertEqual(
            parse_group_default_expanded(RequestFactory().get("/?group_expanded=-1")),
            -1,
        )

    def test_assign_by_rulebook(self):
        rb = SimpleNamespace(pk=5, name="Security Rules RB")
        rb.get_absolute_url = lambda: "/rb/5/"
        rule = SimpleNamespace(pk=1, rulebook=rb)
        mapping = assign_rules_to_groups([rule], "rulebook")
        self.assertEqual(mapping[1][0]["label"], "Security Rules RB")
        self.assertEqual(mapping[1][0]["key"], "rulebook::5")

    def test_nested_group_display_items(self):
        source_field = SimpleNamespace(slug="source")
        dest_field = SimpleNamespace(slug="destination")
        zone = SimpleNamespace(name="prod", color="#111", pk=1)
        src_item = SimpleNamespace(
            exclude=False,
            field=source_field,
            content_type_id=1,
            assigned_object=zone,
        )
        tag = SimpleNamespace(slug="web", __str__=lambda self: "web")
        dest_obj = SimpleNamespace(tags=SimpleNamespace(all=lambda: [tag]))
        dest_item = SimpleNamespace(
            exclude=False,
            field=dest_field,
            content_type_id=1,
            assigned_object=dest_obj,
        )
        rule = SimpleNamespace(
            pk=10,
            _cached_object_items=[src_item, dest_item],
            _cached_group_items=[],
        )
        with patch(
            "netbox_nsm.display_utils.get_display_template_map",
            return_value={},
        ):
            with patch(
                "netbox_nsm.display_utils.render_object_display",
                return_value="prod",
            ):
                primary = assign_rules_to_groups(
                    [rule], "col:source::ct_1", group_mode=GROUP_MODE_VALUE
                )
                secondary = assign_rules_to_groups(
                    [rule], "tag:destination", group_mode=GROUP_MODE_VALUE
                )
        items = build_rule_display_items(
            [rule],
            rule_to_buckets=primary,
            rule_to_buckets_secondary=secondary,
        )
        group_levels = [
            item.get("group_level") for item in items if item["kind"] == "group"
        ]
        self.assertEqual(group_levels, [1, 2])
        self.assertEqual(len([item for item in items if item["kind"] == "rule"]), 1)

    def test_nested_group_hierarchy_order(self):
        """Level-1 group header, then level-2 headers + rules — no duplicate L1 rows."""
        primary_a = _bucket("col:source::ct_1::us", "United States")
        primary_b = _bucket("col:source::ct_1::de", "Germany")
        secondary_a = _bucket("tag:destination::2008", "2008")
        secondary_b = _bucket("tag:destination::2009", "2009")
        rule_a = SimpleNamespace(pk=1)
        rule_b = SimpleNamespace(pk=2)
        items = build_rule_display_items(
            [rule_a, rule_b],
            rule_to_buckets={
                1: [primary_a],
                2: [primary_b],
            },
            rule_to_buckets_secondary={
                1: [secondary_a],
                2: [secondary_b],
            },
        )
        kinds = [item["kind"] for item in items]
        self.assertEqual(
            kinds,
            ["group", "group", "rule", "group", "group", "rule"],
        )
        group_levels = [
            item.get("group_level") for item in items if item["kind"] == "group"
        ]
        self.assertEqual(group_levels, [1, 2, 1, 2])

    def test_collapsed_all_hides_nested_groups_and_rules(self):
        primary = _bucket("col:source::ct_1::us", "United States")
        secondary = _bucket("tag:destination::2008", "2008")
        items = build_rule_display_items(
            [SimpleNamespace(pk=1)],
            rule_to_buckets={1: [primary]},
            rule_to_buckets_secondary={1: [secondary]},
        )
        filtered = filter_group_display_items(items, collapsed_keys={COLLAPSE_ALL})
        self.assertEqual([item["kind"] for item in filtered], ["group"])
        self.assertEqual(filtered[0]["group_level"], 1)

    def _nested_two_level_items(self):
        primary = _bucket("rulebook::5", "Demo - Addresses")
        secondary_a = _bucket("col:source::ct_1::prod", "prod")
        secondary_b = _bucket("col:source::ct_1::dev", "dev")
        return build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={1: [primary], 2: [primary]},
            rule_to_buckets_secondary={1: [secondary_a], 2: [secondary_b]},
        )

    def test_nested_expand_level1_shows_level2_not_rules(self):
        items = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items,
            expanded_keys={"rulebook::5"},
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds.count("group"), 3)
        self.assertEqual(kinds.count("rule"), 0)
        levels = [
            item.get("group_level") for item in filtered if item["kind"] == "group"
        ]
        self.assertEqual(levels, [1, 2, 2])

    def test_nested_expand_level2_shows_rules(self):
        items = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items,
            expanded_keys={"rulebook::5::col:source::ct_1::prod"},
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds.count("group"), 2)
        self.assertEqual(kinds.count("rule"), 1)
        rule_items = [item for item in filtered if item["kind"] == "rule"]
        self.assertEqual(
            rule_items[0]["group_key"],
            "rulebook::5::col:source::ct_1::prod",
        )

    def test_nested_expand_level1_and_level2_shows_all_matching_rules(self):
        items = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items,
            expanded_keys={
                "rulebook::5",
                "rulebook::5::col:source::ct_1::prod",
            },
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds.count("group"), 3)
        self.assertEqual(kinds.count("rule"), 1)

    def test_nested_collapsed_level2_hides_rules(self):
        items = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items,
            collapsed_keys={"rulebook::5::col:source::ct_1::prod"},
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds.count("group"), 3)
        self.assertEqual(kinds.count("rule"), 1)
        rule_items = [item for item in filtered if item["kind"] == "rule"]
        self.assertEqual(
            rule_items[0]["group_key"],
            "rulebook::5::col:source::ct_1::dev",
        )

    def test_nested_collapsed_level1_hides_children(self):
        items = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items,
            collapsed_keys={"rulebook::5"},
        )
        kinds = [item["kind"] for item in filtered]
        self.assertEqual(kinds, ["group"])
        self.assertEqual(filtered[0]["group_level"], 1)

    def test_lazy_build_matches_filter_collapse_all(self):
        primary = _bucket("col:source::ct_1::us", "United States")
        secondary = _bucket("tag:destination::2008", "2008")
        rules = [SimpleNamespace(pk=1)]
        full = build_rule_display_items(
            rules,
            rule_to_buckets={1: [primary]},
            rule_to_buckets_secondary={1: [secondary]},
        )
        filtered = filter_group_display_items(full, collapsed_keys={COLLAPSE_ALL})
        lazy = build_rule_display_items(
            rules,
            rule_to_buckets={1: [primary]},
            rule_to_buckets_secondary={1: [secondary]},
            collapsed_keys={COLLAPSE_ALL},
        )
        self.assertEqual(lazy, filtered)

    def test_lazy_build_matches_filter_expanded_level1(self):
        items_input = self._nested_two_level_items()
        filtered = filter_group_display_items(
            items_input,
            expanded_keys={"rulebook::5"},
        )
        primary = _bucket("rulebook::5", "Demo - Addresses")
        secondary_a = _bucket("col:source::ct_1::prod", "prod")
        secondary_b = _bucket("col:source::ct_1::dev", "dev")
        lazy = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={1: [primary], 2: [primary]},
            rule_to_buckets_secondary={1: [secondary_a], 2: [secondary_b]},
            expanded_keys={"rulebook::5"},
        )
        self.assertEqual(
            [(item["kind"], item.get("group_key")) for item in lazy],
            [(item["kind"], item.get("group_key")) for item in filtered],
        )

    def test_lazy_build_matches_filter_expanded_level2(self):
        items_input = self._nested_two_level_items()
        expanded = {"rulebook::5::col:source::ct_1::prod"}
        filtered = filter_group_display_items(items_input, expanded_keys=expanded)
        primary = _bucket("rulebook::5", "Demo - Addresses")
        secondary_a = _bucket("col:source::ct_1::prod", "prod")
        secondary_b = _bucket("col:source::ct_1::dev", "dev")
        lazy = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={1: [primary], 2: [primary]},
            rule_to_buckets_secondary={1: [secondary_a], 2: [secondary_b]},
            expanded_keys=expanded,
        )
        self.assertEqual(
            [(item["kind"], item.get("group_key")) for item in lazy],
            [(item["kind"], item.get("group_key")) for item in filtered],
        )

    def test_lazy_build_omits_rule_rows_when_collapsed(self):
        lazy = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={
                1: [_bucket("col:source::ct_1::prod", "prod")],
                2: [_bucket("col:source::ct_1::dev", "dev")],
            },
            collapsed_keys={COLLAPSE_ALL},
        )
        self.assertEqual([item["kind"] for item in lazy], ["group", "group"])
        self.assertEqual(lazy[0]["rule_count"], 1)
        self.assertEqual(lazy[1]["rule_count"], 1)

    def test_ungrouped_last(self):
        bucket = _bucket("col:source::ct_1::prod", "prod")
        items = build_rule_display_items(
            [SimpleNamespace(pk=1), SimpleNamespace(pk=2)],
            rule_to_buckets={1: [bucket], 2: []},
            enabled=True,
        )
        keys = [item["group_key"] for item in items if item["kind"] == "group"]
        self.assertEqual(keys[-1], UNGROUPED_GROUP_KEY)
