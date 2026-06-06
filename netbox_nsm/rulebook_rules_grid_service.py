"""Server-side Rules AG Grid data (Community infinite row model)."""

from __future__ import annotations

import hashlib
import json

from django.core.cache import cache

from netbox_nsm.branch_urls import with_branch_query
from netbox_nsm.models import Rule
from netbox_nsm.rulebook_rules_grid_filter import parse_filter_model_json
from netbox_nsm.rulebook_rules_grid_payload import (
    apply_ag_grid_row_filter,
    build_rulebook_rules_grid_column_defs,
    build_rulebook_rules_grid_row,
    build_rulebook_rules_group_row_record,
)
from netbox_nsm.rulebook_rules_grouping import (
    UNGROUPED_GROUP_KEY,
    assign_rules_to_groups,
    build_rulebook_rules_group_options,
    build_rule_display_items,
    group_by_field_label,
    parse_collapsed_keys,
    parse_expanded_keys,
    parse_group_by_mode,
    parse_rulebook_rules_group_levels,
    resolve_group_expansion,
)
from netbox_nsm.query.engine import prepare_rules

__all__ = (
    "RULEBOOK_RULES_GRID_BLOCK_SIZE",
    "RULEBOOK_RULES_GRID_RULES_CACHE_TTL",
    "all_rules_grid_rules_cache_key",
    "fetch_rulebook_rules_grid_page",
    "rulebook_rules_grid_column_defs",
    "rulebook_rules_grid_filtered_rules",
    "rulebook_rules_grid_filtered_rules_after_ag_filter",
    "rulebook_rules_grid_rules_cache_key",
    "resolve_all_rules_filtered_rules",
    "resolve_rulebook_rules_grid_filtered_rules",
    "wrap_rulebook_rules_grid_row_urls",
)

RULEBOOK_RULES_GRID_BLOCK_SIZE = 100
RULEBOOK_RULES_GRID_RULES_CACHE_TTL = 600
UNION_LAYOUT_CACHE_KEY = "nsm:all_rules:union_layout_v1"
UNION_LAYOUT_CACHE_TTL = 600


def _group_assign_cache_key(
    rule_pks: list[int],
    primary: str,
    secondary: str = "",
) -> str:
    pks_sig = hashlib.sha256(
        ",".join(str(pk) for pk in rule_pks).encode("utf-8")
    ).hexdigest()[:16]
    return f"nsm:rulebook_rules_grid:group_map:{pks_sig}:{primary}:{secondary}"


def _serialize_bucket_map(bucket_map: dict[int, list]) -> dict[str, list]:
    return {str(pk): buckets for pk, buckets in bucket_map.items()}


def _deserialize_bucket_map(data: dict[str, list]) -> dict[int, list]:
    return {int(pk): buckets for pk, buckets in data.items()}


def _cached_rule_group_maps(
    rules: list,
    *,
    primary: str,
    secondary: str = "",
    group_mode: str,
    secondary_mode: str = "",
    rulebook=None,
    assign_primary,
    assign_secondary=None,
) -> tuple[dict[int, list], dict[int, list] | None]:
    rule_pks = [rule.pk for rule in rules]
    cache_key = _group_assign_cache_key(rule_pks, primary, secondary)
    cached = cache.get(cache_key)
    if cached is not None:
        primary_map = _deserialize_bucket_map(cached["primary"])
        secondary_map = None
        if cached.get("secondary") is not None:
            secondary_map = _deserialize_bucket_map(cached["secondary"])
        return primary_map, secondary_map

    rule_to_primary = assign_primary(
        rules,
        primary,
        group_mode=group_mode,
        rulebook=rulebook,
    )
    rule_to_secondary = None
    if secondary:
        assign_fn = assign_secondary or assign_primary
        rule_to_secondary = assign_fn(
            rules,
            secondary,
            group_mode=secondary_mode or group_mode,
            rulebook=rulebook,
        )
    cache.set(
        cache_key,
        {
            "primary": _serialize_bucket_map(rule_to_primary),
            "secondary": (
                _serialize_bucket_map(rule_to_secondary)
                if rule_to_secondary is not None
                else None
            ),
        },
        RULEBOOK_RULES_GRID_RULES_CACHE_TTL,
    )
    return rule_to_primary, rule_to_secondary


