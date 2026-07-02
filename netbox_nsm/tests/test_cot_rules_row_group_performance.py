"""Row-group tab loading: DB aggregation, reduced prefetch, cache."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from netbox_nsm.rulebooks.rules_row_grouping import (
    build_system_row_group_tab_summaries_from_queryset,
    cached_row_group_tab_summaries,
    filter_queryset_by_system_group_key,
    row_group_tab_summaries_cache_key,
    system_group_db_field,
    system_group_key_from_db_value,
)
from netbox_nsm.rulebooks.rules_tab import _cot_rules_row_group_page


class SystemGroupDbHelpersTests(SimpleTestCase):
    def test_system_group_db_field_name(self):
        column = {"kind": "system", "slug": "name", "col_id": "name"}
        self.assertEqual(system_group_db_field(column), "name")

    def test_system_group_db_field_object_returns_none(self):
        column = {"kind": "object", "col_id": "zones::ct_1"}
        self.assertIsNone(system_group_db_field(column))

    def test_system_group_key_from_db_value_empty_name(self):
        self.assertEqual(
            system_group_key_from_db_value("name", ""),
            "(empty)",
        )


class SystemGroupTabSummariesQuerysetTests(SimpleTestCase):
    def test_build_summaries_from_queryset_values(self):
        column = {"kind": "system", "slug": "name", "col_id": "name"}
        qs = MagicMock()
        qs.values.return_value.annotate.return_value = [
            {"name": "alpha", "rule_count": 2},
            {"name": "beta", "rule_count": 1},
        ]
        summaries = build_system_row_group_tab_summaries_from_queryset(
            qs,
            column,
            sort_field="index",
            sort_order="asc",
        )
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0]["group_label"], "alpha")
        self.assertEqual(summaries[0]["rule_count"], 2)
        qs.values.assert_called_once_with("name")


class RowGroupTabSummariesCacheTests(SimpleTestCase):
    @patch("netbox_nsm.rulebooks.rules_row_grouping.cache")
    def test_cached_row_group_tab_summaries_hits_cache(self, mock_cache):
        mock_cache.get.return_value = [{"group_id": "a"}]
        result = cached_row_group_tab_summaries("key", lambda: [{"group_id": "b"}])
        self.assertEqual(result, [{"group_id": "a"}])
        mock_cache.set.assert_not_called()

    @patch("netbox_nsm.rulebooks.rules_row_grouping.cache")
    def test_cached_row_group_tab_summaries_builds_on_miss(self, mock_cache):
        mock_cache.get.return_value = None
        built = [{"group_id": "built"}]
        result = cached_row_group_tab_summaries("key", lambda: built)
        self.assertIs(result, built)
        mock_cache.set.assert_called_once()

    def test_cache_key_includes_filter_model(self):
        key_a = row_group_tab_summaries_cache_key(
            "rb", "name", {"name": {"filter": "a"}}, "index", "asc"
        )
        key_b = row_group_tab_summaries_cache_key(
            "rb", "name", {"name": {"filter": "b"}}, "index", "asc"
        )
        self.assertNotEqual(key_a, key_b)


class CotRulesRowGroupPageTests(SimpleTestCase):
    def _layout(self):
        return {
            "grouped_columns": [
                {
                    "key": "source_zones::ct_1",
                    "area_slug": "source_zones",
                }
            ],
            "rules_layout": [],
            "header_groups": [],
        }

    def _name_group_column(self):
        return {"kind": "system", "slug": "name", "col_id": "name", "label": "Name"}

    @patch("netbox_nsm.rulebooks.rules_tab.context._cot_load_display_rows")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_system_row_group_tab_summaries_from_queryset")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cached_row_group_tab_summaries")
    @patch("netbox_nsm.rulebooks.rules_tab.context.filter_queryset_by_system_group_key")
    @patch("netbox_nsm.rulebooks.rules_tab.context.apply_cot_system_field_filters")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cot_rule_instances_queryset")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cot_multiobject_prefetch_plan")
    def test_system_group_uses_db_path_without_full_scan(
        self,
        mock_prefetch_plan,
        mock_qs_fn,
        mock_apply_filters,
        mock_filter_group,
        mock_cached_summaries,
        mock_db_summaries,
        mock_load_display,
    ):
        layout = self._layout()
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(), slug="nsm_rb_demo_zone_matrix")
        mock_prefetch_plan.return_value = ["source_zones"]

        base_qs = MagicMock()
        filtered_qs = MagicMock()
        mock_qs_fn.return_value = base_qs
        mock_apply_filters.return_value = filtered_qs
        filtered_qs.count.return_value = 62000
        mock_cached_summaries.side_effect = lambda _key, builder: builder()
        mock_db_summaries.return_value = [
            {
                "group_key": "rule-a",
                "group_label": "rule-a",
                "group_id": "rule-a",
                "rule_count": 62000,
            }
        ]
        ordered_all_qs = MagicMock()
        filtered_qs.order_by.return_value = ordered_all_qs

        page_instance = SimpleNamespace(pk=42)
        paginator = MagicMock()
        page_obj = MagicMock()
        page_obj.object_list = [page_instance]
        paginator.get_page.return_value = page_obj
        paginator.num_pages = 1

        with patch(
            "netbox_nsm.rulebooks.rules_tab.context.EnhancedPaginator",
            return_value=paginator,
        ) as mock_paginator_cls:
            request = RequestFactory().get("/rules/")
            (
                tabs,
                tab_active,
                total,
                rows,
                paginator_out,
                page_out,
            ) = _cot_rules_row_group_page(
                request,
                virtual_rb,
                layout=layout,
                row_group_column=self._name_group_column(),
                filter_model={},
                sort_field="index",
                sort_order="asc",
                page_num=1,
                per_page=50,
            )

        mock_db_summaries.assert_called_once_with(
            filtered_qs,
            self._name_group_column(),
            sort_field="index",
            sort_order="asc",
        )
        mock_filter_group.assert_not_called()
        mock_paginator_cls.assert_called_once_with(ordered_all_qs, 50)
        mock_load_display.assert_called_once_with(
            [page_instance], virtual_rb, layout=layout, m2m_prefetch=["source_zones"]
        )
        self.assertEqual(total, 62000)
        self.assertEqual(len(tabs), 2)
        self.assertEqual(tabs[0]["group_id"], "all")
        self.assertEqual(tabs[0]["rule_count"], 62000)
        self.assertEqual(tab_active, "all")
        self.assertEqual(rows, mock_load_display.return_value)
        self.assertIs(paginator_out, paginator)
        self.assertIs(page_out, page_obj)

    @patch("netbox_nsm.rulebooks.rules_tab.context._cot_load_display_rows")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_cot_grouped_rules_table_data")
    @patch("netbox_nsm.rulebooks.rules_tab.context.prefetch_cot_multiobject_fields")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cached_row_group_tab_summaries")
    @patch("netbox_nsm.rulebooks.rules_tab.context.apply_cot_system_field_filters")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cot_rule_instances_queryset")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cot_multiobject_prefetch_plan")
    def test_object_group_loads_only_group_field_for_summaries(
        self,
        mock_prefetch_plan,
        mock_qs_fn,
        mock_apply_filters,
        mock_cached_summaries,
        mock_m2m_prefetch,
        mock_build_rows,
        mock_load_display,
    ):
        layout = self._layout()
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(), slug="nsm_rb_demo_zone_matrix")
        mock_prefetch_plan.return_value = ["source_zones"]
        group_column = {
            "kind": "object",
            "col_id": "source_zones::ct_1",
            "key": "source_zones::ct_1",
            "area_slug": "source_zones",
        }

        filtered_qs = MagicMock()
        mock_qs_fn.return_value = MagicMock()
        mock_apply_filters.return_value = filtered_qs
        filtered_qs.count.return_value = 3
        filtered_qs.order_by.return_value = [SimpleNamespace(pk=1)]
        filtered_qs.filter.return_value = filtered_qs

        mock_build_rows.return_value = {
            "rows": [
                {
                    "pk": 1,
                    "cells_items": {
                        "source_zones::ct_1": [{"name": "trust"}],
                    },
                    "cells_filter": {"source_zones::ct_1": "trust"},
                }
            ]
        }
        mock_cached_summaries.side_effect = lambda _key, builder: builder()

        page_instance = SimpleNamespace(pk=1)
        paginator = MagicMock()
        page_obj = MagicMock()
        page_obj.object_list = [page_instance]
        paginator.get_page.return_value = page_obj
        paginator.num_pages = 1
        filtered_qs.order_by.return_value = filtered_qs

        with patch(
            "netbox_nsm.rulebooks.rules_tab.context.EnhancedPaginator",
            return_value=paginator,
        ):
            with patch(
                "netbox_nsm.rulebooks.rules_tab.context.build_row_group_tab_summaries",
                return_value=[
                    {
                        "group_key": "trust",
                        "group_label": "trust",
                        "group_id": "trust",
                        "rule_count": 1,
                    }
                ],
            ):
                request = RequestFactory().get("/rules/")
                _cot_rules_row_group_page(
                    request,
                    virtual_rb,
                    layout=layout,
                    row_group_column=group_column,
                    filter_model={},
                    sort_field="index",
                    sort_order="asc",
                    page_num=1,
                    per_page=50,
                )

        mock_m2m_prefetch.assert_called_with(
            [SimpleNamespace(pk=1)], virtual_rb, ["source_zones"]
        )
        mock_build_rows.assert_called_with(
            [SimpleNamespace(pk=1)],
            virtual_rb,
            layout=layout,
            object_field_names={"source_zones"},
            include_links=False,
        )
        mock_load_display.assert_called_once_with(
            [page_instance], virtual_rb, layout=layout, m2m_prefetch=["source_zones"]
        )
