"""Filter query view(matrix) / view(group) directive parsing."""

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.grid_filter import validate_rules_filter_query
from netbox_nsm.rulebooks.grid import (
    VIEW_DIRECTIVE_MULTIPLE_ERROR,
    build_ag_grid_filter_model_from_column_map,
    count_view_directives,
    format_filter_query_with_view,
    normalize_filter_query_view,
    parse_view_directive,
    validate_view_directive_count,
)


class FilterViewDirectiveTests(SimpleTestCase):
    def test_default_no_view(self):
        view, body, err = parse_view_directive("Name(server)")
        self.assertIsNone(err)
        self.assertIsNone(view)
        self.assertEqual(body, "Name(server)")

    def test_view_group_stripped(self):
        view, body, err = parse_view_directive("Name(server) AND view(group)")
        self.assertIsNone(err)
        self.assertEqual(view, "group")
        self.assertEqual(body, "Name(server)")

    def test_view_matrix_stripped(self):
        view, body, err = parse_view_directive("view(matrix) AND Name(server)")
        self.assertIsNone(err)
        self.assertEqual(view, "matrix")
        self.assertEqual(body, "Name(server)")

    def test_view_matrix_only(self):
        view, body, err = parse_view_directive("view(matrix)")
        self.assertIsNone(err)
        self.assertEqual(view, "matrix")
        self.assertEqual(body, "")

    def test_view_case_insensitive(self):
        view, body, err = parse_view_directive("VIEW(MATRIX) AND (web)")
        self.assertIsNone(err)
        self.assertEqual(view, "matrix")
        self.assertEqual(body, "(web)")

    def test_view_table_stripped(self):
        view, body, err = parse_view_directive("Name(server) AND view(table)")
        self.assertIsNone(err)
        self.assertEqual(view, "table")
        self.assertEqual(body, "Name(server)")

    def test_view_table_only(self):
        view, body, err = parse_view_directive("view(table)")
        self.assertIsNone(err)
        self.assertEqual(view, "table")
        self.assertEqual(body, "")

    def test_multiple_view_directives_last_wins_on_parse(self):
        view, body, err = parse_view_directive("view(matrix) AND view(group)")
        self.assertIsNone(err)
        self.assertEqual(view, "group")
        self.assertEqual(body, "")

    def test_duplicate_view_directives_last_wins_on_parse(self):
        view, body, err = parse_view_directive(
            "Name(server) AND view(matrix) AND view(group) AND view(group)"
        )
        self.assertIsNone(err)
        self.assertEqual(view, "group")
        self.assertEqual(body, "Name(server)")

    def test_count_view_directives(self):
        self.assertEqual(count_view_directives("Name(server)"), 0)
        self.assertEqual(count_view_directives("view(matrix)"), 1)
        self.assertEqual(
            count_view_directives("view(matrix) AND view(group) AND Name(x)"),
            2,
        )

    def test_validate_view_directive_count_rejects_multiple(self):
        self.assertIsNone(validate_view_directive_count("view(matrix)"))
        err = validate_view_directive_count("view(matrix) AND view(group)")
        self.assertEqual(err, VIEW_DIRECTIVE_MULTIPLE_ERROR)
        self.assertIn("view(table)", err)

    def test_normalize_filter_query_view(self):
        self.assertEqual(
            normalize_filter_query_view(
                "Name(server) AND view(matrix) AND view(group)"
            ),
            "Name(server) AND view(group)",
        )
        self.assertEqual(
            normalize_filter_query_view("view(matrix) AND view(table)"),
            "",
        )

    def test_format_filter_query_with_view(self):
        self.assertEqual(
            format_filter_query_with_view("Name(server)", "matrix"),
            "Name(server) AND view(matrix)",
        )
        self.assertEqual(format_filter_query_with_view("", "matrix"), "view(matrix)")
        self.assertEqual(format_filter_query_with_view("Name(x)", None), "Name(x)")
        self.assertEqual(format_filter_query_with_view("Name(x)", "table"), "Name(x)")

    def test_format_filter_query_with_view_replaces_existing(self):
        self.assertEqual(
            format_filter_query_with_view("Name(server) AND view(group)", "matrix"),
            "Name(server) AND view(matrix)",
        )

    def test_build_filter_model_strips_view(self):
        column_map = {
            "name": "Name",
        }
        model, err = build_ag_grid_filter_model_from_column_map(
            "Name(server) AND view(matrix)",
            column_map,
        )
        self.assertIsNone(err)
        self.assertEqual(
            model["name"],
            {"filterType": "text", "type": "equals", "filter": "server"},
        )

    def test_validate_rules_filter_query_rejects_multiple_views(self):
        class _Helpers:
            @staticmethod
            def _build_grouped_rules_table_data(_rules, _rulebook):
                return {"rules_layout": [{"slug": "name", "label": "Name"}]}

        class _Rulebook:
            pk = 1

        payload = validate_rules_filter_query(
            "Name(server) AND view(matrix) AND view(group)",
            _Rulebook(),
            _Helpers(),
        )
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["error"], VIEW_DIRECTIVE_MULTIPLE_ERROR)
