"""Rules tab pagination and prefetch for large COT rulebooks."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.rules_layout import (
    build_cot_grouped_rules_table_data,
    cot_db_order_fields,
)
from netbox_nsm.rulebooks.rules_tab import _cot_rules_page


class CotRulesTabOrderFieldsTests(SimpleTestCase):
    def test_default_index_asc(self):
        self.assertEqual(cot_db_order_fields("index", "asc"), ["index", "pk"])

    def test_enabled_desc_uses_status_column(self):
        self.assertEqual(cot_db_order_fields("enabled", "desc"), ["-status", "-pk"])


class CotRulesTabFastPathTests(SimpleTestCase):
    def _layout(self):
        return {
            "grouped_columns": [
                {
                    "key": "source_addresses::ct_1",
                    "area_slug": "source_addresses",
                }
            ],
            "rules_layout": [],
            "header_groups": [],
        }

    @patch("netbox_nsm.rulebooks.rules_tab.prefetch_cot_multiobject_fields")
    @patch("netbox_nsm.rulebooks.rules_tab.cot_multiobject_prefetch_plan")
    @patch("netbox_nsm.rulebooks.rules_tab.build_cot_grouped_rules_table_data")
    @patch("netbox_nsm.rulebooks.rules_tab.cot_rule_instances_queryset")
    def test_unfiltered_system_sort_uses_queryset_pagination(
        self, mock_qs_fn, mock_build_rows, mock_prefetch_plan, mock_m2m_prefetch
    ):
        layout = self._layout()
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(), slug="nsm_rb_demo")
        mock_prefetch_plan.return_value = ["source_addresses", "actions"]

        page_instance = SimpleNamespace(pk=99)
        qs = MagicMock()
        paginator = MagicMock()
        page_obj = MagicMock()
        page_obj.object_list = [page_instance]
        paginator.get_page.return_value = page_obj
        paginator.count = 3250
        paginator.num_pages = 65
        qs.order_by.return_value = qs

        mock_qs_fn.return_value = qs
        mock_build_rows.return_value = {"rows": [{"pk": 99}]}

        with patch(
            "netbox_nsm.rulebooks.rules_tab.EnhancedPaginator",
            return_value=paginator,
        ) as mock_paginator_cls:
            rows, paginator_out, page_out = _cot_rules_page(
                virtual_rb,
                layout=layout,
                filter_model={},
                sort_field="index",
                sort_order="asc",
                page_num=1,
                per_page=50,
            )

        mock_qs_fn.assert_called_once_with(virtual_rb)
        mock_m2m_prefetch.assert_called_once_with(
            [page_instance], virtual_rb, ["source_addresses", "actions"]
        )
        qs.order_by.assert_called_once_with("index", "pk")
        mock_paginator_cls.assert_called_once_with(qs, 50)
        mock_build_rows.assert_called_once_with(
            [page_instance], virtual_rb, layout=layout
        )
        self.assertEqual(rows, [{"pk": 99}])
        self.assertIs(paginator_out, paginator)
        self.assertIs(page_out, page_obj)

    @patch("netbox_nsm.rulebooks.rules_tab.prefetch_cot_multiobject_fields")
    @patch("netbox_nsm.rulebooks.rules_tab.cot_multiobject_prefetch_plan")
    @patch("netbox_nsm.rulebooks.rules_tab.build_cot_grouped_rules_table_data")
    @patch("netbox_nsm.rulebooks.rules_tab.cot_rule_instances_queryset")
    def test_active_filter_loads_all_rows(
        self, mock_qs_fn, mock_build_rows, mock_prefetch_plan, mock_m2m_prefetch
    ):
        layout = self._layout()
        virtual_rb = SimpleNamespace(cot=SimpleNamespace(), slug="nsm_rb_demo")
        mock_prefetch_plan.return_value = ["source_addresses"]
        mock_qs_fn.return_value = [SimpleNamespace(pk=1), SimpleNamespace(pk=2)]
        mock_build_rows.return_value = {
            "rows": [{"pk": 1, "cells_filter": {}}, {"pk": 2, "cells_filter": {}}]
        }

        with patch("netbox_nsm.rulebooks.rules_tab.EnhancedPaginator") as mock_paginator_cls:
            paginator = MagicMock()
            page_obj = MagicMock()
            page_obj.object_list = [{"pk": 1}]
            paginator.get_page.return_value = page_obj
            paginator.num_pages = 1
            mock_paginator_cls.return_value = paginator

            _cot_rules_page(
                virtual_rb,
                layout=layout,
                filter_model={"name": {"filterType": "text", "type": "contains", "filter": "x"}},
                sort_field="index",
                sort_order="asc",
                page_num=1,
                per_page=50,
            )

        mock_qs_fn.assert_called_once()
        mock_build_rows.assert_called_once()
        listed = mock_build_rows.call_args[0][0]
        self.assertEqual(len(listed), 2)


class CotGroupedRulesTableDataTests(SimpleTestCase):
    @patch("netbox_nsm.rulebooks.rules_layout.build_cot_rules_layout")
    def test_reuses_supplied_layout(self, mock_layout):
        layout = {
            "grouped_columns": [],
            "rules_layout": [],
            "header_groups": [],
        }
        virtual_rb = SimpleNamespace(
            cot=SimpleNamespace(fields=SimpleNamespace(filter=lambda **_kw: [])),
            slug="nsm_rb_demo",
        )
        result = build_cot_grouped_rules_table_data([], virtual_rb, layout=layout)
        mock_layout.assert_not_called()
        self.assertIs(result, layout)
        self.assertEqual(result["rows"], [])
