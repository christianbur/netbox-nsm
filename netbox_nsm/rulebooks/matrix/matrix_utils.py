"""Shared zone matrix helpers (HTML matrix tab)."""

from __future__ import annotations

MATRIX_AXIS_MAX = 400
MATRIX_AXIS_LABEL_MAX_CHARS = 100
MATRIX_CELL_WIDTH_PX = 48
MATRIX_CELL_HEIGHT_PX = 48
MATRIX_CELL_WIDTH_DENSE_PX = 38
MATRIX_CELL_HEIGHT_DENSE_PX = 38
MATRIX_CORNER_WIDTH_PX = 104
MATRIX_VIEWPORT_DEFAULT_ROWS = 50
MATRIX_VIEWPORT_DEFAULT_COLS = 50
MATRIX_VIEWPORT_ROW_BUFFER = 5
MATRIX_VIEWPORT_COL_BUFFER = 4


def dedupe_matrix_object_types(entries: list[dict]) -> list[dict]:
    """Keep one matrix object-type option per visible label (case-insensitive)."""
    seen_labels: set[str] = set()
    deduped: list[dict] = []
    for entry in entries:
        label = str(entry.get("label") or "").strip()
        key = label.casefold()
        if not key or key in seen_labels:
            continue
        seen_labels.add(key)
        deduped.append({"ct_id": entry["ct_id"], "label": label})
    return deduped


def _default_matrix_object_type_id(available_types: list[dict]) -> int | None:
    """Pick a sensible default object type for the zone matrix tab."""
    if not available_types:
        return None
    for entry in available_types:
        if str(entry.get("label") or "").strip().casefold() == "zone":
            return entry["ct_id"]
    return available_types[0]["ct_id"]


def resolve_matrix_object_type_selection(
    selected_ct_id: int | None,
    *,
    raw_types: list[dict],
    available_types: list[dict],
) -> int | None:
    """Map a requested content type to the deduped matrix object-type option."""
    if not available_types:
        return None
    valid_deduped = {entry["ct_id"] for entry in available_types}
    if selected_ct_id in valid_deduped:
        return selected_ct_id
    if selected_ct_id is None:
        return _default_matrix_object_type_id(available_types)
    selected_label = None
    for entry in raw_types:
        if entry["ct_id"] == selected_ct_id:
            selected_label = str(entry.get("label") or "").casefold()
            break
    if selected_label:
        for entry in available_types:
            if str(entry.get("label") or "").casefold() == selected_label:
                return entry["ct_id"]
    return _default_matrix_object_type_id(available_types)


def matrix_axis_display_label(
    label: str, *, max_chars: int = MATRIX_AXIS_LABEL_MAX_CHARS
) -> str:
    """Return axis label text for matrix cells (hard cap, no ellipsis suffix)."""
    text = str(label or "")
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def matrix_zone_display_label(
    zone,
    zone_content_type_id: int | None,
    display_template_map: dict[int, str] | None = None,
) -> str:
    """Render axis label via TypeConfig display_template when a content type is selected."""
    if zone_content_type_id is None:
        return getattr(zone, "name", str(zone))
    from netbox_nsm.core.display_utils import get_display_template_map, render_object_display

    tmpl_map = display_template_map or get_display_template_map()
    return render_object_display(zone, zone_content_type_id, tmpl_map)
