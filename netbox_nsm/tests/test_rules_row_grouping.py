"""Tests for Grouped Rows in the rules table."""

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebooks.rules_tab_base import (
    _build_rules_cell_html,
    format_rules_tab_badge,
)
from netbox_nsm.rulebooks.rules_row_grouping import (
    RULE_GROUP_COLUMN_ID,
    RULES_ROW_GROUP_TAB_QUERY_PARAM,
    build_group_key,
    build_row_group_column_choices,
    build_row_group_tab_summaries,
    build_row_grouped_display_rows,
    build_system_row_group_tab_summaries_from_queryset,
    filter_queryset_by_system_group_key,
    filter_rows_by_group_key,
    is_row_groupable_column,
    paginate_grouped_rule_rows,
    prepare_row_grouping_columns,
    prepare_row_grouping_tab_columns,
    resolve_row_group_tab,
    resolve_stored_row_group_column_id,
    row_group_column_display_label,
    row_group_sort_applies_to_groups,
)


class RulesRowGroupingTests(SimpleTestCase):
    def _zone_column(
        self,
        *,
        field_group="Source",
        group_header="Source",
        col_id="source_zones::ct_1",
    ):
        return {
            "kind": "object",
            "col_id": col_id,
            "key": col_id,
            "area_slug": col_id.split("::", 1)[0],
            "label": "Zones (Source)",
            "field_group": field_group,
            "group_header": group_header,
            "header_subtitle": "Zone",
            "header_title": "Zones (Source)",
        }

    def test_build_group_key_joins_multiple_values_with_comma(self):
        row = {
            "cells_items": {
                "source_zones::ct_1": [
                    {"name": "trust"},
                    {"name": "zone_097"},
                ]
            }
        }
        self.assertEqual(
            build_group_key(row, self._zone_column()),
            "trust, zone_097",
        )

    def test_build_group_key_composite_object_values(self):
        row = {
            "cells_items": {
                "source_zones::ct_1": [
                    {"name": "untrust"},
                    {"name": "dmz"},
                ]
            }
        }
        self.assertEqual(
            build_group_key(row, self._zone_column()),
            "dmz, untrust",
        )

    def test_build_group_key_empty_object_values(self):
        row = {"cells_items": {"source_zones::ct_1": []}}
        self.assertEqual(build_group_key(row, self._zone_column()), "(empty)")

    def test_build_group_key_system_name(self):
        row = {"system": {"name": "rule-1"}, "name": "rule-1"}
        column = {"kind": "system", "slug": "name", "col_id": "name"}
        self.assertEqual(build_group_key(row, column), "rule-1")

    def test_resolve_stored_row_group_column_id_rejects_actions(self):
        flat_columns = [self._zone_column(), {"kind": "actions", "col_id": "_actions"}]
        self.assertIsNone(
            resolve_stored_row_group_column_id("_actions", flat_columns)
        )

    def test_prepare_row_grouping_tab_columns_accepts_expanded_group_column(self):
        collapsed_flat = [
            {
                "kind": "object",
                "col_id": "source_zones",
                "key": "source_zones",
                "area_slug": "source_zones",
                "merged_keys": ["source_zones::ct_1"],
            }
        ]
        _, _, group_col = prepare_row_grouping_tab_columns(
            collapsed_flat,
            [],
            "source_zones::ct_1",
            group_column=self._zone_column(),
        )
        self.assertEqual(group_col["col_id"], "source_zones::ct_1")

    def test_prepare_row_grouping_tab_columns_keeps_grouped_column_visible(self):
        flat_columns = [
            self._zone_column(),
            {"kind": "system", "slug": "index", "col_id": "index", "label": "Index"},
            {"kind": "system", "slug": "name", "col_id": "name", "label": "Name"},
            {"kind": "actions", "col_id": "_actions"},
        ]
        column_defs = [
            {
                "headerName": "Zones",
                "children": [{"field": "source_zones::ct_1", "headerName": "Zone"}],
            },
            {"colId": "index", "headerName": "Index"},
            {"colId": "name", "headerName": "Name"},
            {"colId": "_actions"},
        ]
        visible_flat, visible_defs, group_col = prepare_row_grouping_tab_columns(
            flat_columns,
            column_defs,
            "source_zones::ct_1",
        )
        self.assertNotIn(RULE_GROUP_COLUMN_ID, [c.get("col_id") for c in visible_flat])
        self.assertEqual(visible_flat[0]["col_id"], "source_zones::ct_1")
        self.assertEqual(group_col["col_id"], "source_zones::ct_1")
        col_ids = [c.get("colId") for c in visible_defs]
        self.assertNotIn(RULE_GROUP_COLUMN_ID, col_ids)
        child_fields = [
            child.get("field")
            for col in visible_defs
            if col.get("children")
            for child in col["children"]
        ]
        self.assertIn("source_zones::ct_1", child_fields)

    def test_build_row_group_tab_summaries_counts_and_sorts(self):
        rows = [
            {
                "pk": 1,
                "cells_items": {"source_zones::ct_1": [{"name": "zone_b"}]},
            },
            {
                "pk": 2,
                "cells_items": {"source_zones::ct_1": [{"name": "zone_a"}]},
            },
            {
                "pk": 3,
                "cells_items": {"source_zones::ct_1": [{"name": "zone_a"}]},
            },
        ]
        summaries = build_row_group_tab_summaries(
            rows,
            self._zone_column(),
            sort_field="index",
            sort_order="asc",
        )
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["group_label"], "zone_a")
        self.assertEqual(summaries[0]["group_id"], "zone-a")
        self.assertEqual(summaries[0]["rule_count"], 2)
        self.assertEqual(summaries[1]["group_label"], "zone_b")
        self.assertEqual(summaries[1]["rule_count"], 1)

    def test_resolve_row_group_tab_defaults_to_first(self):
        summaries = [
            {"group_key": "a", "group_id": "a", "group_label": "A", "rule_count": 1},
            {"group_key": "b", "group_id": "b", "group_label": "B", "rule_count": 2},
        ]
        request = RequestFactory().get("/rules/")
        key, group_id = resolve_row_group_tab(request, summaries)
        self.assertEqual(key, "a")
        self.assertEqual(group_id, "a")

    def test_resolve_row_group_tab_by_query_param(self):
        summaries = [
            {"group_key": "a", "group_id": "a", "group_label": "A", "rule_count": 1},
            {"group_key": "b", "group_id": "b", "group_label": "B", "rule_count": 2},
        ]
        request = RequestFactory().get(
            "/rules/",
            {RULES_ROW_GROUP_TAB_QUERY_PARAM: "b"},
        )
        key, group_id = resolve_row_group_tab(request, summaries)
        self.assertEqual(key, "b")
        self.assertEqual(group_id, "b")

    def test_filter_rows_by_group_key(self):
        rows = [
            {"pk": 1, "cells_items": {"source_zones::ct_1": [{"name": "dmz"}]}},
            {"pk": 2, "cells_items": {"source_zones::ct_1": [{"name": "trust"}]}},
        ]
        filtered = filter_rows_by_group_key(rows, self._zone_column(), "dmz")
        self.assertEqual([row["pk"] for row in filtered], [1])

    def test_tab_mode_badge_uses_total_filtered_count(self):
        """Filter badge x/y counts all filtered rules, not just active tab."""
        filtered_total = 62500
        unfiltered_total = 62500
        badge = format_rules_tab_badge(
            filtered_total,
            unfiltered_total,
            filter_active=True,
        )
        self.assertEqual(badge, "62500/62500")

    def test_prepare_row_grouping_columns_hides_grouped_column(self):
        flat_columns = [
            self._zone_column(),
            {"kind": "system", "slug": "index", "col_id": "index", "label": "Index"},
            {"kind": "system", "slug": "name", "col_id": "name", "label": "Name"},
            {"kind": "actions", "col_id": "_actions"},
        ]
        column_defs = [
            {
                "headerName": "Zones",
                "children": [{"field": "source_zones::ct_1", "headerName": "Zone"}],
            },
            {"colId": "index", "headerName": "Index"},
            {"colId": "name", "headerName": "Name"},
            {"colId": "_actions"},
        ]
        visible_flat, visible_defs, group_col = prepare_row_grouping_columns(
            flat_columns,
            column_defs,
            "source_zones::ct_1",
        )
        self.assertEqual(visible_flat[0]["col_id"], RULE_GROUP_COLUMN_ID)
        self.assertEqual(visible_flat[1]["col_id"], "index")
        self.assertEqual(
            [col.get("col_id") for col in visible_flat],
            [RULE_GROUP_COLUMN_ID, "index", "name", "_actions"],
        )
        self.assertEqual(visible_defs[0]["colId"], RULE_GROUP_COLUMN_ID)
        self.assertEqual(visible_defs[1]["colId"], "index")
        self.assertEqual(visible_defs[0]["headerName"], "Rule-Group")
        self.assertEqual(group_col["col_id"], "source_zones::ct_1")
        child_fields = [
            child.get("field")
            for col in visible_defs
            if col.get("children")
            for child in col["children"]
        ]
        self.assertNotIn("source_zones::ct_1", child_fields)

    def test_build_row_grouped_display_rows_structure(self):
        rows = [
            {
                "pk": 1,
                "index": 1,
                "name": "r1",
                "enabled": True,
                "cells_items": {"source_zones::ct_1": [{"name": "dmz"}]},
            },
            {
                "pk": 2,
                "index": 2,
                "name": "r2",
                "enabled": True,
                "cells_items": {
                    "source_zones::ct_1": [{"name": "dmz"}, {"name": "untrust"}]
                },
            },
        ]
        grouped = build_row_grouped_display_rows(
            rows,
            self._zone_column(),
            sort_field="index",
            sort_order="asc",
        )
        kinds = [row.get("kind") for row in grouped]
        self.assertEqual(kinds, ["group", "rule", "group", "rule"])
        self.assertEqual(grouped[0]["group_label"], "dmz")
        self.assertEqual(grouped[2]["group_label"], "dmz, untrust")
        self.assertEqual(grouped[1]["parent_group_label"], "dmz")
        self.assertEqual(grouped[3]["parent_group_label"], "dmz, untrust")

    def test_paginate_grouped_rule_rows_includes_children_for_page_groups(self):
        grouped = [
            {"kind": "group", "group_id": "a", "group_label": "A", "rule_count": 1},
            {"kind": "rule", "parent_group_id": "a", "pk": 1},
            {"kind": "group", "group_id": "b", "group_label": "B", "rule_count": 1},
            {"kind": "rule", "parent_group_id": "b", "pk": 2},
        ]
        page_rows, paginator, page_obj = paginate_grouped_rule_rows(
            grouped,
            per_page=25,
            page_num=1,
        )
        self.assertEqual(paginator.count, 2)
        self.assertEqual(page_rows[0]["kind"], "group")
        self.assertEqual(page_rows[1]["kind"], "rule")
        self.assertEqual(page_rows[2]["kind"], "group")
        self.assertEqual(page_rows[3]["kind"], "rule")
        self.assertEqual(len(page_obj.object_list), 2)

    def test_row_group_sort_applies_to_groups_for_name(self):
        column = {"kind": "system", "slug": "name", "col_id": "name"}
        self.assertTrue(row_group_sort_applies_to_groups("name", column))

    def test_build_system_row_group_tab_summaries_from_queryset(self):
        column = {"kind": "system", "slug": "index", "col_id": "index"}
        rows = [
            {"index": 1, "system": {"index": 1}},
            {"index": 1, "system": {"index": 1}},
            {"index": 2, "system": {"index": 2}},
        ]
        python_summaries = build_row_group_tab_summaries(
            rows, column, sort_field="index", sort_order="asc"
        )

        class FakeQS:
            def values(self, field):
                self._field = field
                return self

            def annotate(self, **_kwargs):
                buckets = {}
                for row in rows:
                    key = row[self._field]
                    buckets[key] = buckets.get(key, 0) + 1
                return [
                    {self._field: key, "rule_count": count}
                    for key, count in buckets.items()
                ]

        db_summaries = build_system_row_group_tab_summaries_from_queryset(
            FakeQS(), column, sort_field="index", sort_order="asc"
        )
        self.assertEqual(
            [(s["group_label"], s["rule_count"]) for s in python_summaries],
            [(s["group_label"], s["rule_count"]) for s in db_summaries],
        )

    def test_filter_queryset_by_system_group_key_name(self):
        column = {"kind": "system", "slug": "name", "col_id": "name"}

        class FakeQS:
            def __init__(self):
                self.filters = []

            def filter(self, **kwargs):
                clone = FakeQS()
                clone.filters = [*self.filters, kwargs]
                return clone

        qs = FakeQS()
        filtered = filter_queryset_by_system_group_key(qs, column, "rule-1")
        self.assertEqual(filtered.filters, [{"name": "rule-1"}])

    def test_is_row_groupable_column(self):
        self.assertTrue(is_row_groupable_column({"kind": "object", "col_id": "x"}))
        self.assertFalse(is_row_groupable_column({"kind": "actions", "col_id": "_actions"}))

    def test_rule_group_child_cell_shows_muted_group_hint(self):
        html = _build_rules_cell_html(
            {"kind": "rule_group", "col_id": "_rule_group"},
            {"parent_group_label": "zone_001"},
            request=RequestFactory().get("/"),
            can_change=False,
            can_delete=False,
            object_fields_by_slug={},
        )
        self.assertIn('nsm-cell-empty">-', html)
        self.assertIn('nsm-rule-group-hint text-muted', html)
        self.assertIn("Group:", html)
        self.assertIn("zone_001", html)

    def test_resolve_stored_row_group_column_id_requires_expanded_leaf_ids(self):
        stored = "source::ct_281"
        collapsed_flat = [
            {
                "kind": "object",
                "col_id": "source",
                "key": "source",
                "area_slug": "source",
            }
        ]
        expanded_flat = [
            {
                "kind": "object",
                "col_id": "source::ct_281",
                "key": "source::ct_281",
                "area_slug": "source",
            }
        ]
        self.assertIsNone(
            resolve_stored_row_group_column_id(stored, collapsed_flat)
        )
        self.assertEqual(
            resolve_stored_row_group_column_id(stored, expanded_flat),
            "source::ct_281",
        )

    def test_resolve_stored_row_group_column_id(self):
        flat_columns = [
            self._zone_column(),
            {"kind": "actions", "col_id": "_actions"},
        ]
        self.assertEqual(
            resolve_stored_row_group_column_id(
                "source_zones::ct_1", flat_columns
            ),
            "source_zones::ct_1",
        )
        self.assertIsNone(resolve_stored_row_group_column_id("missing", flat_columns))

    def test_build_row_group_column_choices_uses_group_and_type_label(self):
        flat_columns = [
            self._zone_column(),
            self._zone_column(
                field_group="Destination",
                col_id="destination_zones::ct_2",
            ),
            {"kind": "system", "slug": "name", "col_id": "name", "label": "Name"},
            {"kind": "actions", "col_id": "_actions"},
        ]
        choices = build_row_group_column_choices(flat_columns)
        self.assertEqual(choices[0], ("", "— none —"))
        self.assertEqual(
            choices[1],
            ("source_zones::ct_1", "Source - Zone"),
        )
        self.assertEqual(
            choices[2],
            ("destination_zones::ct_2", "Destination - Zone"),
        )
        self.assertEqual(choices[3], ("name", "Name"))

    def test_row_group_column_display_label_uses_group_header_without_field_group(self):
        col = {
            "kind": "object",
            "col_id": "source::ct_281",
            "field_group": "",
            "group_header": "Source",
            "header_title": "Source",
            "header_subtitle": "Zone",
        }
        self.assertEqual(row_group_column_display_label(col), "Source - Zone")
