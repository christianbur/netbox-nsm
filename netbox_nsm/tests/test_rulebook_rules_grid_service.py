"""Policy grid lazy loading helpers."""

from django.test import SimpleTestCase

from netbox_nsm.rulebook_rules_grid_payload import (
    RULES_ROW_HEIGHT,
    _description_cell_html,
    _description_line_count,
    apply_ag_grid_row_filter,
    build_rulebook_rules_grid_row,
    build_rulebook_rules_group_row_record,
    rules_group_row_height_for_label,
    rules_row_height_for_object_lines,
)


class PolicyGridServiceTests(SimpleTestCase):
    def test_build_row_uses_raw_items(self):
        row = build_rulebook_rules_grid_row(
            {
                "pk": 7,
                "edit_url": "/edit/",
                "delete_url": "/delete/",
                "system": {
                    "enabled": True,
                    "name": "r1",
                    "index": 10,
                    "url": "/detail/",
                    "description": "note",
                },
                "cells_items": {
                    "source::ct_1": [{"url": "/z/", "name": "dmz", "color": "#111"}],
                },
                "cells_filter": {"source::ct_1": "dmz"},
            }
        )
        self.assertEqual(row["source::ct_1"][0]["name"], "dmz")
        self.assertEqual(row["source::ct_1__filter"], "dmz")
        self.assertEqual(row["_objectLineCount"], 1)
        self.assertEqual(row["_rowHeight"], rules_row_height_for_object_lines(1))

    def test_build_row_height_scales_with_object_count(self):
        items = [{"name": f"obj-{i}"} for i in range(8)]
        row = build_rulebook_rules_grid_row(
            {
                "pk": 8,
                "edit_url": "/edit/",
                "delete_url": "/delete/",
                "system": {"enabled": True, "name": "r8", "index": 80},
                "cells_items": {
                    "source::ct_1": items,
                    "destination::ct_1": items[:3],
                },
            }
        )
        self.assertEqual(row["_objectLineCount"], 8)
        self.assertEqual(row["_rowHeight"], rules_row_height_for_object_lines(8))
        self.assertGreater(row["_rowHeight"], RULES_ROW_HEIGHT)

    def test_description_line_count_splits_source_dest(self):
        desc = (
            "Source ×1 (demo-addr-0001) → "
            "Dest ×3 (demo-addr-0032, demo-addr-0033, demo-addr-0034)"
        )
        self.assertEqual(_description_line_count(desc), 2)
        html = _description_cell_html({"description": desc})
        self.assertIn("nsm-ag-description-lines", html)
        self.assertIn("Dest ×3", html)
        self.assertNotIn("…", html)

    def test_build_row_height_includes_description_lines(self):
        desc = "Source ×1 (a) → Dest ×2 (b, c)"
        row = build_rulebook_rules_grid_row(
            {
                "pk": 11,
                "edit_url": "/edit/",
                "delete_url": "/delete/",
                "system": {
                    "enabled": True,
                    "name": "r11",
                    "index": 110,
                    "description": desc,
                },
                "cells_items": {
                    "source::ct_1": [{"name": "a"}],
                },
            }
        )
        self.assertEqual(row["_descriptionLineCount"], 2)
        self.assertEqual(row["_objectLineCount"], 1)
        self.assertEqual(row["_rowHeight"], rules_row_height_for_object_lines(2))

    def test_apply_ag_grid_row_filter_contains(self):
        rows = [
            {"name": "alpha", "source::ct_1": [{"name": "dmz"}]},
            {"name": "beta", "source::ct_1": [{"name": "lan"}]},
        ]
        filtered = apply_ag_grid_row_filter(
            rows,
            {
                "source::ct_1": {
                    "filterType": "text",
                    "type": "contains",
                    "filter": "dmz",
                }
            },
        )
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "alpha")

    def test_build_group_row_record_multiline_label_height(self):
        record = build_rulebook_rules_group_row_record(
            {"label": "alpha\nbeta\ngamma", "url": "#"},
            group_key="col:source::ct_1::set::alpha|beta|gamma",
            rule_count=4,
        )
        self.assertEqual(record["_groupLabel"], "alpha\nbeta\ngamma")
        self.assertGreater(record["_rowHeight"], 36)
        self.assertEqual(
            rules_group_row_height_for_label("alpha\nbeta\ngamma"),
            record["_rowHeight"],
        )

    def test_build_group_row_record(self):
        record = build_rulebook_rules_group_row_record(
            {"label": "prod", "url": "/zones/1/", "color": "#111"},
            group_key="col:source::ct_1::prod",
            rule_count=3,
        )
        self.assertEqual(record["_rowType"], "group")
        self.assertEqual(record["_groupLabel"], "prod")
        self.assertEqual(record["_ruleCount"], 3)
        self.assertEqual(record["_groupKey"], "col:source::ct_1::prod")

    def test_build_group_row_record_with_level(self):
        record = build_rulebook_rules_group_row_record(
            {"label": "prod", "url": "#"},
            group_key="col:source::ct_1::prod",
            rule_count=2,
            group_level=2,
            group_field_label="Source / Zones",
        )
        self.assertEqual(record["_groupLevel"], 2)
        self.assertEqual(record["_groupFieldLabel"], "Source / Zones")

    def test_rule_row_lacks_group_header_fields(self):
        row = build_rulebook_rules_grid_row(
            {
                "pk": 9,
                "edit_url": "/edit/",
                "delete_url": "/delete/",
                "system": {"enabled": True, "name": "r9", "index": 90},
                "cells_items": {},
            }
        )
        row["_rowType"] = "rule"
        row["_groupKey"] = "col:source::ct_1::prod"
        self.assertNotIn("_groupLabel", row)
        self.assertNotIn("_groupLevel", row)
        self.assertNotIn("_ruleCount", row)

    def test_group_row_record_is_distinct_from_rule_row(self):
        group = build_rulebook_rules_group_row_record(
            {"label": "United States", "url": "#"},
            group_key="col:source::ct_1::us",
            rule_count=1109,
            group_level=1,
        )
        rule = build_rulebook_rules_grid_row(
            {
                "pk": 1,
                "edit_url": "/edit/",
                "delete_url": "/delete/",
                "system": {"enabled": True, "name": "r1", "index": 1},
                "cells_items": {},
            }
        )
        rule["_rowType"] = "rule"
        rule["_groupKey"] = group["_groupKey"]
        self.assertEqual(group["_rowType"], "group")
        self.assertEqual(rule["_rowType"], "rule")
        self.assertIn("_groupLabel", group)
        self.assertNotIn("_groupLabel", rule)

    def test_build_group_column_def(self):
        from netbox_nsm.rulebook_rules_grid_payload import (
            build_rulebook_rules_group_column_def,
        )

        col = build_rulebook_rules_group_column_def()
        self.assertEqual(col["colId"], "_group")
        self.assertEqual(col["pinned"], "left")
        self.assertEqual(col["cellRenderer"], "rulesGroupCell")
        self.assertFalse(col["sortable"])
        self.assertFalse(col["filter"])
