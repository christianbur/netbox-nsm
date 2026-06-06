"""Serialize zone matrix data for AG Grid (Community)."""

from __future__ import annotations

MULTI_RULE_COLOR = "#6c757d"
MATRIX_AXIS_MAX = 250  # max zones per matrix axis (src rows / dst columns)
MATRIX_CELL_SIZE = 48  # square data cells: dst col width = row height
MATRIX_AXIS_MAX_TEXT_LEN = 50
MATRIX_HEADER_PAD_PX = 10
MATRIX_AXIS_FONT_PX = 16  # 1rem default (--nsm-matrix-axis-header-font)
MATRIX_AXIS_CHAR_STEP_PX = MATRIX_AXIS_FONT_PX  # vertical-rl: ~1em per glyph
MATRIX_AXIS_CHAR_WIDTH_PX = 10  # horizontal labels: ~0.62em average glyph width
MATRIX_AXIS_MAX_PX = 140  # cap header/cell extent; long names ellipsis
# A1 corner cell — square minimum (width = height).
MATRIX_CORNER_MIN_PX = 230
MATRIX_CORNER_FILTER_MIN_WIDTH_PX = MATRIX_CORNER_MIN_PX
MATRIX_CORNER_FILTER_MIN_HEIGHT_PX = MATRIX_CORNER_MIN_PX
MATRIX_CORNER_HEADER_MIN_PX = MATRIX_CORNER_MIN_PX
MATRIX_SOURCE_COL_MIN_PX = MATRIX_CORNER_MIN_PX


def _badge_bg(badge: dict) -> str | None:
    if badge.get("count", 0) == 0:
        return None
    if badge["count"] == 1:
        return badge.get("color") or MULTI_RULE_COLOR
    return MULTI_RULE_COLOR


def _badge_label(badge: dict, *, prefix: str = "") -> str:
    count = badge.get("count", 0)
    if count == 0:
        return "+"
    if count == 1:
        return f"{prefix}{badge.get('label') or '?'}"
    return f"{prefix}{count}"


def _directed_line(
    badge: dict, href: str | None, add_href: str | None, arrow: str
) -> dict:
    if badge.get("count", 0) == 0:
        return {
            "label": arrow,
            "href": add_href or "#",
            "empty": True,
            "title": f"Add rule ({arrow})",
        }
    label = _badge_label(badge, prefix=f"{arrow} ")
    title = label
    if badge["count"] > 1:
        title = f"{badge['count']} rules ({arrow})"
    return {
        "label": label,
        "href": href or add_href or "#",
        "empty": False,
        "title": title,
    }


def serialize_matrix_cell(cell: dict, matrix_mode: str) -> dict:
    """Map classic matrix cell dict to AG Grid cell value (full-cell fill metadata)."""
    meta: dict = {
        "empty": False,
        "isSelf": bool(cell.get("is_self")),
        "href": cell.get("add_href") or "#",
        "label": "+",
        "bg": None,
        "bgSecondary": None,
        "title": "",
    }

    if matrix_mode == "undirected":
        badge = cell.get("combined") or {}
        if badge.get("count", 0) == 0:
            meta["empty"] = True
            meta["title"] = "Add rule"
            return meta
        meta["href"] = cell.get("both_href") or meta["href"]
        meta["bg"] = _badge_bg(badge)
        meta["label"] = _badge_label(badge)
        if badge["count"] > 1:
            meta["title"] = f"{badge['count']} rules"
        else:
            meta["title"] = meta["label"]
        return meta

    fwd = cell.get("fwd") or {}
    rev = cell.get("rev") or {}
    if fwd.get("count", 0) == 0 and rev.get("count", 0) == 0:
        meta["empty"] = True
        meta["title"] = "Add rule"
        return meta

    fwd_bg = _badge_bg(fwd)
    rev_bg = _badge_bg(rev)
    meta["directedLines"] = [
        _directed_line(fwd, cell.get("fwd_href"), cell.get("add_href"), "→"),
        _directed_line(rev, cell.get("rev_href"), cell.get("add_href"), "←"),
    ]

    if fwd.get("count", 0) > 0 and rev.get("count", 0) > 0:
        meta["bg"] = fwd_bg
        meta["bgSecondary"] = rev_bg
        meta["title"] = (
            f"{meta['directedLines'][0]['title']} · {meta['directedLines'][1]['title']}"
        )
        return meta

    if fwd.get("count", 0) > 0:
        meta["bg"] = fwd_bg
        meta["title"] = meta["directedLines"][0]["title"]
        return meta

    meta["bg"] = rev_bg
    meta["title"] = meta["directedLines"][1]["title"]
    return meta


def _zone_url(zone) -> str:
    if hasattr(zone, "get_absolute_url"):
        return zone.get_absolute_url()
    return "#"


def _zone_color(zone) -> str | None:
    """Object color from attribute or custom-object field_data."""
    from netbox_nsm.query.engine import _object_attribute

    raw = _object_attribute(zone, "color")
    if raw in (None, ""):
        return None
    color = str(raw).strip()
    return color or None


