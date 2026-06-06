"""Rules grid filter model → matrix axis query strings."""

import unittest

from netbox_nsm.matrix_filter_query import (
    ag_grid_col_filter_to_axis_query,
    extract_matrix_axis_queries,
    matrix_value_to_column_key,
)


class MatrixFilterQueryTests(unittest.TestCase):
    def test_matrix_value_to_column_key(self):
        self.assertEqual(
            matrix_value_to_column_key("col:source::ct_10"), "source::ct_10"
        )
        self.assertIsNone(matrix_value_to_column_key("source::ct_10"))

    def test_single_contains_to_axis_query(self):
        model = {"filterType": "text", "type": "contains", "filter": "dmz"}
        self.assertEqual(ag_grid_col_filter_to_axis_query(model), "dmz")

    def test_or_conditions_to_axis_query(self):
        model = {
            "filterType": "text",
            "operator": "OR",
            "conditions": [
                {"filterType": "text", "type": "contains", "filter": "dmz"},
                {"filterType": "text", "type": "contains", "filter": "mgmt"},
            ],
        }
        self.assertEqual(ag_grid_col_filter_to_axis_query(model), "dmz OR mgmt")

    def test_and_conditions_to_axis_query(self):
        model = {
            "filterType": "text",
            "operator": "AND",
            "conditions": [
                {"filterType": "text", "type": "contains", "filter": "prod"},
                {"filterType": "text", "type": "contains", "filter": "test"},
            ],
        }
        self.assertEqual(ag_grid_col_filter_to_axis_query(model), "prod AND test")

    def test_extract_matrix_axis_queries(self):
        filter_model = {
            "source::ct_10": {
                "filterType": "text",
                "type": "contains",
                "filter": "dmz",
            },
            "destination::ct_10": {
                "filterType": "text",
                "operator": "OR",
                "conditions": [
                    {"filterType": "text", "type": "contains", "filter": "app"},
                    {"filterType": "text", "type": "contains", "filter": "web"},
                ],
            },
            "name": {
                "filterType": "text",
                "type": "contains",
                "filter": "server",
            },
        }
        src_q, dst_q = extract_matrix_axis_queries(
            filter_model,
            "col:source::ct_10",
            "col:destination::ct_10",
        )
        self.assertEqual(src_q, "dmz")
        self.assertEqual(dst_q, "app OR web")

    def test_extract_ignores_unrelated_columns(self):
        filter_model = {
            "name": {"filterType": "text", "type": "contains", "filter": "server"},
        }
        src_q, dst_q = extract_matrix_axis_queries(
            filter_model,
            "col:source::ct_10",
            "col:destination::ct_10",
        )
        self.assertEqual(src_q, "")
        self.assertEqual(dst_q, "")


if __name__ == "__main__":
    unittest.main()
