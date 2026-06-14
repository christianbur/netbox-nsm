"""Shared rules grid payload helpers for Rules."""

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.grid import (
    apply_ag_grid_row_filter,
    build_ag_grid_filter_model_from_query_text,
    build_column_quick_filter_spec,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_grid_row,
    filter_spec_to_column_quick_value,
)
from netbox_nsm.rulebooks.cell_html import render_rules_cell_ag


def _sample_grouped():
    return {
        "rules_layout": [
            {"kind": "system", "slug": "status", "label": "Status"},
            {"kind": "system", "slug": "name", "label": "Name"},
            {"kind": "system", "slug": "index", "label": "Index"},
            {"kind": "system", "slug": "description", "label": "Description"},
            {
                "kind": "object",
                "slug": "source",
                "label": "Source",
                "group": {
                    "slug": "source",
                    "label": "Source",
                    "columns": [
                        {
                            "key": "source::ct_1",
                            "label": "Zones",
                            "area_slug": "source",
                        }
                    ],
                },
            },
        ],
        "rows": [
            {
                "pk": 1,
                "edit_url": "/plugins/netbox-nsm/rules/1/edit/",
                "delete_url": "/plugins/netbox-nsm/rules/1/delete/",
                "system": {
                    "enabled": True,
                    "name": "rule-one",
                    "index": 1,
                    "url": "/plugins/netbox-nsm/rules/1/",
                    "description": "Short desc",
                },
                "cells_items": {
                    "source::ct_1": [
                        {"url": "/z/1/", "name": "DMZ", "color": "#336699"}
                    ],
                },
                "cells_filter": {
                    "source::ct_1": "prod dmz",
                },
            }
        ],
    }


class RulesGridPayloadTests(SimpleTestCase):
    def test_empty_column_defs(self):
        payload = build_rulebook_rules_grid_column_defs(
            {"rules_layout": [], "rows": []}
        )
        self.assertEqual(len(payload["columnDefs"]), 1)
        self.assertEqual(payload["columnDefs"][0]["colId"], "_actions")

    def test_ag_cell_uses_dot_and_standard_link(self):
        html = render_rules_cell_ag(
            [{"url": "/z/1/", "name": "DMZ", "color": "#336699"}],
            max_pills=5,
        )
        self.assertIn("nsm-ag-cell-dot", html)
        self.assertIn("#336699", html)
        self.assertIn("nsm-ag-cell-link", html)
        self.assertNotIn("nsm-rule-pill", html)

    def test_build_row_record(self):
        row = build_rulebook_rules_grid_row(_sample_grouped()["rows"][0])
        self.assertTrue(row["enabled"])
        self.assertEqual(row["name"], "rule-one")
        self.assertEqual(row["index"], 1)
        self.assertEqual(row["source::ct_1__filter"], "prod dmz")
        self.assertEqual(row["source::ct_1"][0]["name"], "DMZ")

    def test_apply_row_filter(self):
        record = build_rulebook_rules_grid_row(_sample_grouped()["rows"][0])
        filtered = apply_ag_grid_row_filter(
            [record],
            {"name": {"filterType": "text", "type": "contains", "filter": "rule-one"}},
        )
        self.assertEqual(len(filtered), 1)
        missing = apply_ag_grid_row_filter(
            [record],
            {"name": {"filterType": "text", "type": "contains", "filter": "missing"}},
        )
        self.assertEqual(missing, [])

    def test_build_column_quick_filter_spec(self):
        self.assertEqual(
            build_column_quick_filter_spec("alpha"),
            {"filterType": "text", "type": "contains", "filter": "alpha"},
        )
        and_spec = build_column_quick_filter_spec("rule1 AND rule2")
        self.assertEqual(and_spec["operator"], "AND")
        self.assertEqual(
            [cond["filter"] for cond in and_spec["conditions"]],
            ["rule1", "rule2"],
        )
        or_spec = build_column_quick_filter_spec("rule1 OR rule2")
        self.assertEqual(or_spec["operator"], "OR")

    def test_apply_row_filter_and_or(self):
        record = build_rulebook_rules_grid_row(_sample_grouped()["rows"][0])
        and_spec = build_column_quick_filter_spec("rule AND one")
        filtered_and = apply_ag_grid_row_filter([record], {"name": and_spec})
        self.assertEqual(len(filtered_and), 1)
        missing_and = apply_ag_grid_row_filter(
            [record],
            {"name": build_column_quick_filter_spec("rule AND missing")},
        )
        self.assertEqual(missing_and, [])
        filtered_or = apply_ag_grid_row_filter(
            [record],
            {"name": build_column_quick_filter_spec("missing OR one")},
        )
        self.assertEqual(len(filtered_or), 1)

    def test_object_groups_have_detail_columns(self):
        payload = build_rulebook_rules_grid_column_defs(_sample_grouped())
        source_group = next(
            c for c in payload["columnDefs"] if c.get("headerName") == "Source"
        )
        self.assertEqual(len(source_group["children"]), 1)
        self.assertEqual(source_group["children"][0]["field"], "source::ct_1")

    def test_filter_spec_to_column_quick_value(self):
        self.assertEqual(
            filter_spec_to_column_quick_value(
                {"filterType": "text", "type": "equals", "filter": "demo-0001"}
            ),
            "demo-0001",
        )
        self.assertEqual(
            filter_spec_to_column_quick_value(
                {
                    "filterType": "text",
                    "operator": "OR",
                    "conditions": [
                        {"filterType": "text", "type": "contains", "filter": "a"},
                        {"filterType": "text", "type": "contains", "filter": "b"},
                    ],
                }
            ),
            "a OR b",
        )

    def test_build_filter_model_from_verbose_nsm_query(self):
        from types import SimpleNamespace

        layout = _sample_grouped()["rules_layout"]

        class FakeContext:
            def get_field(self, name):
                if str(name).lower() == "source":
                    return SimpleNamespace(slug="source", pk=1, name="Source")
                return None

        model, err = build_ag_grid_filter_model_from_query_text(
            'Source.Zones.name == "dmz"',
            layout,
            FakeContext(),
        )
        self.assertIsNone(err)
        self.assertEqual(
            model["source::ct_1"],
            {"filterType": "text", "type": "contains", "filter": "dmz"},
        )