def _matrix_axis_header_style(color: str | None) -> dict:
    if not color:
        return {}
    return {"backgroundColor": color, "color": "#fff"}


def matrix_zone_display_label(
    zone,
    zone_content_type_id: int | None,
    display_template_map: dict[int, str] | None = None,
) -> str:
    """Render axis label via TypeConfig display_template when a content type is selected."""
    if zone_content_type_id is None:
        return getattr(zone, "name", str(zone))
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    tmpl_map = display_template_map or get_display_template_map()
    return render_object_display(zone, zone_content_type_id, tmpl_map)


def _matrix_display_name(name: str) -> str:
    """Cap visible axis label length (full name remains in tooltip / filter fields)."""
    text = name or ""
    if len(text) <= MATRIX_AXIS_MAX_TEXT_LEN:
        return text
    return text[: MATRIX_AXIS_MAX_TEXT_LEN - 1] + "…"


def _matrix_longest_word_len(name: str) -> int:
    """Longest whitespace-delimited word after the 50-character cap."""
    capped = (name or "")[:MATRIX_AXIS_MAX_TEXT_LEN]
    words = capped.split()
    if not words:
        return len(capped.strip())
    return max(len(word) for word in words)


def _matrix_max_longest_word_len(labels: list[str]) -> int:
    if not labels:
        return 0
    return max(_matrix_longest_word_len(label) for label in labels)


def _matrix_axis_extent(word_len: int) -> int:
    """Pixel span along an axis for the longest word (+ padding), with floor and cap."""
    if word_len <= 0:
        return MATRIX_CELL_SIZE
    px = word_len * MATRIX_AXIS_CHAR_STEP_PX + MATRIX_HEADER_PAD_PX
    px = max(px, MATRIX_CELL_SIZE)
    return min(px, MATRIX_AXIS_MAX_PX)


def _matrix_row_height() -> int:
    """Fixed data row height (independent of label length)."""
    return MATRIX_CELL_SIZE


def _matrix_dst_col_width() -> int:
    """Dst column width = row height so data cells are square (header height stays separate)."""
    return _matrix_row_height()


def _matrix_header_height(dst_labels: list[str], *, source_col_width: int) -> int:
    """Header row height: dest label extent, but at least source width (square A1)."""
    from_text = _matrix_axis_extent(_matrix_max_longest_word_len(dst_labels))
    return max(from_text, source_col_width)


def _matrix_horizontal_extent(word_len: int) -> int:
    """Pinned source column width from longest horizontal word (+ padding)."""
    if word_len <= 0:
        return MATRIX_CELL_SIZE
    px = word_len * MATRIX_AXIS_CHAR_WIDTH_PX + MATRIX_HEADER_PAD_PX
    px = max(px, MATRIX_CELL_SIZE)
    return min(px, MATRIX_AXIS_MAX_PX)


def _matrix_source_col_width(src_labels: list[str]) -> int:
    """Pinned source column width from longest source zone word (horizontal labels)."""
    from_text = _matrix_horizontal_extent(_matrix_max_longest_word_len(src_labels))
    return max(from_text, MATRIX_SOURCE_COL_MIN_PX)


def build_matrix_ag_grid_row_records(
    matrix_rows: list,
    dst_zones: list,
    matrix_mode: str,
    *,
    zone_content_type_id: int | None = None,
    display_template_map: dict[int, str] | None = None,
    request=None,
) -> list[dict]:
    """Serialize matrix rows only (sparse cells) for lazy API loading."""
    from netbox_nsm.display_utils import get_display_template_map
    from netbox_nsm.branch_urls import with_branch_query

    tmpl_map = display_template_map
    if tmpl_map is None and zone_content_type_id is not None:
        tmpl_map = get_display_template_map()

    def zone_label(zone) -> str:
        return matrix_zone_display_label(zone, zone_content_type_id, tmpl_map)

    row_data = []
    for row in matrix_rows:
        src = row["source_zone"]
        full_src = zone_label(src)
        cells = row.get("cells") or []
        record: dict = {
            "_sourceLabel": full_src,
            "_sourceDisplayLabel": _matrix_display_name(full_src),
            "_sourceUrl": with_branch_query(_zone_url(src), request),
            "_sourceColor": _zone_color(src),
        }
        for dst, cell in zip(dst_zones, cells):
            serialized = serialize_matrix_cell(cell, matrix_mode)
            if serialized.get("empty"):
                continue
            record[f"dst_{dst.pk}"] = serialized
        row_data.append(record)
    return row_data


def build_matrix_ag_grid_scaffold(
    matrix_rows: list,
    dst_zones: list,
    matrix_mode: str,
    *,
    zone_content_type_id: int | None = None,
    display_template_map: dict[int, str] | None = None,
    request=None,
    matrix_axis_limit: dict | None = None,
) -> dict:
    """Column defs + grid meta without row data (lazy matrix load)."""
    from netbox_nsm.matrix_tab_context import cap_matrix_axis_zones

    dst_zones, _, _ = cap_matrix_axis_zones(dst_zones)
    payload = build_matrix_ag_grid_payload(
        matrix_rows,
        dst_zones,
        matrix_mode,
        zone_content_type_id=zone_content_type_id,
        display_template_map=display_template_map,
        request=request,
        matrix_axis_limit=matrix_axis_limit,
    )
    payload["rowData"] = []
    return payload


