"""AG Grid payload for Matrix tab."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from netbox_nsm.matrix_grid_payload import (
    MATRIX_AXIS_CHAR_STEP_PX,
    MATRIX_AXIS_CHAR_WIDTH_PX,
    MATRIX_AXIS_MAX_PX,
    MATRIX_AXIS_MAX_TEXT_LEN,
    MATRIX_CELL_SIZE,
    MATRIX_CORNER_HEADER_MIN_PX,
    MATRIX_CORNER_FILTER_MIN_HEIGHT_PX,
    MATRIX_CORNER_FILTER_MIN_WIDTH_PX,
    MATRIX_HEADER_PAD_PX,
    MATRIX_SOURCE_COL_MIN_PX,
    _matrix_axis_extent,
    _matrix_display_name,
    _matrix_header_height,
    _matrix_longest_word_len,
    _matrix_source_col_width,
    build_matrix_ag_grid_payload,
    serialize_matrix_cell,
)


def _cell(
    *,
    fwd_count=0,
    rev_count=0,
    combined_count=0,
    color="#336699",
    label="Permit",
    is_self=False,
):
    def badge(count):
        if count == 0:
            return {"count": 0, "color": None, "label": None}
        if count == 1:
            return {"count": 1, "color": color, "label": label}
        return {"count": count, "color": None, "label": None}

    return {
        "fwd": badge(fwd_count),
        "rev": badge(rev_count),
        "combined": badge(combined_count or max(fwd_count, rev_count)),
        "fwd_href": "/policy/?fwd=1",
        "rev_href": "/policy/?rev=1",
        "both_href": "/policy/?both=1",
        "add_href": "/rules/add/",
        "is_self": is_self,
    }


class MatrixGridPayloadTests(SimpleTestCase):
    def test_undirected_single_rule_fills_cell(self):
        meta = serialize_matrix_cell(
            _cell(combined_count=1, color="#ff0000", label="Deny"),
            "undirected",
        )
        self.assertFalse(meta["empty"])
        self.assertEqual(meta["bg"], "#ff0000")
        self.assertEqual(meta["label"], "Deny")
        self.assertIsNone(meta["bgSecondary"])

    def test_directed_both_directions_split_fill(self):
        meta = serialize_matrix_cell(
            _cell(fwd_count=1, rev_count=1, color="#00ff00", label="Allow"),
            "directed",
        )
        self.assertEqual(meta["bg"], "#00ff00")
        self.assertEqual(meta["bgSecondary"], "#00ff00")
        self.assertEqual(len(meta["directedLines"]), 2)
        self.assertEqual(meta["directedLines"][0]["label"], "→ Allow")
        self.assertEqual(meta["directedLines"][1]["label"], "← Allow")
        self.assertNotIn("/", meta["directedLines"][0]["label"])

    def test_empty_cell(self):
        meta = serialize_matrix_cell(_cell(), "undirected")
        self.assertTrue(meta["empty"])
        self.assertIsNone(meta["bg"])

    def test_build_payload_columns_and_rows(self):
        dst_a = SimpleNamespace(pk=10, name="DMZ")
        dst_b = SimpleNamespace(pk=20, name="LAN")
        src = SimpleNamespace(pk=1, name="Internet")
        rows = [
            {
                "source_zone": src,
                "cells": [
                    _cell(combined_count=1),
                    _cell(),
                ],
            }
        ]
        payload = build_matrix_ag_grid_payload(rows, [dst_a, dst_b], "undirected")
        self.assertEqual(len(payload["columnDefs"]), 3)
        self.assertEqual(payload["rowData"][0]["_sourceLabel"], "Internet")
        self.assertEqual(payload["rowData"][0]["_sourceDisplayLabel"], "Internet")
        self.assertEqual(payload["rowData"][0]["dst_10"]["bg"], "#336699")
        self.assertTrue(payload["rowData"][0]["dst_20"]["empty"])
        self.assertEqual(payload["gridMeta"]["headerHeight"], MATRIX_CORNER_HEADER_MIN_PX)
        self.assertEqual(
            payload["gridMeta"]["headerHeight"],
            payload["gridMeta"]["sourceColWidth"],
        )
        self.assertEqual(
            payload["gridMeta"]["cornerFilterMinWidthPx"],
            MATRIX_CORNER_FILTER_MIN_WIDTH_PX,
        )
        self.assertEqual(
            payload["gridMeta"]["cornerFilterMinHeightPx"],
            MATRIX_CORNER_FILTER_MIN_HEIGHT_PX,
        )
        self.assertEqual(payload["gridMeta"]["rowHeight"], MATRIX_CELL_SIZE)
        self.assertEqual(payload["gridMeta"]["dstColWidth"], MATRIX_CELL_SIZE)
        self.assertEqual(payload["gridMeta"]["headerPadPx"], MATRIX_HEADER_PAD_PX)
        self.assertEqual(payload["gridMeta"]["maxTextLen"], MATRIX_AXIS_MAX_TEXT_LEN)
        dst_col = next(c for c in payload["columnDefs"] if c["colId"] == "dst_10")
        self.assertEqual(dst_col["width"], MATRIX_CELL_SIZE)
        self.assertEqual(dst_col["maxWidth"], MATRIX_CELL_SIZE)
        self.assertFalse(dst_col["resizable"])
        src_col = payload["columnDefs"][0]
        self.assertEqual(src_col["width"], MATRIX_SOURCE_COL_MIN_PX)

    def test_header_height_from_longest_word_plus_padding(self):
        source_w = _matrix_source_col_width(["Production"])
        from_dest = min(
            _matrix_axis_extent(len("Production")),
            MATRIX_AXIS_MAX_PX,
        )
        expected = max(from_dest, source_w)
        self.assertEqual(
            _matrix_header_height(["Production"], source_col_width=source_w),
            expected,
        )

    def test_header_height_corner_minimum_for_short_names(self):
        self.assertEqual(
            _matrix_header_height(["X"], source_col_width=MATRIX_CORNER_HEADER_MIN_PX),
            MATRIX_CORNER_HEADER_MIN_PX,
        )

    def test_longest_word_not_full_phrase(self):
        self.assertEqual(_matrix_longest_word_len("Corp DMZ Zone"), len("Corp"))
        self.assertEqual(
            _matrix_longest_word_len("a" * 60),
            MATRIX_AXIS_MAX_TEXT_LEN,
        )

    def test_display_name_truncated_at_fifty_chars(self):
        long_name = "x" * 60
        display = _matrix_display_name(long_name)
        self.assertEqual(len(display), MATRIX_AXIS_MAX_TEXT_LEN)
        self.assertTrue(display.endswith("…"))

    def test_dst_col_width_matches_row_height_for_square_cells(self):
        dst = SimpleNamespace(pk=1, name="VeryLongDestinationName")
        rows = [{"source_zone": SimpleNamespace(pk=2, name="Src"), "cells": [_cell()]}]
        payload = build_matrix_ag_grid_payload(rows, [dst], "undirected")
        self.assertEqual(payload["gridMeta"]["dstColWidth"], MATRIX_CELL_SIZE)
        self.assertEqual(payload["gridMeta"]["rowHeight"], MATRIX_CELL_SIZE)
        self.assertGreater(payload["gridMeta"]["headerHeight"], MATRIX_CELL_SIZE)
        dst_col = next(c for c in payload["columnDefs"] if c["colId"] == "dst_1")
        self.assertEqual(dst_col["width"], MATRIX_CELL_SIZE)

    def test_short_source_label_uses_corner_minimum_width(self):
        self.assertEqual(
            _matrix_source_col_width(["dev-1"]),
            MATRIX_SOURCE_COL_MIN_PX,
        )

    def test_short_label_header_uses_corner_minimum(self):
        """dev-1 style labels: header at least source width (square A1)."""
        source_w = MATRIX_SOURCE_COL_MIN_PX
        self.assertEqual(
            _matrix_header_height(["dev-1"], source_col_width=source_w),
            source_w,
        )
        self.assertEqual(
            _matrix_axis_extent(len("dev-1")),
            5 * MATRIX_AXIS_CHAR_STEP_PX + MATRIX_HEADER_PAD_PX,
        )

    def test_zone_color_on_axis_headers(self):
        zone = SimpleNamespace(pk=1, name="dmz", color="#ff5500")
        rows = [{"source_zone": zone, "cells": [_cell()]}]
        payload = build_matrix_ag_grid_payload(rows, [zone], "undirected")
        dst_col = next(c for c in payload["columnDefs"] if c["colId"] == "dst_1")
        self.assertEqual(dst_col["headerStyle"]["backgroundColor"], "#ff5500")
        self.assertEqual(dst_col["headerBackgroundColor"], "#ff5500")
        self.assertEqual(payload["rowData"][0]["_sourceColor"], "#ff5500")

    def test_display_template_applied_to_axis_labels(self):
        zone = SimpleNamespace(pk=1, name="dmz", label_type="prod")
        tmpl_map = {99: "{label_type!u}:{name}"}
        rows = [{"source_zone": zone, "cells": [_cell()]}]
        payload = build_matrix_ag_grid_payload(
            rows,
            [zone],
            "undirected",
            zone_content_type_id=99,
            display_template_map=tmpl_map,
        )
        self.assertEqual(payload["rowData"][0]["_sourceLabel"], "PROD:dmz")
        self.assertEqual(payload["rowData"][0]["_sourceDisplayLabel"], "PROD:dmz")
        dst_col = next(c for c in payload["columnDefs"] if c["colId"] == "dst_1")
        self.assertEqual(dst_col["headerTooltip"], "PROD:dmz")
        self.assertEqual(dst_col["headerName"], "PROD:dmz")
