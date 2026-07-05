"""Tests for object detail → COT rulebook field filter URLs."""

from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from django.test import SimpleTestCase

from netbox_nsm.security.object_rules import (
    build_cot_rule_name_column_filter_url,
    build_matrix_cell_rules_filter_url,
    build_rulebook_list_quickfilter_url,
    build_rulebook_rules_tab_url,
    build_rulebooks_panel_url,
)


class CotRulesColumnFilterUrlTests(SimpleTestCase):
    def test_cot_name_filter(self):
        url = build_cot_rule_name_column_filter_url("nsm_rb_prod", "deny-all")
        query = parse_qs(urlparse(url).query)
        self.assertIn("/rulebooks/cot/nsm_rb_prod/rules/", url)
        self.assertEqual(query["f_name"][0], "deny-all")


class MatrixCellRulesFilterUrlTests(SimpleTestCase):
    def test_builds_matrix_cell_source_destination_filters_collapsed(self):
        base = "/rulebooks/cot/nsm_rb_demo_zone_matrix/rules/"
        url = build_matrix_cell_rules_filter_url(
            base,
            src_column_key="source_zones",
            dst_column_key="destination_zones",
            src_filter="zone_01",
            dst_filter="zone_06",
        )
        query = parse_qs(urlparse(url).query)
        self.assertEqual(unquote(query["f_source_zones"][0]), "zone_01")
        self.assertEqual(unquote(query["f_destination_zones"][0]), "zone_06")
        self.assertNotIn("filter_q", query)

    def test_builds_matrix_cell_source_destination_filters_expanded(self):
        base = "/rulebooks/cot/nsm_rb_demo_zone_matrix/rules/"
        url = build_matrix_cell_rules_filter_url(
            base,
            src_column_key="source::ct_12",
            dst_column_key="destination::ct_12",
            src_filter="demo-0001",
            dst_filter="demo-0003",
        )
        query = parse_qs(urlparse(url).query)
        self.assertEqual(unquote(query["f_source__ct_12"][0]), "demo-0001")
        self.assertEqual(unquote(query["f_destination__ct_12"][0]), "demo-0003")
        self.assertNotIn("filter_q", query)


class RulebookLinkUrlTests(SimpleTestCase):
    def test_rules_tab_url(self):
        url = build_rulebook_rules_tab_url("nsm_rb_demo_zone_matrix")
        self.assertIn("/rulebooks/cot/nsm_rb_demo_zone_matrix/rules/", url)

    def test_list_quickfilter_url(self):
        url = build_rulebook_list_quickfilter_url("Rulebook RB Demo Zone Matrix")
        self.assertIn("/rulebooks/", url)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(
            query["q"][0],
            "Rulebook RB Demo Zone Matrix",
        )


class RulebooksPanelUrlTests(SimpleTestCase):
    def test_single_rulebook_links_to_rules_tab(self):
        rb = SimpleNamespace(
            pk=3,
            get_absolute_url=lambda: "/rulebooks/cot/nsm_rb_prod/",
            get_rules_tab_url=lambda: "/rulebooks/cot/nsm_rb_prod/rules/",
        )
        url = build_rulebooks_panel_url([{"rulebook": rb}])
        self.assertEqual(url, "/rulebooks/cot/nsm_rb_prod/rules/")

    def test_multiple_rulebooks_links_to_list(self):
        rb_a = SimpleNamespace(pk=1, get_absolute_url=lambda: "/rulebooks/cot/a/")
        rb_b = SimpleNamespace(pk=2, get_absolute_url=lambda: "/rulebooks/cot/b/")
        url = build_rulebooks_panel_url([{"rulebook": rb_a}, {"rulebook": rb_b}])
        self.assertIn("/rulebooks", url)
