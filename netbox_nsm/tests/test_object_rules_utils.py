"""Tests for object detail → rulebook field filter URLs."""

from types import SimpleNamespace
from urllib.parse import parse_qs, unquote, urlparse

from django.test import SimpleTestCase

from netbox_nsm.object_rules_utils import (
    build_matrix_cell_rules_filter_url,
    build_object_field_column_filter_url,
    build_object_field_rules_filter_url,
    build_rule_name_column_filter_url,
    build_rulebooks_panel_url,
    build_rules_column_filter_url,
)


class RulesColumnFilterUrlTests(SimpleTestCase):
    def test_builds_f_param_from_column_key(self):
        rulebook = SimpleNamespace(pk=5)
        url = build_rules_column_filter_url(rulebook, "source::ct_99", "bench-ip-1")
        self.assertIn("/rulebooks/5/rules/", url)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(unquote(query["f_source__ct_99"][0]), "bench-ip-1")

    def test_builds_name_column_filter(self):
        rulebook = SimpleNamespace(pk=2)
        rule = SimpleNamespace(name="allow-web")
        url = build_rule_name_column_filter_url(rulebook, rule)
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["f_name"][0], "allow-web")

    def test_builds_matrix_cell_source_destination_filters(self):
        base = "/rulebooks/7/rules/"
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


class RulebooksPanelUrlTests(SimpleTestCase):
    def test_single_rulebook_links_to_detail(self):
        rb = SimpleNamespace(
            pk=3,
            get_absolute_url=lambda: "/rulebooks/3/",
        )
        url = build_rulebooks_panel_url([{"rulebook": rb}])
        self.assertEqual(url, "/rulebooks/3/")

    def test_multiple_rulebooks_links_to_list(self):
        rb_a = SimpleNamespace(pk=1, get_absolute_url=lambda: "/rulebooks/1/")
        rb_b = SimpleNamespace(pk=2, get_absolute_url=lambda: "/rulebooks/2/")
        url = build_rulebooks_panel_url(
            [{"rulebook": rb_a}, {"rulebook": rb_b}]
        )
        self.assertIn("/rulebooks", url)


class ObjectFieldRulesFilterUrlTests(SimpleTestCase):
    def test_builds_object_type_column_filter(self):
        rulebook = SimpleNamespace(pk=5)
        field = SimpleNamespace(
            pk=1,
            slug="destination",
            name="Destination",
            type_configs=SimpleNamespace(
                all=lambda: [
                    SimpleNamespace(
                        type_config=SimpleNamespace(
                            name="Zones",
                            content_type_id=99,
                        )
                    )
                ]
            ),
        )
        obj = SimpleNamespace(name="trust")
        ct = SimpleNamespace(pk=99)

        url = build_object_field_column_filter_url(
            rulebook,
            field,
            obj,
            ct,
            display_template_map={99: "{name}"},
        )
        query = parse_qs(urlparse(url).query)
        self.assertIn("/rulebooks/5/rules/", url)
        self.assertEqual(unquote(query["f_destination__ct_99"][0]), "trust")

    def test_alias_matches_column_filter(self):
        rulebook = SimpleNamespace(pk=3)
        field = SimpleNamespace(pk=2, slug="service", name="Service")
        obj = SimpleNamespace(name="HTTPS")
        ct = SimpleNamespace(pk=42)

        url = build_object_field_rules_filter_url(
            rulebook,
            field,
            obj,
            ct,
            display_template_map={42: "{name}"},
        )
        query = parse_qs(urlparse(url).query)
        self.assertEqual(unquote(query["f_service__ct_42"][0]), "HTTPS")
