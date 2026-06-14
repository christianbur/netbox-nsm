"""COT rules tab: row grouping interacts with column mode and chrome context."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from utilities.testing import TestCase

from netbox_nsm.rulebooks.forms.cot import CotRulebookDetailForm
from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from netbox_nsm.rulebooks.grid import build_rulebook_rules_grid_column_defs
from netbox_nsm.rulebooks.rules_tab import build_cot_rulebook_rules_tab_context
from netbox_nsm.tests.test_rules_column_mode import _sample_grouped


def _row_group_page_result():
    paginator = MagicMock()
    paginator.count = 0
    page_obj = MagicMock()
    page_obj.object_list = []
    return [], "", 0, [], paginator, page_obj


class CotRulesTabRowGroupContextTests(SimpleTestCase):
    def _request(self, *, col_mode: str = ""):
        path = "/plugins/netbox-nsm/rulebooks/cot/nsm_rb_test/rules/"
        if col_mode:
            path = f"{path}?col_mode={col_mode}"
        request = RequestFactory().get(path)
        request.user = MagicMock()
        request.user.has_perm = MagicMock(return_value=True)
        return request

    def _virtual_rb(self):
        cot = MagicMock()
        cot.slug = "nsm_rb_test"
        return SimpleNamespace(cot=cot, slug=cot.slug, name="Test")

    def _layout_and_defs(self):
        layout = _sample_grouped()
        grouped = {**layout, "rows": []}
        return layout, build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]

    @patch("netbox_nsm.rulebooks.rules_tab.context.get_paginate_count", return_value=50)
    @patch("netbox_nsm.rulebooks.rules_tab.context._cot_rules_row_group_page")
    @patch("netbox_nsm.rulebooks.rules_tab.context._resolve_rules_filter_model")
    @patch("netbox_nsm.rulebooks.rules_tab.context.get_cot_row_group_by_col_id")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_rulebook_rules_grid_column_defs")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_cot_rules_layout")
    def test_row_group_allows_collapsed_column_mode(
        self,
        mock_build_layout,
        mock_build_defs,
        mock_get_row_group_col,
        mock_resolve_filter,
        mock_row_group_page,
        _mock_per_page,
    ):
        layout, column_defs = self._layout_and_defs()
        mock_build_layout.return_value = layout
        mock_build_defs.return_value = {"columnDefs": column_defs}
        mock_get_row_group_col.return_value = "source_addresses::ct_1"
        mock_resolve_filter.return_value = ({}, None, "")
        mock_row_group_page.return_value = _row_group_page_result()

        ctx = build_cot_rulebook_rules_tab_context(
            self._request(col_mode="collapsed"),
            self._virtual_rb(),
        )

        self.assertTrue(ctx["rules_row_group_active"])
        self.assertEqual(ctx["rules_row_group_col_id"], "source_addresses")
        self.assertEqual(ctx["rules_column_mode"], "collapsed")

    @patch("netbox_nsm.rulebooks.rules_tab.context.get_paginate_count", return_value=50)
    @patch("netbox_nsm.rulebooks.rules_tab.context._cot_rules_page")
    @patch("netbox_nsm.rulebooks.rules_tab.context._resolve_rules_filter_model")
    @patch("netbox_nsm.rulebooks.rules_tab.context.cot_rule_instances_queryset")
    @patch("netbox_nsm.rulebooks.rules_tab.context.get_cot_row_group_by_col_id")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_rulebook_rules_grid_column_defs")
    @patch("netbox_nsm.rulebooks.rules_tab.context.build_cot_rules_layout")
    def test_no_row_group_uses_standard_pagination(
        self,
        mock_build_layout,
        mock_build_defs,
        mock_get_row_group_col,
        mock_qs,
        mock_resolve_filter,
        mock_rules_page,
        _mock_per_page,
    ):
        layout, column_defs = self._layout_and_defs()
        mock_build_layout.return_value = layout
        mock_build_defs.return_value = {"columnDefs": column_defs}
        mock_get_row_group_col.return_value = ""
        mock_resolve_filter.return_value = ({}, None, "")
        mock_rules_page.return_value = ([], MagicMock(count=0), MagicMock())

        ctx = build_cot_rulebook_rules_tab_context(
            self._request(),
            self._virtual_rb(),
        )

        self.assertFalse(ctx["rules_row_group_active"])
        mock_rules_page.assert_called_once()


class CotRulebookGroupedRowsFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType

        cls.cot = CustomObjectType.objects.create(
            name="nsm_rb_rowgroup_form",
            slug="nsm_rb_rowgroup_form",
            verbose_name="Row Group Form",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def test_grouped_rows_field_label(self):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        self.assertEqual(str(form.fields["row_group_by_col_id"].label), "Grouped rows")

    def test_grouped_rows_widget_uses_native_select(self):
        form = CotRulebookDetailForm(cot=self.cot, rulebook_slug=self.cot.slug)
        classes = form.fields["row_group_by_col_id"].widget.attrs.get("class", "")
        self.assertIn("no-ts", classes)
