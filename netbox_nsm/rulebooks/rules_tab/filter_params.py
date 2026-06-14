from __future__ import annotations

from netbox_nsm.rulebooks.grid.filter_model import filter_spec_to_column_quick_value
from netbox_nsm.rulebooks.grid.rows import build_column_quick_filter_spec
from netbox_nsm.rulebooks.rules_tab.constants import RULES_FILTER_PREFIX

def _rules_query_field(col: dict) -> str | None:
    if col.get("kind") == "actions":
        return None
    if col.get("kind") == "system":
        return "enabled" if col.get("slug") == "status" else col.get("slug")
    return col.get("key")


def _rules_param_token(field: str) -> str:
    return field.replace("::", "__")


def _rules_filter_param_name(col: dict) -> str:
    if col.get("slug") == "status":
        return f"{RULES_FILTER_PREFIX}status"
    field = _rules_query_field(col)
    return f"{RULES_FILTER_PREFIX}{_rules_param_token(field or '')}"


def _rules_column_filter_param_names(col: dict) -> list[str]:
    """URL query keys that apply a quick-search value to this column."""
    primary = _rules_filter_param_name(col)
    names: list[str] = [primary] if primary else []
    for merged_key in col.get("merged_keys") or []:
        alt = f"{RULES_FILTER_PREFIX}{_rules_param_token(merged_key)}"
        if alt not in names:
            names.append(alt)
    field = _rules_query_field(col)
    area_slug = col.get("area_slug") or (
        (field or "").split("::", 1)[0] if field else ""
    )
    if area_slug and field and field != area_slug:
        collapsed = f"{RULES_FILTER_PREFIX}{_rules_param_token(area_slug)}"
        if collapsed not in names:
            names.append(collapsed)
    return names


def _rules_filter_raw_from_request(request, col: dict) -> str:
    """Read the first matching per-column filter value from the query string."""
    for param in _rules_column_filter_param_names(col):
        raw = (request.GET.get(param) or "").strip()
        if raw:
            return raw
    return ""

def _sync_column_filter_values_from_model(
    flat_columns: list,
    filter_model: dict,
) -> None:
    """Mirror resolved filter_q values into per-column quick-search inputs."""
    for col in flat_columns:
        field = _rules_query_field(col)
        if not field:
            continue
        spec = filter_model.get(field)
        if not spec:
            continue
        col["filter_value"] = filter_spec_to_column_quick_value(spec)

def parse_rules_filter_model(request, flat_columns: list) -> dict:
    model: dict = {}
    for col in flat_columns:
        field = _rules_query_field(col)
        if not field:
            continue
        raw = _rules_filter_raw_from_request(request, col)
        if raw:
            model[field] = build_column_quick_filter_spec(raw)
    return model
