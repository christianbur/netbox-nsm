"""Resolve AG Grid filter models from JSON and filter_q query text."""

from __future__ import annotations

import json

from netbox_nsm.models import Rulebook
from netbox_nsm.policy_grid_payload import (
    ALL_RULES_FILTER_QUERY_FORMAT,
    SCOPED_FILTER_FORMAT_ERROR,
    SCOPED_FILTER_QUERY_FORMAT,
    build_ag_grid_filter_model_from_column_map,
    build_ag_grid_filter_model_from_query_text,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    parse_scoped_grid_filter_query,
    serialize_ag_grid_filter_to_nsm_q,
)
from netbox_nsm.query import RulebookContext

__all__ = (
    "ALL_RULES_FILTER_QUERY_FORMAT",
    "SCOPED_FILTER_QUERY_FORMAT",
    "extract_all_rules_filter_params",
    "extract_grid_filter_params",
    "parse_filter_model_json",
    "resolve_all_rules_filter_model",
    "resolve_policy_filter_model",
    "validate_all_rules_filter_query",
    "validate_policy_filter_query",
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


def extract_all_rules_filter_params(
    request,
) -> tuple[Rulebook | None, str | None, str | None]:
    """
    Return (scoped_rulebook, unscoped filter_q body, error).

    Priority: rulebook_id > rulebook (name) > scoped prefix in filter_q.
    """
    from netbox_nsm.all_rules_grid_service import (
        resolve_policy_rulebook_by_id,
        resolve_policy_rulebook_scope,
    )

    filter_q = (request.GET.get("filter_q") or request.GET.get("q") or "").strip()
    scoped_rulebook: Rulebook | None = None

    rb_id_raw = (request.GET.get("rulebook_id") or "").strip()
    if rb_id_raw:
        scoped_rulebook, err = resolve_policy_rulebook_by_id(rb_id_raw)
        if err:
            return None, filter_q or None, err
    elif (request.GET.get("rulebook") or "").strip():
        rb_name = request.GET.get("rulebook", "").strip()
        scoped_rulebook, err = resolve_policy_rulebook_scope(rb_name)
        if err:
            return None, filter_q or None, err

    if scoped_rulebook is not None:
        if filter_q:
            _rb_name, body, scope_err = parse_scoped_grid_filter_query(filter_q)
            if scope_err:
                return scoped_rulebook, None, scope_err
            return scoped_rulebook, body or None, None
        return scoped_rulebook, None, None

    if not filter_q:
        return None, None, None

    rb_name, body, scope_err = parse_scoped_grid_filter_query(filter_q)
    if scope_err:
        return None, None, scope_err
    if rb_name:
        scoped_rulebook, err = resolve_policy_rulebook_scope(rb_name)
        if err:
            return None, None, err
        return scoped_rulebook, body or None, None
    return None, body or None, None


def resolve_policy_filter_model(
    *,
    filter_model_raw: str | None = None,
    filter_q_raw: str | None = None,
    rulebook,
    view_helpers,
    policy_layout: list | None = None,
) -> tuple[dict | None, str | None]:
    """
    Build an AG Grid filter model for one policy rulebook.

    ``filter_q`` takes precedence over JSON ``filter`` / ``filterModel``.
    """
    if filter_q_raw:
        if policy_layout is None:
            grouped = view_helpers._build_grouped_policy_table_data([], rulebook)
            policy_layout = grouped.get("policy_layout") or []
        context = RulebookContext(rulebook)
        filter_model, err = build_ag_grid_filter_model_from_query_text(
            filter_q_raw, policy_layout, context
        )
        if err:
            return None, err
        return filter_model if filter_model else None, None
    return parse_filter_model_json(filter_model_raw), None


def validate_policy_filter_query(
    raw_q: str,
    rulebook,
    view_helpers,
    *,
    policy_layout: list | None = None,
) -> dict:
    """Validate policy filter_q and return JSON payload fields."""
    raw_q = (raw_q or "").strip()
    if not raw_q:
        return {"valid": True, "empty": True, "filterModel": {}}

    if policy_layout is None:
        grouped = view_helpers._build_grouped_policy_table_data([], rulebook)
        policy_layout = grouped.get("policy_layout") or []
    context = RulebookContext(rulebook)
    filter_model, err = build_ag_grid_filter_model_from_query_text(
        raw_q, policy_layout, context
    )
    if err:
        return {"valid": False, "error": err}

    column_map = build_filter_column_query_map(policy_layout, context)
    shorthand_names = build_filter_column_shorthand_names(column_map, policy_layout)
    normalized = serialize_ag_grid_filter_to_nsm_q(
        filter_model,
        column_map,
        shorthand_names=shorthand_names,
    )
    return {
        "valid": True,
        "empty": not filter_model,
        "filterModel": filter_model or {},
        "normalized": normalized,
    }


def _resolve_all_rules_filter_body(
    *,
    filter_q_body: str | None,
    scoped_rulebook: Rulebook | None,
    view_helpers,
) -> tuple[dict | None, Rulebook | None, str | None]:
    from netbox_nsm.all_rules_grid_service import (
        build_all_rules_filter_extra_aliases,
        build_all_rules_filter_maps,
    )

    body = (filter_q_body or "").strip()
    if scoped_rulebook is not None:
        grouped = view_helpers._build_grouped_policy_table_data([], scoped_rulebook)
        policy_layout = grouped.get("policy_layout") or []
        context = RulebookContext(scoped_rulebook)
        if not body:
            return None, scoped_rulebook, None
        filter_model, err = build_ag_grid_filter_model_from_query_text(
            body, policy_layout, context
        )
        if err:
            return None, scoped_rulebook, err
        return filter_model if filter_model else None, scoped_rulebook, None

    if not body:
        return None, None, None

    column_map, policy_layout = build_all_rules_filter_maps(view_helpers)
    extra_aliases = build_all_rules_filter_extra_aliases(column_map)
    filter_model, err = build_ag_grid_filter_model_from_column_map(
        body,
        column_map,
        policy_layout,
        extra_aliases=extra_aliases,
    )
    if err:
        return None, None, err
    return filter_model if filter_model else None, None, None


def _build_all_rules_validate_payload(
    *,
    scoped_rulebook: Rulebook | None,
    filter_q_body: str | None,
    filter_model: dict | None,
    view_helpers,
) -> dict:
    from netbox_nsm.all_rules_grid_service import (
        ALL_RULES_FILTER_QUERY_COLUMN_ORDER,
        build_all_rules_filter_maps,
        build_all_rules_filter_shorthand_names,
    )

    body = (filter_q_body or "").strip()
    if scoped_rulebook is not None:
        grouped = view_helpers._build_grouped_policy_table_data([], scoped_rulebook)
        policy_layout = grouped.get("policy_layout") or []
        context = RulebookContext(scoped_rulebook)
        column_map = build_filter_column_query_map(policy_layout, context)
        shorthand_names = build_filter_column_shorthand_names(column_map, policy_layout)
        column_order = None
    else:
        column_map, policy_layout = build_all_rules_filter_maps(view_helpers)
        shorthand_names = build_all_rules_filter_shorthand_names(
            column_map, policy_layout
        )
        column_order = list(ALL_RULES_FILTER_QUERY_COLUMN_ORDER)

    normalized_body = serialize_ag_grid_filter_to_nsm_q(
        filter_model,
        column_map,
        shorthand_names=shorthand_names,
        column_order=column_order,
    )
    payload = {
        "valid": True,
        "empty": not filter_model and not body,
        "filterModel": filter_model or {},
        "filterQ": normalized_body,
        "normalized": normalized_body,
    }
    if scoped_rulebook is not None:
        payload["rulebook"] = scoped_rulebook.name
        payload["rulebookId"] = scoped_rulebook.pk
    return payload


def resolve_all_rules_filter_model(
    *,
    filter_model_raw: str | None = None,
    filter_q_raw: str | None = None,
    scoped_rulebook: Rulebook | None = None,
    view_helpers,
    request=None,
) -> tuple[dict | None, Rulebook | None, str | None]:
    """Build an AG Grid filter model for the global all-rules grid."""
    if request is not None:
        scoped_rulebook, filter_q_body, scope_err = extract_all_rules_filter_params(
            request
        )
        if scope_err:
            return None, scoped_rulebook, scope_err
        if scoped_rulebook is not None or filter_q_body:
            return _resolve_all_rules_filter_body(
                filter_q_body=filter_q_body,
                scoped_rulebook=scoped_rulebook,
                view_helpers=view_helpers,
            )

    if filter_q_raw:
        scoped_rulebook, filter_q_body, scope_err = extract_all_rules_filter_params(
            _params_from_filter_q(filter_q_raw)
        )
        if scope_err:
            return None, scoped_rulebook, scope_err
        return _resolve_all_rules_filter_body(
            filter_q_body=filter_q_body,
            scoped_rulebook=scoped_rulebook,
            view_helpers=view_helpers,
        )
    return parse_filter_model_json(filter_model_raw), scoped_rulebook, None


def _params_from_filter_q(filter_q_raw: str):
    """Minimal request-like object for deprecated scoped-only filter_q."""

    class _Params:
        def __init__(self, filter_q: str):
            self._data = {"filter_q": filter_q}

        def get(self, key, default=""):
            return self._data.get(key, default)

    return _Params(filter_q_raw)


def validate_all_rules_filter_query(
    *,
    filter_q: str | None = None,
    rulebook_id: str | None = None,
    rulebook_name: str | None = None,
    view_helpers,
    request=None,
) -> dict:
    """Validate all-rules filter params and return JSON payload fields."""
    if request is not None:
        scoped_rulebook, filter_q_body, scope_err = extract_all_rules_filter_params(
            request
        )
    else:
        scoped_rulebook, filter_q_body, scope_err = _resolve_all_rules_scope_from_parts(
            filter_q=filter_q,
            rulebook_id=rulebook_id,
            rulebook_name=rulebook_name,
        )

    if scope_err:
        return {
            "valid": False,
            "error": scope_err,
            "expectedFormat": ALL_RULES_FILTER_QUERY_FORMAT,
        }

    if not filter_q_body and scoped_rulebook is None:
        return {"valid": True, "empty": True, "filterModel": {}, "filterQ": ""}

    filter_model, _rb, err = _resolve_all_rules_filter_body(
        filter_q_body=filter_q_body,
        scoped_rulebook=scoped_rulebook,
        view_helpers=view_helpers,
    )
    if err:
        return {"valid": False, "error": err}

    return _build_all_rules_validate_payload(
        scoped_rulebook=scoped_rulebook,
        filter_q_body=filter_q_body,
        filter_model=filter_model,
        view_helpers=view_helpers,
    )


def _resolve_all_rules_scope_from_parts(
    *,
    filter_q: str | None,
    rulebook_id: str | None,
    rulebook_name: str | None,
) -> tuple[Rulebook | None, str | None, str | None]:
    from netbox_nsm.all_rules_grid_service import (
        resolve_policy_rulebook_by_id,
        resolve_policy_rulebook_scope,
    )

    body = (filter_q or "").strip()
    scoped_rulebook: Rulebook | None = None

    if (rulebook_id or "").strip():
        scoped_rulebook, err = resolve_policy_rulebook_by_id(rulebook_id)
        if err:
            return None, body or None, err
    elif (rulebook_name or "").strip():
        scoped_rulebook, err = resolve_policy_rulebook_scope(rulebook_name)
        if err:
            return None, body or None, err

    if scoped_rulebook is not None:
        if body:
            _rb_name, unscoped_body, scope_err = parse_scoped_grid_filter_query(body)
            if scope_err:
                return scoped_rulebook, None, scope_err
            return scoped_rulebook, unscoped_body or None, None
        return scoped_rulebook, None, None

    if not body:
        return None, None, None

    rb_name, unscoped_body, scope_err = parse_scoped_grid_filter_query(body)
    if scope_err:
        return None, None, scope_err
    if rb_name:
        scoped_rulebook, err = resolve_policy_rulebook_scope(rb_name)
        if err:
            return None, None, err
        return scoped_rulebook, unscoped_body or None, None
    return None, unscoped_body or None, None
