"""All-rules grid: union column layout across policy rulebooks."""

import json

from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import RequestFactory, override_settings
from django.urls import reverse

import netbox_nsm.views.rulebook as rulebook_views
from netbox_nsm.all_rules_grid_service import (
    _remap_grouped_row,
    _union_global_column_key,
    build_all_rules_filter_maps,
    build_all_rules_grid_config,
    build_all_rules_grid_scaffold,
    fetch_all_rules_grid_page,
)
from netbox_nsm.models import (
    Rule,
    Rulebook,
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase
from netbox_nsm.views.all_rules_grid_api import AllRulesGridApiView

_UNION_GRID_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "netbox_nsm_all_rules_grid_union_tests",
    }
}


def _leaf_column_defs(column_defs):
    for col in column_defs or []:
        children = col.get("children")
        if children:
            yield from _leaf_column_defs(children)
        elif col.get("colId"):
            yield col


def _object_col_ids(scaffold: dict) -> list[str]:
    ids: list[str] = []
    for col in scaffold.get("columnDefs") or []:
        for child in col.get("children") or []:
            col_id = child.get("colId")
            if col_id:
                ids.append(col_id)
    return ids


def _top_level_col_ids(scaffold: dict) -> list[str]:
    return [
        col.get("colId") for col in scaffold.get("columnDefs") or [] if col.get("colId")
    ]


def _column_def_order(scaffold: dict) -> list[str]:
    order: list[str] = []
    for col in scaffold.get("columnDefs") or []:
        if col.get("colId"):
            order.append(col["colId"])
        elif col.get("children"):
            order.append(f"group:{col.get('headerName') or ''}")
    return order


