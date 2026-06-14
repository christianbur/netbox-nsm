from __future__ import annotations

from netbox_nsm.rulebooks.rules_tab.filter_params import parse_rules_filter_model

def _resolve_rules_filter_model(
    request,
    rulebook,
    flat_columns: list,
    *,
    view_helpers,
    rules_layout: list,
) -> tuple[dict, str | None, str]:
    """filter_q takes precedence over per-column quick-search params."""
    from netbox_nsm.rulebooks.grid_filter import (
        extract_grid_filter_params,
        resolve_rules_filter_model,
    )

    filter_raw, filter_q_raw = extract_grid_filter_params(request)
    filter_q_raw = filter_q_raw or ""
    column_model = parse_rules_filter_model(request, flat_columns)
    if column_model:
        return column_model, None, filter_q_raw

    if filter_q_raw:
        filter_model, err = resolve_rules_filter_model(
            filter_model_raw=filter_raw,
            filter_q_raw=filter_q_raw,
            rulebook=rulebook,
            view_helpers=view_helpers,
            rules_layout=rules_layout,
        )
        if err:
            return parse_rules_filter_model(request, flat_columns), err, filter_q_raw
        return filter_model or {}, None, filter_q_raw
    return parse_rules_filter_model(request, flat_columns), None, filter_q_raw
