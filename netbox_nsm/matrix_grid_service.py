"""Lazy matrix AG Grid row loading (Community infinite row model)."""

from __future__ import annotations

from netbox_nsm.matrix_grid_payload import build_matrix_ag_grid_row_records
from netbox_nsm.matrix_tab_context import build_matrix_tab_context

__all__ = (
    "MATRIX_GRID_BLOCK_SIZE",
    "fetch_matrix_grid_page",
)

MATRIX_GRID_BLOCK_SIZE = 50


def fetch_matrix_grid_page(
    request,
    rulebook,
    *,
    start_row: int,
    end_row: int,
    view_helpers,
) -> dict:
    start_row = max(0, int(start_row))
    end_row = max(start_row, int(end_row))
    ctx = build_matrix_tab_context(
        request,
        rulebook,
        view_helpers=view_helpers,
        client_axis_filters=True,
        lazy_grid=True,
        src_row_range=(start_row, end_row),
    )
    matrix_rows = ctx.get("matrix_rows") or []
    slice_rows = matrix_rows
    row_data = build_matrix_ag_grid_row_records(
        slice_rows,
        ctx["dst_zones"],
        ctx["matrix_mode"],
        zone_content_type_id=ctx.get("selected_ct_id"),
        request=request,
    )
    return {
        "rowData": row_data,
        "lastRow": len(ctx.get("src_zones") or []),
        "axisLimit": ctx.get("matrix_axis_limit"),
    }
