"""Matrix axis cap (250 zones per src/dst axis)."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from netbox_nsm.matrix_grid_payload import (
    MATRIX_AXIS_MAX,
    build_matrix_ag_grid_payload,
    build_matrix_ag_grid_scaffold,
)
from netbox_nsm.matrix_tab_context import (
    build_matrix_axis_limit_info,
    cap_matrix_axis_zones,
)


def _zones(count: int, *, prefix: str = "zone") -> list:
    return [SimpleNamespace(pk=i, name=f"{prefix}-{i}") for i in range(1, count + 1)]


class MatrixAxisLimitTests(SimpleTestCase):
    def test_cap_matrix_axis_zones_under_limit(self):
        zones = _zones(100)
        capped, truncated, total = cap_matrix_axis_zones(zones)
        self.assertEqual(len(capped), 100)
        self.assertFalse(truncated)
        self.assertEqual(total, 100)

    def test_cap_matrix_axis_zones_at_limit(self):
        zones = _zones(MATRIX_AXIS_MAX)
        capped, truncated, total = cap_matrix_axis_zones(zones)
        self.assertEqual(len(capped), MATRIX_AXIS_MAX)
        self.assertFalse(truncated)
        self.assertEqual(total, MATRIX_AXIS_MAX)

    def test_cap_matrix_axis_zones_over_limit(self):
        zones = _zones(MATRIX_AXIS_MAX + 50)
        capped, truncated, total = cap_matrix_axis_zones(zones)
        self.assertEqual(len(capped), MATRIX_AXIS_MAX)
        self.assertTrue(truncated)
        self.assertEqual(total, MATRIX_AXIS_MAX + 50)
        self.assertEqual(capped[0].pk, 1)
        self.assertEqual(capped[-1].pk, MATRIX_AXIS_MAX)

    def test_build_matrix_axis_limit_info_none_when_not_truncated(self):
        self.assertIsNone(
            build_matrix_axis_limit_info(
                src_total=10,
                dst_total=20,
                src_truncated=False,
                dst_truncated=False,
            )
        )

    def test_build_matrix_axis_limit_info_when_truncated(self):
        info = build_matrix_axis_limit_info(
            src_total=300,
            dst_total=400,
            src_truncated=True,
            dst_truncated=True,
        )
        self.assertEqual(info["limit"], MATRIX_AXIS_MAX)
        self.assertEqual(info["src_total"], 300)
        self.assertEqual(info["dst_total"], 400)
        self.assertTrue(info["src_truncated"])
        self.assertTrue(info["dst_truncated"])

    def test_scaffold_caps_dst_columns(self):
        dst_zones = _zones(MATRIX_AXIS_MAX + 10, prefix="dst")
        payload = build_matrix_ag_grid_scaffold([], dst_zones, "undirected")
        dst_cols = [c for c in payload["columnDefs"] if c["colId"].startswith("dst_")]
        self.assertEqual(len(dst_cols), MATRIX_AXIS_MAX)
        self.assertEqual(payload["gridMeta"]["axisMax"], MATRIX_AXIS_MAX)

    def test_payload_includes_axis_limit_in_grid_meta(self):
        dst_zones = _zones(MATRIX_AXIS_MAX + 5, prefix="dst")
        axis_limit = build_matrix_axis_limit_info(
            src_total=260,
            dst_total=len(dst_zones),
            src_truncated=True,
            dst_truncated=True,
        )
        src = SimpleNamespace(pk=1, name="src-1")
        rows = [{"source_zone": src, "cells": [_empty_cell() for _ in dst_zones]}]
        payload = build_matrix_ag_grid_payload(
            rows,
            dst_zones,
            "undirected",
            matrix_axis_limit=axis_limit,
        )
        self.assertEqual(payload["gridMeta"]["axisLimit"], axis_limit)
        dst_cols = [c for c in payload["columnDefs"] if c["colId"].startswith("dst_")]
        self.assertEqual(len(dst_cols), MATRIX_AXIS_MAX)


def _empty_cell():
    return {
        "fwd": {"count": 0, "color": None, "label": None},
        "rev": {"count": 0, "color": None, "label": None},
        "combined": {"count": 0, "color": None, "label": None},
        "fwd_href": "#",
        "rev_href": "#",
        "both_href": "#",
        "add_href": "#",
        "is_self": False,
    }
