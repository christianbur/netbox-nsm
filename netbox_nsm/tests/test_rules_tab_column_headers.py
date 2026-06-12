"""Rules tab thead column header metadata."""

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.grid_payload import build_rulebook_rules_grid_column_defs
from netbox_nsm.rulebooks.rules_tab_base import (
    COLUMN_MODE_EXPANDED,
    _annotate_rules_columns,
    attach_rules_column_defs_meta,
    flatten_rules_column_defs,
    rules_field_display_label,
    rules_object_column_header_parts,
)


def _sample_grouped():
    return {
        "rules_layout": [
            {"kind": "system", "slug": "index", "label": "Index"},
            {"kind": "system", "slug": "name", "label": "Name"},
            {
                "kind": "object",
                "slug": "source_zones",
                "label": "Zones (Source)",
                "field_label": "Zones",
                "field_group": "Source",
                "group": {
                    "slug": "source_zones",
                    "label": "Zones (Source)",
                    "field_label": "Zones",
                    "field_group": "Source",
                    "columns": [
                        {
                            "key": "source_zones::ct_1",
                            "label": "Zone",
                            "area_slug": "source_zones",
                        },
                    ],
                },
            },
            {
                "kind": "object",
                "slug": "source_addresses",
                "label": "Addresses (Source)",
                "field_label": "Addresses",
                "field_group": "Source",
                "group": {
                    "slug": "source_addresses",
                    "label": "Addresses (Source)",
                    "field_label": "Addresses",
                    "field_group": "Source",
                    "columns": [
                        {
                            "key": "source_addresses::ct_1",
                            "label": "Address",
                            "area_slug": "source_addresses",
                        },
                    ],
                },
            },
        ],
    }


def _sample_ungrouped_field():
    return {
        "rules_layout": [
            {
                "kind": "object",
                "slug": "services_applications",
                "label": "Services & Applications",
                "field_label": "Services & Applications",
                "field_group": "",
                "group": {
                    "slug": "services_applications",
                    "label": "Services & Applications",
                    "field_label": "Services & Applications",
                    "field_group": "",
                    "columns": [
                        {
                            "key": "services_applications::ct_1",
                            "label": "Network App",
                            "area_slug": "services_applications",
                        },
                    ],
                },
            },
        ],
    }


class RulesTabColumnHeaderTests(SimpleTestCase):
    def test_rules_field_display_label_with_group(self):
        self.assertEqual(
            rules_field_display_label("Zones", "Source"), "Zones (Source)"
        )

    def test_rules_field_display_label_resolves_sort_key_group(self):
        self.assertEqual(
            rules_field_display_label("Zones", "2# Source"), "Zones (2# Source)"
        )

    def test_rules_field_display_label_without_group(self):
        self.assertEqual(
            rules_field_display_label("Services & Applications", ""), "Services & Applications"
        )

    def test_rules_field_display_label_skips_duplicate_group(self):
        self.assertEqual(
            rules_field_display_label("Services & Applications", "Services & Applications"),
            "Services & Applications",
        )

    def test_rules_object_column_header_parts_no_group_name(self):
        title, subtitle = rules_object_column_header_parts(
            "Network App",
            "Services & Applications",
            field_label="Services & Applications",
            field_group="",
        )
        self.assertEqual(title, "Services & Applications")
        self.assertEqual(subtitle, "Network App")

    def test_rules_object_column_header_parts_split_field_metadata(self):
        title, subtitle = rules_object_column_header_parts(
            "Address",
            field_label="Addresses",
            field_group="Source",
        )
        self.assertEqual(title, "Addresses (Source)")
        self.assertEqual(subtitle, "Address")

    def test_rules_object_column_header_parts_legacy_combined_group(self):
        title, subtitle = rules_object_column_header_parts(
            "Address", "Addresses (Source)"
        )
        self.assertEqual(title, "Addresses (Source)")
        self.assertEqual(subtitle, "Address")

    def test_rules_object_column_header_parts_short_group(self):
        title, subtitle = rules_object_column_header_parts("Zones", "Source")
        self.assertEqual(title, "Zones (Source)")
        self.assertEqual(subtitle, "Zones")

    def test_attach_rules_column_defs_meta_sets_display_labels(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )

        class FakeRequest:
            GET = {}
            COOKIES = {}
            path = "/plugins/netbox_nsm/rulebooks/cot/demo/rules/"

        _annotate_rules_columns(
            flat_columns,
            request=FakeRequest(),
            sort_field="index",
            sort_order="asc",
            base_qs_str="",
        )
        attach_rules_column_defs_meta(column_defs, flat_columns)

        zones_parent = next(
            c
            for c in column_defs
            if c.get("field_label") == "Zones" and c.get("field_group") == "Source"
        )
        zones_child = zones_parent["children"][0]
        addr_parent = next(
            c
            for c in column_defs
            if c.get("field_label") == "Addresses" and c.get("field_group") == "Source"
        )
        addr_child = addr_parent["children"][0]
        self.assertEqual(zones_child["header_title"], "Zones (Source)")
        self.assertEqual(zones_child["header_subtitle"], "Zone")
        self.assertEqual(zones_child["display_label"], "Zone, Zones (Source)")
        self.assertEqual(addr_child["header_title"], "Addresses (Source)")
        self.assertEqual(addr_child["header_subtitle"], "Address")
        self.assertEqual(addr_child["display_label"], "Address, Addresses (Source)")
        self.assertIn("rules_meta", zones_child)
        self.assertTrue(zones_child["rules_meta"]["sort_url"])

        index_col = next(c for c in column_defs if c.get("colId") == "index")
        self.assertIn("rules_meta", index_col)

    def test_attach_rules_column_defs_meta_ungrouped_field_no_duplicate_title(self):
        grouped = _sample_ungrouped_field()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )

        class FakeRequest:
            GET = {}
            COOKIES = {}
            path = "/plugins/netbox_nsm/rulebooks/cot/demo/rules/"

        _annotate_rules_columns(
            flat_columns,
            request=FakeRequest(),
            sort_field="index",
            sort_order="asc",
            base_qs_str="",
        )
        attach_rules_column_defs_meta(column_defs, flat_columns)

        parent = column_defs[0]
        child = parent["children"][0]
        self.assertEqual(child["header_title"], "Services & Applications")
        self.assertEqual(child["header_subtitle"], "Network App")
        self.assertEqual(child["display_label"], "Network App, Services & Applications")

    def test_flatten_rules_column_defs_collapsed_ungrouped_field(self):
        grouped = _sample_ungrouped_field()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(column_defs, column_mode="collapsed")
        data_columns = [col for col in flat_columns if col.get("col_id") != "_actions"]
        self.assertEqual(len(data_columns), 1)
        self.assertEqual(data_columns[0]["header_title"], "Services & Applications")
        self.assertEqual(flat_columns[0]["header_subtitle"], "")