def build_matrix_ag_grid_payload(
    matrix_rows: list,
    dst_zones: list,
    matrix_mode: str,
    *,
    zone_content_type_id: int | None = None,
    display_template_map: dict[int, str] | None = None,
    request=None,
    matrix_axis_limit: dict | None = None,
) -> dict:
    """Build columnDefs + rowData for the matrix AG Grid."""
    from netbox_nsm.display_utils import get_display_template_map
    from netbox_nsm.branch_urls import with_branch_query
    from netbox_nsm.matrix_tab_context import cap_matrix_axis_zones

    dst_zones, _, _ = cap_matrix_axis_zones(dst_zones)

    tmpl_map = display_template_map
    if tmpl_map is None and zone_content_type_id is not None:
        tmpl_map = get_display_template_map()

    def zone_label(zone) -> str:
        return matrix_zone_display_label(zone, zone_content_type_id, tmpl_map)

    dst_labels = [zone_label(z) for z in dst_zones]
    src_labels = [zone_label(row["source_zone"]) for row in matrix_rows]
    dst_display_labels = [_matrix_display_name(label) for label in dst_labels]
    src_display_labels = [_matrix_display_name(label) for label in src_labels]
    dst_col_width = _matrix_dst_col_width()
    row_height = _matrix_row_height()
    source_col_width = _matrix_source_col_width(src_display_labels)
    header_height = _matrix_header_height(
        dst_display_labels,
        source_col_width=source_col_width,
    )
    column_defs: list[dict] = [
        {
            "colId": "_source",
            "field": "_sourceDisplayLabel",
            "headerName": "",
            "pinned": "left",
            "lockPinned": True,
            "lockPosition": "left",
            "suppressMovable": True,
            "width": source_col_width,
            "minWidth": source_col_width,
            "maxWidth": source_col_width,
            "resizable": False,
            "cellRenderer": "matrixRowLabelCell",
            "headerComponent": "matrixCornerHeader",
            "filter": False,
            "sortable": False,
            "suppressHeaderMenuButton": True,
            "headerClass": "nsm-matrix-corner-header",
        }
    ]

    for dst, full_label in zip(dst_zones, dst_labels):
        field = f"dst_{dst.pk}"
        display_name = _matrix_display_name(full_label)
        zone_color = _zone_color(dst)
        dst_col: dict = {
            "colId": field,
            "field": field,
            "headerName": display_name,
            "headerTooltip": full_label,
            "headerClass": "nsm-matrix-col-header-vertical",
            "headerComponent": "matrixDstHeader",
            "cellRenderer": "matrixCell",
            "minWidth": dst_col_width,
            "width": dst_col_width,
            "maxWidth": dst_col_width,
            "resizable": False,
            "suppressMovable": True,
            "lockPosition": True,
            "sortable": False,
            "filter": False,
            "suppressHeaderMenuButton": True,
        }
        header_style = _matrix_axis_header_style(zone_color)
        if header_style:
            dst_col["headerStyle"] = header_style
            dst_col["headerBackgroundColor"] = zone_color
        column_defs.append(dst_col)

    row_data = []
    for row in matrix_rows:
        src = row["source_zone"]
        full_src = zone_label(src)
        cells = row.get("cells") or []
        record: dict = {
            "_sourceLabel": full_src,
            "_sourceDisplayLabel": _matrix_display_name(full_src),
            "_sourceUrl": with_branch_query(_zone_url(src), request),
            "_sourceColor": _zone_color(src),
        }
        for dst, cell in zip(dst_zones, cells):
            record[f"dst_{dst.pk}"] = serialize_matrix_cell(cell, matrix_mode)
        row_data.append(record)

    grid_meta = {
        "headerHeight": header_height,
        "rowHeight": row_height,
        "dstColWidth": dst_col_width,
        "sourceColWidth": source_col_width,
        "headerPadPx": MATRIX_HEADER_PAD_PX,
        "axisCharStepPx": MATRIX_AXIS_CHAR_STEP_PX,
        "axisCharWidthPx": MATRIX_AXIS_CHAR_WIDTH_PX,
        "axisMaxPx": MATRIX_AXIS_MAX_PX,
        "cornerHeaderMinPx": MATRIX_CORNER_HEADER_MIN_PX,
        "cornerFilterMinWidthPx": MATRIX_CORNER_FILTER_MIN_WIDTH_PX,
        "cornerFilterMinHeightPx": MATRIX_CORNER_FILTER_MIN_HEIGHT_PX,
        "maxTextLen": MATRIX_AXIS_MAX_TEXT_LEN,
        "cellSizeMin": MATRIX_CELL_SIZE,
        "axisMax": MATRIX_AXIS_MAX,
    }
    if matrix_axis_limit:
        grid_meta["axisLimit"] = matrix_axis_limit

    return {
        "columnDefs": column_defs,
        "rowData": row_data,
        "matrixMode": matrix_mode,
        "gridMeta": grid_meta,
    }
