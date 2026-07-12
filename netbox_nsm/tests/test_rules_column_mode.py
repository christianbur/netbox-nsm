"""Rules tab column layout mode (expanded vs collapsed polymorphic columns)."""

from django.test import RequestFactory, SimpleTestCase
from unittest.mock import patch

from netbox_nsm.rulebooks.cell_html import render_rules_merged_object_cell_html
from netbox_nsm.rulebooks.cell_html import render_rules_object_cell_html
from netbox_nsm.rulebooks.rules_pill_render import render_rules_pill_cell
from netbox_nsm.rulebooks.grid import (
    _record_field_filter_text,
    build_rulebook_rules_grid_column_defs,
)
from netbox_nsm.rulebooks.rules_tab import (
    COLUMN_MODE_COLLAPSED,
    COLUMN_MODE_EXPANDED,
    _annotate_rules_columns,
    attach_rules_column_defs_meta,
    collapse_rules_column_defs,
    flatten_rules_column_defs,
    prepare_rules_column_defs,
    normalize_rules_column_mode,
    parse_rules_column_mode,
    parse_rules_filter_model,
)


def _sample_grouped():
    return {
        "rules_layout": [
            {"kind": "system", "slug": "index", "label": "Index"},
            {
                "kind": "object",
                "slug": "source_addresses",
                "label": "Addresses (Source)",
                "field_label": "Addresses",
                "field_group": "Source",
                "is_polymorphic": True,
                "group": {
                    "slug": "source_addresses",
                    "label": "Addresses (Source)",
                    "field_label": "Addresses",
                    "field_group": "Source",
                    "is_polymorphic": True,
                    "columns": [
                        {
                            "key": "source_addresses::ct_1",
                            "label": "Address",
                            "area_slug": "source_addresses",
                        },
                        {
                            "key": "source_addresses::ct_2",
                            "label": "Address Group",
                            "area_slug": "source_addresses",
                        },
                    ],
                },
            },
        ],
    }


def _sample_zone_polymorphic():
    return {
        "rules_layout": [
            {
                "kind": "object",
                "slug": "source_zones",
                "label": "Zones (Source)",
                "field_label": "Zones",
                "field_group": "Source",
                "is_polymorphic": True,
                "group": {
                    "slug": "source_zones",
                    "label": "Zones (Source)",
                    "field_label": "Zones",
                    "field_group": "Source",
                    "is_polymorphic": True,
                    "columns": [
                        {
                            "key": "source_zones::ct_10",
                            "label": "Zone",
                            "area_slug": "source_zones",
                        },
                        {
                            "key": "source_zones::ct_11",
                            "label": "Label",
                            "area_slug": "source_zones",
                        },
                    ],
                },
            },
        ],
    }


