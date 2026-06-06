"""Matrix dropzone validation and client config for the Rules AG Grid tab."""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox_nsm.rule_field_selections import parse_rules_column_key

__all__ = (
    "MATRIX_COL_QUERY_PARAM",
    "MATRIX_COL_SLOT_LABEL",
    "MATRIX_DUPLICATE_MESSAGE",
    "MATRIX_MODE_DIRECTED_LABEL",
    "MATRIX_MODE_DIRECTED_TITLE",
    "MATRIX_MODE_QUERY_PARAM",
    "MATRIX_MODE_UNDIRECTED_LABEL",
    "MATRIX_MODE_UNDIRECTED_TITLE",
    "MATRIX_NOT_ALLOWED_MESSAGE",
    "MATRIX_ROW_SLOT_LABEL",
    "MATRIX_ROW_QUERY_PARAM",
    "MATRIX_TYPE_MISMATCH_MESSAGE",
    "build_matrix_column_meta",
    "build_rules_matrix_grid_config",
    "parse_matrix_column_levels",
    "validate_matrix_column_pair",
)

MATRIX_ROW_QUERY_PARAM = "matrix_row"
MATRIX_COL_QUERY_PARAM = "matrix_col"
MATRIX_NOT_ALLOWED_MESSAGE = _(
    "Only object columns (e.g. zones) can be used in the matrix."
)
MATRIX_TYPE_MISMATCH_MESSAGE = _(
    "Both matrix fields must use the same object type (e.g. both zones)."
)
MATRIX_DUPLICATE_MESSAGE = _("This column is already in the matrix.")
MATRIX_ROW_SLOT_LABEL = _("Row")
MATRIX_COL_SLOT_LABEL = _("Column")
MATRIX_MODE_DIRECTED_LABEL = _("Directed")
MATRIX_MODE_UNDIRECTED_LABEL = _("Undirected")
MATRIX_MODE_DIRECTED_TITLE = _("Directed: → and ← shown separately")
MATRIX_MODE_UNDIRECTED_TITLE = _("Undirected: A↔B merged")
MATRIX_MODE_QUERY_PARAM = "mode"


def _matrix_group_value(column_key: str) -> str:
    return f"col:{column_key}"


def _content_type_id_from_column_key(column_key: str) -> int | None:
    _area, type_key = parse_rules_column_key(column_key)
    if not type_key.startswith("ct_"):
        return None
    try:
        return int(type_key[3:])
    except (TypeError, ValueError):
        return None


def parse_matrix_mode(request) -> str:
    """Return directed or undirected from the matrix mode query param."""
    raw = (request.GET.get(MATRIX_MODE_QUERY_PARAM) or "directed").strip()
    if raw not in ("undirected", "directed"):
        return "directed"
    return raw


def build_matrix_column_meta(
    rules_layout: list,
    field_placements: dict[str, str] | None = None,
) -> dict[str, dict]:
    """Map group-by values (col:area::ct_N) to matrix axis metadata."""
    placements = field_placements or {}
    meta: dict[str, dict] = {}
    for entry in rules_layout or []:
        if entry.get("kind") != "object":
            continue
        area_slug = entry.get("slug") or ""
        area_label = entry.get("label") or area_slug
        placement = placements.get(area_slug, "")
        for col in (entry.get("group") or {}).get("columns") or []:
            col_key = col.get("key") or ""
            type_name = col.get("type_name") or ""
            ct_id = _content_type_id_from_column_key(col_key)
            if ct_id is None:
                continue
            col_label = col.get("label") or col_key
            value = _matrix_group_value(col_key)
            meta[value] = {
                "value": value,
                "columnKey": col_key,
                "areaSlug": area_slug,
                "areaLabel": area_label,
                "columnLabel": col_label,
                "label": f"{area_label} / {col_label}",
                "placement": placement,
                "contentTypeId": ct_id,
                "matrixCompatible": True,
            }
    return meta


def validate_matrix_column_pair(
    row_value: str,
    col_value: str,
    matrix_column_meta: dict[str, dict],
) -> str | None:
    """Return user-facing error message when the pair is invalid, else None."""
    row_value = (row_value or "").strip()
    col_value = (col_value or "").strip()
    if not row_value or not col_value:
        return None
    row_meta = matrix_column_meta.get(row_value)
    col_meta = matrix_column_meta.get(col_value)
    if not row_meta or not col_meta:
        return str(MATRIX_NOT_ALLOWED_MESSAGE)
    if row_meta["contentTypeId"] != col_meta["contentTypeId"]:
        return str(MATRIX_TYPE_MISMATCH_MESSAGE)
    return None


def parse_matrix_column_levels(
    request,
    *,
    matrix_column_meta: dict[str, dict],
) -> tuple[str, str] | None:
    row_raw = (request.GET.get(MATRIX_ROW_QUERY_PARAM) or "").strip()
    col_raw = (request.GET.get(MATRIX_COL_QUERY_PARAM) or "").strip()
    if not row_raw or not col_raw:
        return None
    if validate_matrix_column_pair(row_raw, col_raw, matrix_column_meta):
        return None
    if row_raw not in matrix_column_meta or col_raw not in matrix_column_meta:
        return None
    return row_raw, col_raw


def build_rules_matrix_grid_config(
    request,
    instance,
    rules_layout: list,
    *,
    field_placements: dict[str, str] | None = None,
) -> dict:
    """Client config for embedded matrix mode in the Rules tab."""
    meta = build_matrix_column_meta(rules_layout, field_placements)
    cfg: dict = {
        "matrixColumnMeta": meta,
        "matrixGridUrl": reverse(
            "plugins:netbox_nsm:rulebook_matrix_grid_api",
            args=[instance.pk],
        ),
        "matrixNotAllowedMessage": str(MATRIX_NOT_ALLOWED_MESSAGE),
        "matrixTypeMismatchMessage": str(MATRIX_TYPE_MISMATCH_MESSAGE),
        "matrixDuplicateMessage": str(MATRIX_DUPLICATE_MESSAGE),
        "matrixRowSlotLabel": str(MATRIX_ROW_SLOT_LABEL),
        "matrixColSlotLabel": str(MATRIX_COL_SLOT_LABEL),
        "matrixMode": parse_matrix_mode(request),
        "removeMatrixFieldLabel": str(_("Remove matrix field")),
        "rulebookName": str(getattr(instance, "name", "") or f"rulebook-{instance.pk}"),
    }
    levels = parse_matrix_column_levels(
        request,
        matrix_column_meta=meta,
    )
    if not levels:
        return cfg
    row_value, col_value = levels
    row_meta = meta[row_value]
    cfg["matrixRow"] = row_value
    cfg["matrixCol"] = col_value
    cfg["matrixEnabled"] = True
    cfg["matrixContentTypeId"] = row_meta["contentTypeId"]
    cfg["matrixRowLabel"] = row_meta["label"]
    cfg["matrixColLabel"] = meta[col_value]["label"]
    return cfg
