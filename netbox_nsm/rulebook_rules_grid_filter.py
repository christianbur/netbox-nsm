"""Resolve Rules filter models from JSON and filter_q query text."""

from __future__ import annotations

import json

from netbox_nsm.rulebook_rules_grid_payload import (
    build_ag_grid_filter_model_from_query_text,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    format_filter_query_with_view,
    parse_view_directive,
    serialize_ag_grid_filter_to_nsm_q,
    validate_view_directive_count,
)
from netbox_nsm.query import RulebookContext

__all__ = (
    "extract_grid_filter_params",
    "parse_filter_model_json",
    "resolve_rules_filter_model",
    "parse_view_directive",
    "validate_rules_filter_query",
    "VIEW_DIRECTIVE_MULTIPLE_ERROR",
)


def parse_filter_model_json(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and data else None


def extract_grid_filter_params(request) -> tuple[str | None, str | None]:
    """Return (filter JSON raw, filter_q text) from a GET request."""
    filter_raw = request.GET.get("filter")
    if filter_raw is None:
        filter_raw = request.GET.get("filterModel")
    filter_q = (request.GET.get("filter_q") or request.GET.get("q") or "").strip()
    return filter_raw, filter_q or None


def resolve_rules_filter_model(
    *,
    filter_model_raw: str | None = None,
    filter_q_raw: str | None = None,
    rulebook,
    view_helpers,
    rules_layout: list | None = None,
) -> tuple[dict | None, str | None]:
    """
    Build a filter model for one policy rulebook.

    ``filter_q`` takes precedence over JSON ``filter`` / ``filterModel``.
    """
    if filter_q_raw:
        _view, filter_body, view_err = parse_view_directive(filter_q_raw)
        if view_err:
            return None, view_err
        if rules_layout is None:
            grouped = view_helpers._build_grouped_rules_table_data([], rulebook)
            rules_layout = grouped.get("rules_layout") or []
        context = RulebookContext(rulebook)
        filter_model, err = build_ag_grid_filter_model_from_query_text(
            filter_body, rules_layout, context
        )
        if err:
            return None, err
        return filter_model if filter_model else None, None
    return parse_filter_model_json(filter_model_raw), None


def validate_rules_filter_query(
    raw_q: str,
    rulebook,
    view_helpers,
    *,
    rules_layout: list | None = None,
) -> dict:
    """Validate policy filter_q and return JSON payload fields."""
    raw_q = (raw_q or "").strip()
    view_err = validate_view_directive_count(raw_q)
    if view_err:
        return {"valid": False, "error": view_err}
    view, filter_body, _ = parse_view_directive(raw_q)
    if not raw_q:
        return {"valid": True, "empty": True, "filterModel": {}}

    if rules_layout is None:
        grouped = view_helpers._build_grouped_rules_table_data([], rulebook)
        rules_layout = grouped.get("rules_layout") or []
    context = RulebookContext(rulebook)
    filter_model, err = build_ag_grid_filter_model_from_query_text(
        filter_body, rules_layout, context
    )
    if err:
        return {"valid": False, "error": err}

    column_map = build_filter_column_query_map(rules_layout, context)
    shorthand_names = build_filter_column_shorthand_names(column_map, rules_layout)
    normalized = serialize_ag_grid_filter_to_nsm_q(
        filter_model,
        column_map,
        shorthand_names=shorthand_names,
    )
    if view:
        normalized = format_filter_query_with_view(normalized, view)
    payload = {
        "valid": True,
        "empty": not filter_model and not filter_body,
        "filterModel": filter_model or {},
        "normalized": normalized,
    }
    if view:
        payload["view"] = view
    return payload