class RulesColumnModeTests(SimpleTestCase):
    def test_merged_cell_suppresses_redundant_targets_heading_for_grouped_items(self):
        from netbox_nsm.rulebooks.rules_tab.cells import _build_rules_cell_html

        request = RequestFactory().get("/rules/")
        row = {
            "index": 1,
            "name": "Rule A",
            "cells_items": {
                "source_segments::ct_7::col_targets": [
                    {"name": "Service (Targets)", "group_label": True},
                    {"name": "HTTPS (tcp/443)"},
                ]
            },
            "system": {},
        }
        col = {
            "kind": "object",
            "key": "source_segments",
            "merged_keys": ["source_segments::ct_7::col_targets"],
            "type_segments": [
                {
                    "key": "source_segments::ct_7::col_targets",
                    "type_label": "Targets",
                }
            ],
            "is_polymorphic": True,
        }

        with patch(
            "netbox_nsm.rulebooks.rules_tab.cells.render_rules_merged_object_cell_html",
            return_value="<div></div>",
        ) as mocked:
            _build_rules_cell_html(
                col,
                row,
                request=request,
                can_change=False,
                can_delete=False,
                can_add=False,
                rulebook_slug="",
                object_fields_by_slug={},
            )

        args, kwargs = mocked.call_args
        type_segments = args[0]
        self.assertEqual(type_segments[0]["type_label"], "")
        self.assertTrue(kwargs["is_polymorphic"])

    def test_merged_cell_suppresses_outer_heading_for_segment_split_items(self):
        from netbox_nsm.rulebooks.rules_tab.cells import _build_rules_cell_html

        request = RequestFactory().get("/rules/")
        row = {
            "index": 1,
            "name": "Rule A",
            "cells_items": {
                "source_segments::ct_7::col_app": [
                    {"name": "erp-src-admin", "segment_label": True},
                    {"name": "ERP-Core", "group_item": True},
                ]
            },
            "system": {},
        }
        col = {
            "kind": "object",
            "key": "source_segments",
            "merged_keys": ["source_segments::ct_7::col_app"],
            "type_segments": [
                {
                    "key": "source_segments::ct_7::col_app",
                    "type_label": "Business App",
                }
            ],
            "is_polymorphic": True,
        }

        with patch(
            "netbox_nsm.rulebooks.rules_tab.cells.render_rules_merged_object_cell_html",
            return_value="<div></div>",
        ) as mocked:
            _build_rules_cell_html(
                col,
                row,
                request=request,
                can_change=False,
                can_delete=False,
                can_add=False,
                rulebook_slug="",
                object_fields_by_slug={},
            )

        args, kwargs = mocked.call_args
        type_segments = args[0]
        self.assertEqual(type_segments[0]["type_label"], "Business App")
        self.assertTrue(kwargs["is_polymorphic"])

    def test_render_rules_merged_object_cell_html_segment_oriented(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Business App",
                    "items": [
                        {
                            "name": "erp-src-admin",
                            "segment_label": True,
                            "segment_type_label": "Business App Segment",
                            "url": "/s/1/",
                        },
                        {"name": "ERP-Core", "group_item": True, "url": "/a/1/"},
                        {
                            "name": "erp-src-users",
                            "segment_label": True,
                            "segment_type_label": "Business App Segment",
                            "url": "/s/2/",
                        },
                        {"name": "ERP-Core", "group_item": True, "url": "/a/2/"},
                    ],
                },
                {
                    "type_label": "Segment Type",
                    "items": [
                        {
                            "name": "erp-src-admin",
                            "segment_label": True,
                            "segment_type_label": "Business App Segment",
                            "url": "/s/1/",
                        },
                        {"name": "source", "group_item": True},
                        {
                            "name": "erp-src-users",
                            "segment_label": True,
                            "segment_type_label": "Business App Segment",
                            "url": "/s/2/",
                        },
                        {"name": "source", "group_item": True},
                    ],
                },
            ],
            is_polymorphic=True,
        )
        self.assertIn("erp-src-admin", html)
        self.assertIn("erp-src-users", html)
        self.assertIn("Business App Segment", html)
        self.assertIn("Business App", html)
        self.assertIn("Segment Type", html)
        self.assertIn("nsm-ag-cell-segment-block", html)

    def test_render_rules_pill_cell_allows_items_without_url(self):
        html = render_rules_pill_cell([{"name": "ERP-Core"}], colored=False)
        self.assertIn("ERP-Core", html)
        self.assertNotIn('href=""', html)

    def test_render_rules_object_cell_html_allows_items_without_url(self):
        html = render_rules_object_cell_html(
            [{"name": "destination", "color": ""}],
            colored=False,
        )
        self.assertIn("destination", html)
        self.assertNotIn('href=""', html)

    def test_normalize_rules_column_mode(self):
        self.assertEqual(normalize_rules_column_mode("collapsed"), COLUMN_MODE_COLLAPSED)
        self.assertEqual(normalize_rules_column_mode("expanded"), COLUMN_MODE_EXPANDED)
        self.assertEqual(normalize_rules_column_mode("invalid"), COLUMN_MODE_COLLAPSED)
        self.assertEqual(normalize_rules_column_mode(None), COLUMN_MODE_COLLAPSED)

    def test_parse_rules_column_mode_from_request(self):
        request = RequestFactory().get("/rules/?col_mode=collapsed")
        self.assertEqual(parse_rules_column_mode(request), COLUMN_MODE_COLLAPSED)

        request = RequestFactory().get("/rules/")
        self.assertEqual(parse_rules_column_mode(request), COLUMN_MODE_COLLAPSED)

        request = RequestFactory().get("/rules/?col_mode=expanded")
        self.assertEqual(parse_rules_column_mode(request), COLUMN_MODE_EXPANDED)

    def test_collapse_rules_column_defs_merges_children(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        collapsed = collapse_rules_column_defs(column_defs)

        object_cols = [
            col for col in collapsed if col.get("colId") not in ("index", "_actions")
        ]
        self.assertEqual(len(object_cols), 1)
        merged = object_cols[0]
        self.assertEqual(merged["colId"], "source_addresses")
        self.assertEqual(merged["headerName"], "Addresses (Source)")
        self.assertEqual(
            merged["merged_keys"],
            ["source_addresses::ct_1", "source_addresses::ct_2"],
        )
        self.assertTrue(merged["is_polymorphic"])

    def test_flatten_collapsed_mode_single_column_without_subtitle(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
        )

        object_cols = [col for col in flat_columns if col["kind"] == "object"]
        self.assertEqual(len(object_cols), 1)
        col = object_cols[0]
        self.assertEqual(col["col_id"], "source_addresses")
        self.assertEqual(col["header_title"], "Addresses (Source)")
        self.assertEqual(col["header_subtitle"], "")
        self.assertEqual(len(col["type_segments"]), 2)
        self.assertTrue(col["is_polymorphic"])

    def test_flatten_expanded_mode_splits_address_types(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )

        object_cols = [col for col in flat_columns if col["kind"] == "object"]
        self.assertEqual(len(object_cols), 2)
        self.assertEqual(
            [col["col_id"] for col in object_cols],
            ["source_addresses::ct_1", "source_addresses::ct_2"],
        )
        self.assertEqual(object_cols[0]["header_subtitle"], "Address")
        self.assertEqual(object_cols[1]["header_subtitle"], "Address Group")

    def test_flatten_expanded_mode_keeps_non_address_type_columns(self):
        grouped = _sample_zone_polymorphic()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )

        object_cols = [col for col in flat_columns if col["kind"] == "object"]
        self.assertEqual(len(object_cols), 2)
        self.assertEqual(object_cols[0]["header_subtitle"], "Zone")
        self.assertEqual(object_cols[1]["header_subtitle"], "Label")

    def test_prepare_rules_column_defs_expanded_keeps_all_type_columns(self):
        grouped = {
            "rules_layout": [
                _sample_grouped()["rules_layout"][1],
                _sample_zone_polymorphic()["rules_layout"][0],
            ],
        }
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        prepared = prepare_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )

        address_col = next(
            col for col in prepared if (col.get("headerName") or "").startswith("Addresses")
        )
        zone_col = next(
            col for col in prepared if (col.get("headerName") or "").startswith("Zones")
        )
        self.assertIn("children", address_col)
        self.assertNotIn("merged_keys", address_col)
        self.assertIn("children", zone_col)

    def test_flatten_assigns_col_position_excluding_actions(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_EXPANDED
        )
        data_cols = [col for col in flat_columns if col.get("col_id") != "_actions"]
        for idx, col in enumerate(data_cols, start=1):
            self.assertEqual(col.get("col_position"), idx)
        actions = next(col for col in flat_columns if col.get("col_id") == "_actions")
        self.assertNotIn("col_position", actions)

    def test_attach_rules_column_defs_meta_collapsed_object_header(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
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

        merged_col = next(
            col for col in column_defs if col.get("colId") == "source_addresses"
        )
        self.assertEqual(merged_col["rules_column_kind"], "object")
        self.assertEqual(merged_col["header_title"], "Addresses (Source)")
        self.assertEqual(merged_col["header_subtitle"], "")
        self.assertEqual(merged_col["display_label"], "Addresses (Source)")

    def test_record_field_filter_text_merges_polymorphic_keys(self):
        record = {
            "source_addresses::ct_1": "",
            "source_addresses::ct_1__filter": "web-server",
            "source_addresses::ct_2": "",
            "source_addresses::ct_2__filter": "dmz-group",
        }
        text = _record_field_filter_text(record, "source_addresses")
        self.assertIn("web-server", text)
        self.assertIn("dmz-group", text)

    def test_render_rules_merged_object_cell_html_groups_by_type(self):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Address",
                    "items": [{"url": "/a/1/", "name": "web-server", "color": ""}],
                },
                {
                    "type_label": "Address Group",
                    "items": [{"url": "/g/1/", "name": "dmz", "color": ""}],
                },
            ],
            is_polymorphic=True,
        )
        self.assertIn("nsm-ag-cell-merged", html)
        self.assertIn("nsm-ag-cell-type-subheading", html)
        self.assertNotIn("nsm-ag-cell-type-badge", html)
        self.assertEqual(html.count("Address</span>"), 1)
        self.assertEqual(html.count("Address Group</span>"), 1)
        self.assertIn("Address Group", html)
        self.assertIn("web-server", html)
        self.assertIn("dmz", html)

    def test_render_rules_merged_object_cell_html_hides_subheading_when_not_polymorphic(
        self,
    ):
        html = render_rules_merged_object_cell_html(
            [
                {
                    "type_label": "Zone",
                    "items": [{"url": "/z/1/", "name": "zone_01", "color": ""}],
                },
            ],
            is_polymorphic=False,
        )
        self.assertNotIn("nsm-ag-cell-type-subheading", html)
        self.assertNotIn("nsm-ag-cell-type-group", html)
        self.assertNotIn("nsm-ag-cell-merged", html)
        self.assertIn("zone_01", html)

    def test_collapse_single_type_field_not_polymorphic(self):
        grouped = {
            "rules_layout": [
                {
                    "kind": "object",
                    "slug": "source_zones",
                    "label": "Zones (Source)",
                    "field_label": "Zones",
                    "field_group": "Source",
                    "is_polymorphic": False,
                    "group": {
                        "slug": "source_zones",
                        "label": "Zones (Source)",
                        "field_label": "Zones",
                        "field_group": "Source",
                        "is_polymorphic": False,
                        "columns": [
                            {
                                "key": "source_zones::ct_1",
                                "label": "Zone",
                                "area_slug": "source_zones",
                            },
                        ],
                    },
                },
            ],
        }
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        collapsed = collapse_rules_column_defs(column_defs)
        merged = next(
            col for col in collapsed if col.get("colId") == "source_zones"
        )
        self.assertFalse(merged["is_polymorphic"])

    def test_parse_rules_filter_model_collapsed_accepts_field_level_params(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
        )
        request = RequestFactory().get("/rules/?f_source_addresses=web-server")
        model = parse_rules_filter_model(request, flat_columns)
        self.assertEqual(model["source_addresses"]["filter"], "web-server")

    def test_parse_rules_filter_model_collapsed_accepts_expanded_param_aliases(self):
        grouped = _sample_grouped()
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
        )
        request = RequestFactory().get(
            "/rules/?f_source_addresses__ct_1=web-server"
            "&f_source_addresses__ct_2=dmz-group"
        )
        model = parse_rules_filter_model(request, flat_columns)
        self.assertEqual(
            model["source_addresses"]["filter"],
            "web-server",
        )

    def test_annotate_rules_columns_prefills_both_zone_filters_from_url(self):
        grouped = {
            "rules_layout": [
                {
                    "kind": "object",
                    "slug": "source_zones",
                    "label": "Zones (Source)",
                    "field_label": "Zones",
                    "field_group": "Source",
                    "is_polymorphic": False,
                    "group": {
                        "slug": "source_zones",
                        "label": "Zones (Source)",
                        "field_label": "Zones",
                        "field_group": "Source",
                        "is_polymorphic": False,
                        "columns": [
                            {
                                "key": "source_zones::ct_232",
                                "label": "Zone",
                                "area_slug": "source_zones",
                            },
                        ],
                    },
                },
                {
                    "kind": "object",
                    "slug": "destination_zones",
                    "label": "Zones (Destination)",
                    "field_label": "Zones",
                    "field_group": "Destination",
                    "is_polymorphic": False,
                    "group": {
                        "slug": "destination_zones",
                        "label": "Zones (Destination)",
                        "field_label": "Zones",
                        "field_group": "Destination",
                        "is_polymorphic": False,
                        "columns": [
                            {
                                "key": "destination_zones::ct_232",
                                "label": "Zone",
                                "area_slug": "destination_zones",
                            },
                        ],
                    },
                },
            ],
        }
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
        )
        request = RequestFactory().get(
            "/rules/?f_source_zones=zone_01&f_destination_zones=zone_06"
        )
        _annotate_rules_columns(
            flat_columns,
            request=request,
            sort_field="index",
            sort_order="asc",
            base_qs_str="",
        )
        by_id = {col["col_id"]: col for col in flat_columns if col["kind"] == "object"}
        self.assertEqual(by_id["source_zones"]["filter_value"], "zone_01")
        self.assertEqual(by_id["destination_zones"]["filter_value"], "zone_06")

    def test_annotate_rules_columns_legacy_expanded_params_prefill_collapsed(self):
        grouped = {
            "rules_layout": [
                {
                    "kind": "object",
                    "slug": "source_zones",
                    "label": "Zones (Source)",
                    "field_label": "Zones",
                    "field_group": "Source",
                    "is_polymorphic": False,
                    "group": {
                        "slug": "source_zones",
                        "label": "Zones (Source)",
                        "field_label": "Zones",
                        "field_group": "Source",
                        "is_polymorphic": False,
                        "columns": [
                            {
                                "key": "source_zones::ct_232",
                                "label": "Zone",
                                "area_slug": "source_zones",
                            },
                        ],
                    },
                },
                {
                    "kind": "object",
                    "slug": "destination_zones",
                    "label": "Zones (Destination)",
                    "field_label": "Zones",
                    "field_group": "Destination",
                    "is_polymorphic": False,
                    "group": {
                        "slug": "destination_zones",
                        "label": "Zones (Destination)",
                        "field_label": "Zones",
                        "field_group": "Destination",
                        "is_polymorphic": False,
                        "columns": [
                            {
                                "key": "destination_zones::ct_232",
                                "label": "Zone",
                                "area_slug": "destination_zones",
                            },
                        ],
                    },
                },
            ],
        }
        column_defs = build_rulebook_rules_grid_column_defs(grouped)["columnDefs"]
        column_defs = collapse_rules_column_defs(column_defs)
        flat_columns = flatten_rules_column_defs(
            column_defs, column_mode=COLUMN_MODE_COLLAPSED
        )
        request = RequestFactory().get(
            "/rules/?f_source_zones__ct_232=zone_01"
            "&f_destination_zones__ct_232=zone_06"
        )
        _annotate_rules_columns(
            flat_columns,
            request=request,
            sort_field="index",
            sort_order="asc",
            base_qs_str="",
        )
        by_id = {col["col_id"]: col for col in flat_columns if col["kind"] == "object"}
        self.assertEqual(by_id["source_zones"]["filter_value"], "zone_01")
        self.assertEqual(by_id["destination_zones"]["filter_value"], "zone_06")