def _filter_model_cache_signature(filter_model) -> str:
    payload = json.dumps(filter_model or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def rulebook_rules_grid_rules_cache_key(rulebook_pk: int, filter_model) -> str:
    return (
        f"nsm:rulebook_rules_grid:rules:{rulebook_pk}:"
        f"{_filter_model_cache_signature(filter_model)}"
    )


def all_rules_grid_rules_cache_key(
    scoped_rulebook_pk: int | None,
    filter_model,
) -> str:
    scope = int(scoped_rulebook_pk or 0)
    return (
        f"nsm:all_rules_grid:rules:{scope}:"
        f"{_filter_model_cache_signature(filter_model)}"
    )


def _rules_from_cached_pks(rulebook, cached_pks: list[int]) -> list:
    if not cached_pks:
        return []
    order = {pk: idx for idx, pk in enumerate(cached_pks)}
    rules = prepare_rules(_base_rules_qs(rulebook).filter(pk__in=cached_pks))
    rules.sort(key=lambda rule: order.get(rule.pk, len(cached_pks)))
    return rules


def _base_rules_qs(rulebook):
    return (
        Rule.objects.filter(rulebook=rulebook)
        .prefetch_related(
            "source_users",
            "destination_users",
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
        .order_by("index")
    )


def rulebook_rules_grid_filtered_rules(rulebook):
    return prepare_rules(_base_rules_qs(rulebook))


def rulebook_rules_grid_column_defs(rulebook, view_helpers) -> list[dict]:
    grouped = view_helpers._build_grouped_rules_table_data([], rulebook)
    payload = build_rulebook_rules_grid_column_defs(grouped)
    return payload["columnDefs"]


def wrap_rulebook_rules_grid_row_urls(records: list[dict], request) -> None:
    for record in records or []:
        for key in ("_detail_url", "_edit_url", "_delete_url"):
            if key in record:
                record[key] = with_branch_query(record[key], request)
        for value in record.values():
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict) and item.get("url"):
                    item["url"] = with_branch_query(item["url"], request)


def _parse_filter_model(raw: str | None) -> dict | None:
    return parse_filter_model_json(raw)


def _rules_after_ag_filter(rules, rulebook, filter_model, view_helpers) -> list:
    grouped = view_helpers._build_grouped_rules_table_data(rules, rulebook)
    rows_by_pk = {row["pk"]: row for row in grouped.get("rows") or []}
    filtered: list = []
    for rule in rules:
        row = rows_by_pk.get(rule.pk)
        if row is None:
            continue
        record = build_rulebook_rules_grid_row(row)
        if apply_ag_grid_row_filter([record], filter_model):
            filtered.append(rule)
    return filtered


def _build_grouped_rules_page(
    rules,
    rulebook,
    *,
    start_row: int,
    end_row: int,
    request,
    view_helpers,
    group_levels: list[str],
    group_mode: str = "",
    group_mode_secondary: str = "",
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
    rules_layout: list | None = None,
) -> tuple[list[dict], int]:
    primary = group_levels[0] if group_levels else ""
    secondary = group_levels[1] if len(group_levels) > 1 else ""
    secondary_mode = group_mode_secondary or group_mode
    rule_to_primary, rule_to_secondary = _cached_rule_group_maps(
        rules,
        primary=primary,
        secondary=secondary,
        group_mode=group_mode,
        secondary_mode=secondary_mode,
        rulebook=rulebook,
        assign_primary=assign_rules_to_groups,
    )
    display_items = build_rule_display_items(
        rules,
        rule_to_buckets=rule_to_primary,
        enabled=True,
        rule_to_buckets_secondary=rule_to_secondary,
        expanded_keys=expanded_keys,
        collapsed_keys=collapsed_keys,
    )
    total = len(display_items)
    page_items = display_items[start_row:end_row]

    rule_pks = [item["rule"].pk for item in page_items if item.get("kind") == "rule"]
    rules_by_pk = {rule.pk: rule for rule in rules}
    page_rules = [rules_by_pk[pk] for pk in rule_pks if pk in rules_by_pk]
    grouped = view_helpers._build_grouped_rules_table_data(page_rules, rulebook)
    rows_by_pk = {row["pk"]: row for row in grouped.get("rows") or []}

    level_labels = [group_by_field_label(level, rules_layout) for level in group_levels]

    page: list[dict] = []
    for item in page_items:
        if item.get("kind") == "group":
            group_level = int(item.get("group_level") or 1)
            field_label = (
                level_labels[group_level - 1]
                if group_level - 1 < len(level_labels)
                else ""
            )
            page.append(
                build_rulebook_rules_group_row_record(
                    item.get("bucket"),
                    group_key=item.get("group_key", UNGROUPED_GROUP_KEY),
                    rule_count=item.get("rule_count", 0),
                    request=request,
                    group_level=group_level,
                    group_field_label=field_label,
                )
            )
            continue
        rule = item["rule"]
        row = rows_by_pk.get(rule.pk)
        if row is None:
            continue
        record = build_rulebook_rules_grid_row(row)
        record["_rowType"] = "rule"
        record["_groupKey"] = item.get("group_key", 0)
        page.append(record)
    return page, total


def rulebook_rules_grid_filtered_rules_after_ag_filter(
    rules, rulebook, filter_model, view_helpers
) -> list:
    return _rules_after_ag_filter(rules, rulebook, filter_model, view_helpers)


def resolve_rulebook_rules_grid_filtered_rules(
    rulebook,
    filter_model,
    view_helpers,
    *,
    use_cached: bool = False,
    refresh_cache: bool = False,
) -> list:
    """Return filtered rules for a rulebook, optionally reusing a 10-minute cache."""
    cache_key = rulebook_rules_grid_rules_cache_key(rulebook.pk, filter_model)
    if refresh_cache:
        cache.delete(cache_key)
    elif use_cached:
        cached_pks = cache.get(cache_key)
        if cached_pks is not None:
            return _rules_from_cached_pks(rulebook, cached_pks)

    rules = rulebook_rules_grid_filtered_rules(rulebook)
    if filter_model:
        rules = _rules_after_ag_filter(rules, rulebook, filter_model, view_helpers)
    cache.set(
        cache_key,
        [rule.pk for rule in rules],
        RULEBOOK_RULES_GRID_RULES_CACHE_TTL,
    )
    return rules


def resolve_all_rules_filtered_rules(
    scoped_rulebook,
    filter_model,
    view_helpers,
    request,
    *,
    use_cached: bool = False,
    refresh_cache: bool = False,
) -> list:
    """Return filtered rules for the all-rules grid, optionally from cache."""
    from netbox_nsm.all_rules_grid_service import (
        _all_rules_base_qs,
        _build_union_layout,
        _records_for_rules,
    )
    from netbox_nsm.rulebook_rules_grid_payload import apply_ag_grid_row_filter

    cache_key = all_rules_grid_rules_cache_key(
        scoped_rulebook.pk if scoped_rulebook is not None else None,
        filter_model,
    )
    if refresh_cache:
        cache.delete(cache_key)
    elif use_cached:
        cached_pks = cache.get(cache_key)
        if cached_pks is not None:
            if not cached_pks:
                return []
            order = {pk: idx for idx, pk in enumerate(cached_pks)}
            rules = prepare_rules(_all_rules_base_qs().filter(pk__in=cached_pks))
            rules.sort(key=lambda rule: order.get(rule.pk, len(cached_pks)))
            return rules

    _union_layout, rb_maps = _build_union_layout(view_helpers)
    rules = prepare_rules(list(_all_rules_base_qs()))
    if scoped_rulebook is not None:
        rules = [rule for rule in rules if rule.rulebook_id == scoped_rulebook.pk]

    if filter_model:
        if scoped_rulebook is not None:
            rules = _rules_after_ag_filter(
                rules, scoped_rulebook, filter_model, view_helpers
            )
        else:
            records = _records_for_rules(rules, view_helpers, rb_maps, request)
            matched_pks = {
                int(rec["pk"])
                for rec in apply_ag_grid_row_filter(records, filter_model)
            }
            rules = [rule for rule in rules if rule.pk in matched_pks]

    cache.set(
        cache_key,
        [rule.pk for rule in rules],
        RULEBOOK_RULES_GRID_RULES_CACHE_TTL,
    )
    return rules


def fetch_rulebook_rules_grid_page(
    request,
    rulebook,
    *,
    start_row: int,
    end_row: int,
    filter_model_raw: str | None = None,
    filter_model: dict | None = None,
    group_levels: list[str] | None = None,
    group_by: str = "",
    group_mode: str = "",
    group_mode_secondary: str = "",
    expanded_keys: set[str] | None = None,
    collapsed_keys: set[str] | None = None,
    view_helpers,
    rules_layout: list | None = None,
    use_cached: bool = False,
    refresh_cache: bool = False,
) -> dict:
    """Return a JSON-serializable block for AG Grid infinite row model."""
    start_row = max(0, int(start_row))
    end_row = max(start_row, int(end_row))
    if filter_model is None:
        filter_model = _parse_filter_model(filter_model_raw)
    rules = resolve_rulebook_rules_grid_filtered_rules(
        rulebook,
        filter_model,
        view_helpers,
        use_cached=use_cached,
        refresh_cache=refresh_cache,
    )

    if group_levels is None:
        group_levels = [group_by] if group_by else []

    if group_levels:
        page, total = _build_grouped_rules_page(
            rules,
            rulebook,
            start_row=start_row,
            end_row=end_row,
            request=request,
            view_helpers=view_helpers,
            group_levels=group_levels,
            group_mode=group_mode,
            group_mode_secondary=group_mode_secondary,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
            rules_layout=rules_layout,
        )
        wrap_rulebook_rules_grid_row_urls(page, request)
    elif filter_model:
        grouped = view_helpers._build_grouped_rules_table_data(rules, rulebook)
        records = [
            build_rulebook_rules_grid_row(row) for row in grouped.get("rows") or []
        ]
        wrap_rulebook_rules_grid_row_urls(records, request)
        total = len(records)
        page = records[start_row:end_row]
    else:
        total = len(rules)
        chunk = rules[start_row:end_row]
        grouped = view_helpers._build_grouped_rules_table_data(chunk, rulebook)
        page = [build_rulebook_rules_grid_row(row) for row in grouped.get("rows") or []]
        wrap_rulebook_rules_grid_row_urls(page, request)

    return {
        "rowData": page,
        "lastRow": total,
    }