@override_settings(CACHES=_UNION_GRID_CACHES)
class AllRulesGridUnionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ct_a = ContentType.objects.order_by("pk").first()
        cls.ct_b = ContentType.objects.exclude(pk=cls.ct_a.pk).order_by("pk").first()
        cls.tc_a, _ = TypeConfig.objects.get_or_create(
            content_type=cls.ct_a,
            defaults={"name": "Union Type A"},
        )
        cls.tc_b, _ = TypeConfig.objects.get_or_create(
            content_type=cls.ct_b,
            defaults={"name": "Union Type B"},
        )

        cls.rb_a = Rulebook.objects.create(
            name="Union RB A", rulebook_type="security_rules"
        )
        cls.rb_b = Rulebook.objects.create(
            name="Union RB B", rulebook_type="security_rules"
        )
        ensure_system_rulebook_fields(cls.rb_a)
        ensure_system_rulebook_fields(cls.rb_b)

        cls.field_src_a = RulebookField.objects.create(
            rulebook=cls.rb_a,
            slug="source",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=10,
        )
        RulebookFieldType.objects.create(
            field=cls.field_src_a, type_config=cls.tc_a, visible=True
        )

        cls.field_dst_b = RulebookField.objects.create(
            rulebook=cls.rb_b,
            slug="destination",
            name="Destination",
            placement="destination",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=10,
        )
        RulebookFieldType.objects.create(
            field=cls.field_dst_b, type_config=cls.tc_b, visible=True
        )

        cls.rule_a = Rule.objects.create(rulebook=cls.rb_a, name="rule-a", index=10)
        cls.rule_b = Rule.objects.create(rulebook=cls.rb_b, name="rule-b", index=20)

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_union_global_column_key_uses_area_and_label(self):
        key = _union_global_column_key(
            "Source",
            {"key": "source::ct_1", "label": "Zones"},
        )
        self.assertEqual(key, "Source::Zones")

    def test_scaffold_includes_columns_from_all_rulebooks(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        object_ids = _object_col_ids(scaffold)
        type_a_label = str(self.ct_a.model_class()._meta.verbose_name).capitalize()
        type_b_label = str(self.ct_b.model_class()._meta.verbose_name).capitalize()
        self.assertIn(f"Source::{type_a_label}", object_ids)
        self.assertIn(f"Destination::{type_b_label}", object_ids)

    def test_rulebook_column_is_first(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        top = _top_level_col_ids(scaffold)
        self.assertEqual(top[0], "rulebook")

    def test_description_column_is_last_before_actions(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        order = _column_def_order(scaffold)
        desc_idx = order.index("description")
        actions_idx = order.index("_actions")
        self.assertLess(desc_idx, actions_idx)
        self.assertEqual(order[actions_idx - 1], "description")
        for group_label in order[desc_idx + 1 : actions_idx]:
            self.fail(f"column after description: {group_label}")

    def test_rulebook_column_is_pinned_locked_and_non_movable(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        rb_col = scaffold["columnDefs"][0]
        self.assertEqual(rb_col["colId"], "rulebook")
        self.assertTrue(rb_col.get("suppressMovable"))
        self.assertEqual(rb_col.get("lockPosition"), "left")

    def test_actions_column_is_pinned_locked_and_non_movable(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        actions_col = next(
            c for c in scaffold["columnDefs"] if c.get("colId") == "_actions"
        )
        self.assertEqual(actions_col.get("pinned"), "right")
        self.assertEqual(actions_col.get("lockPosition"), "right")
        self.assertTrue(actions_col.get("suppressMovable"))

    def test_all_leaf_columns_suppress_movable(self):
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        for col in _leaf_column_defs(scaffold["columnDefs"]):
            self.assertTrue(
                col.get("suppressMovable"),
                msg=f"column {col.get('colId')} must be non-movable",
            )

    def test_filter_maps_include_union_object_columns(self):
        column_map, _layout = build_all_rules_filter_maps(rulebook_views)
        type_a_label = str(self.ct_a.model_class()._meta.verbose_name).capitalize()
        global_key = f"Source::{type_a_label}"
        self.assertIn(global_key, column_map)
        self.assertIn("Source.", column_map[global_key])

    def test_dedupes_same_area_and_header_across_rulebooks(self):
        field_src_b = RulebookField.objects.create(
            rulebook=self.rb_b,
            slug="src",
            name="Source",
            placement="source",
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
            sort_order=5,
        )
        RulebookFieldType.objects.create(
            field=field_src_b, type_config=self.tc_a, visible=True
        )
        scaffold = build_all_rules_grid_scaffold(rulebook_views)
        type_a_label = str(self.ct_a.model_class()._meta.verbose_name).capitalize()
        global_key = f"Source::{type_a_label}"
        self.assertEqual(_object_col_ids(scaffold).count(global_key), 1)

    def test_grid_config_enables_progressive_load(self):
        request = RequestFactory().get("/plugins/netbox-nsm/rulebooks/0/rules/")
        request.user = self.user
        cfg = build_all_rules_grid_config(request, read_only=True)
        self.assertTrue(cfg.get("infiniteRowModel"))
        self.assertTrue(cfg.get("readOnly"))
        self.assertIn("gridLoadSteps", cfg)
        self.assertGreater(len(cfg["gridLoadSteps"]), 1)
        self.assertIn("loadRowLimit", cfg)
        self.assertIn("initialLoadLimit", cfg)
        self.assertIn("loadMoreStep", cfg)
        self.assertFalse(cfg["permissions"]["change"])
        self.assertFalse(cfg["permissions"]["delete"])

    def test_grid_config_group_by_options_include_rulebook_and_columns(self):
        request = RequestFactory().get("/plugins/netbox-nsm/rulebooks/0/rules/")
        request.user = self.user
        cfg = build_all_rules_grid_config(request, read_only=True)
        values = {opt["value"] for opt in cfg.get("groupByOptions") or []}
        self.assertIn("rulebook", values)
        type_a_label = str(self.ct_a.model_class()._meta.verbose_name).capitalize()
        self.assertIn(f"col:Source::{type_a_label}", values)
        self.assertIn("groupByNotAllowedMessage", cfg)
        self.assertNotIn("name", values)
        self.assertNotIn("index", values)

    def test_remap_grouped_row_maps_local_to_global_keys(self):
        type_a_label = str(self.ct_a.model_class()._meta.verbose_name).capitalize()
        local_key = f"source::ct_{self.ct_a.pk}"
        global_key = f"Source::{type_a_label}"
        remapped = _remap_grouped_row(
            {
                "cells_items": {local_key: [{"name": "dmz"}]},
                "cells_filter": {local_key: "dmz"},
            },
            {global_key: local_key},
        )
        self.assertEqual(remapped["cells_items"][global_key][0]["name"], "dmz")
        self.assertEqual(remapped["cells_filter"][global_key], "dmz")

    def test_fetch_page_returns_all_rulebooks(self):
        request = RequestFactory().get("/")
        request.user = self.user
        payload = fetch_all_rules_grid_page(
            request,
            start_row=0,
            end_row=50,
            view_helpers=rulebook_views,
        )
        self.assertEqual(payload["lastRow"], 2)
        names = {row["name"] for row in payload["rowData"]}
        self.assertEqual(names, {"rule-a", "rule-b"})
        rulebooks = {row["rulebook"] for row in payload["rowData"]}
        self.assertEqual(rulebooks, {"Union RB A", "Union RB B"})

    def test_meta_api_returns_union_scaffold(self):
        self.add_permissions("netbox_nsm.view_rule")
        url = reverse("plugins:netbox_nsm:all_rules_grid_api") + "?meta=1"
        request = RequestFactory().get(url)
        request.user = self.user
        response = AllRulesGridApiView.as_view()(request)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(_object_col_ids(data)), 1)
