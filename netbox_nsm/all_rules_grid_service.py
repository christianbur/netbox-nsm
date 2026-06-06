"""AG Grid data for all rules across policy rulebooks."""

from __future__ import annotations

from collections import defaultdict

from django.urls import reverse

from django.core.cache import cache

from netbox_nsm.branch_urls import with_branch_query
from netbox_nsm.models import Rule, Rulebook, RulebookTypeChoices
from netbox_nsm.rulebook_rules_grid_payload import (
    BARE_NAME_FILTER_SHORTHAND,
    _SYSTEM_COLUMN_DEFS,
    apply_suppress_movable,
    _object_column_def,
    build_filter_column_shorthand_names,
    build_rulebook_rules_grid_row,
    build_rulebook_rules_group_row_record,
)
from netbox_nsm.rulebook_rules_grid_service import (
    RULEBOOK_RULES_GRID_BLOCK_SIZE,
    UNION_LAYOUT_CACHE_KEY,
    UNION_LAYOUT_CACHE_TTL,
    _cached_rule_group_maps,
    _parse_filter_model,
    _rules_after_ag_filter,
    resolve_all_rules_filtered_rules,
    wrap_rulebook_rules_grid_row_urls,
)
from netbox_nsm.rulebook_rules_grouping import (
    GROUP_BY_NOT_ALLOWED_MESSAGE,
    GROUP_MODE_SET,
    UNGROUPED_GROUP_KEY,
    assign_rules_to_groups_for_union,
    build_rulebook_rules_group_options,
    build_rule_display_items,
    group_by_field_label,
    parse_group_by_mode,
    parse_rulebook_rules_group_by,
    resolve_group_expansion,
)
from netbox_nsm.query.engine import prepare_rules

__all__ = (
    "ALL_RULES_FILTER_QUERY_COLUMN_ORDER",
    "RULEBOOK_RULES_GRID_BLOCK_SIZE",
    "all_rules_count",
    "build_all_rules_filter_extra_aliases",
    "build_all_rules_filter_maps",
    "build_all_rules_filter_shorthand_names",
    "build_all_rules_grid_config",
    "build_all_rules_grid_scaffold",
    "fetch_all_rules_grid_page",
    "resolve_rules_rulebook_by_id",
    "resolve_rules_rulebook_by_name",
    "resolve_rules_rulebook_scope",
)

ALL_RULES_FILTER_QUERY_COLUMN_ORDER = ("rulebook", "name")


def all_rules_count() -> int:
    return Rule.objects.filter(
        rulebook__rulebook_type=RulebookTypeChoices.SECURITY_RULES
    ).count()


def _security_rules_rulebooks_qs():
    return Rulebook.objects.filter(rulebook_type=RulebookTypeChoices.SECURITY_RULES).order_by(
        "name"
    )


def _all_rules_base_qs():
    return (
        Rule.objects.filter(rulebook__rulebook_type=RulebookTypeChoices.SECURITY_RULES)
        .select_related("rulebook")
        .prefetch_related(
            "source_users",
            "destination_users",
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
        .order_by("rulebook__name", "index", "name")
    )


def _union_global_column_key(area: str, col: dict) -> str:
    """Stable union id for a policy object column (dedupe by area+header)."""
    label = (col.get("label") or "").strip()
    local_key = (col.get("key") or "").strip()
    if area and label:
        return f"{area}::{label}"
    if label:
        return label
    return local_key


def _build_union_layout(view_helpers) -> tuple[list[dict], dict[int, dict[str, str]]]:
    """Return (object column defs grouped by area, rulebook_id -> global->local key map).

    Builds the union of object columns across all policy rulebooks. Columns that share
    the same area label and header (type label) are deduplicated into one grid column;
    per-rulebook local keys are remapped when row data is built.
    """
    cached = cache.get(UNION_LAYOUT_CACHE_KEY)
    if cached is not None:
        rb_maps = {int(rb_id): mapping for rb_id, mapping in cached["rb_maps"].items()}
        return cached["layout"], rb_maps

    union_cols: dict[str, dict] = {}
    rb_maps: dict[int, dict[str, str]] = {}
    area_order: list[str] = []
    columns_by_area: dict[str, list[dict]] = defaultdict(list)

    for rb in _security_rules_rulebooks_qs():
        grouped = view_helpers._build_grouped_rules_table_data([], rb)
        rb_map: dict[str, str] = {}
        for entry in grouped.get("rules_layout") or []:
            if entry.get("kind") != "object":
                continue
            area = (entry.get("label") or entry.get("slug") or "").strip()
            for col in (entry.get("group") or {}).get("columns") or []:
                global_key = _union_global_column_key(area, col)
                if not global_key:
                    continue
                if global_key not in union_cols:
                    label = (col.get("label") or "").strip()
                    union_cols[global_key] = {
                        "key": global_key,
                        "label": label,
                        "area": area,
                        "max_visible_pills": col.get("max_visible_pills", 5),
                        "show_colored_pills": col.get("show_colored_pills", True),
                    }
                    if area not in area_order:
                        area_order.append(area)
                    columns_by_area[area].append(union_cols[global_key])
                rb_map[global_key] = col["key"]
        rb_maps[rb.pk] = rb_map

    layout_groups = [
        {"area": area, "columns": columns_by_area[area]} for area in area_order
    ]
    cache.set(
        UNION_LAYOUT_CACHE_KEY,
        {
            "layout": layout_groups,
            "rb_maps": {str(rb_id): mapping for rb_id, mapping in rb_maps.items()},
        },
        UNION_LAYOUT_CACHE_TTL,
    )
    return layout_groups, rb_maps


def resolve_rules_rulebook_by_name(name: str) -> Rulebook | None:
    """Resolve a policy rulebook by display name (case-insensitive)."""
    rulebook, _err = resolve_rules_rulebook_scope(name)
    return rulebook


def resolve_rules_rulebook_scope(name: str) -> tuple[Rulebook | None, str | None]:
    """Resolve a policy rulebook by display name; return (rulebook, error)."""
    text = (name or "").strip()
    if not text:
        return None, None
    matches = list(_security_rules_rulebooks_qs().filter(name__iexact=text).order_by("pk")[:3])
    if not matches:
        return None, f"Unknown rulebook: {text}"
    if len(matches) > 1:
        return None, f"Ambiguous rulebook name: {text!r} (multiple matches)"
    return matches[0], None


def resolve_rules_rulebook_by_id(pk) -> tuple[Rulebook | None, str | None]:
    """Resolve a policy rulebook by primary key; return (rulebook, error)."""
    if pk in (None, ""):
        return None, None
    try:
        rb_id = int(pk)
    except (TypeError, ValueError):
        return None, f"Invalid rulebook_id: {pk!r}"
    rulebook = _security_rules_rulebooks_qs().filter(pk=rb_id).first()
    if rulebook is None:
        return None, f"Unknown rulebook id: {rb_id}"
    return rulebook, None


def build_all_rules_filter_maps(view_helpers) -> tuple[dict[str, str], list]:
    """Column map and synthetic layout for unscoped all-rules filter queries."""
    layout_groups, _rb_maps = _build_union_layout(view_helpers)
    column_map: dict[str, str] = {
        "index": "Index",
        "name": "Name",
        "description": "Description",
        "enabled": "Status",
        "rulebook": "Rulebook.Name",
    }
    rules_layout: list[dict] = [
        {"kind": "system", "slug": "index", "label": "Index"},
        {"kind": "system", "slug": "name", "label": "Name"},
        {"kind": "system", "slug": "enabled", "label": "Status"},
    ]
    object_areas: dict[str, dict] = {}
    for group in layout_groups:
        area = (group.get("area") or "").strip()
        slug = area.lower().replace(" ", "_") if area else "object"
        if slug not in object_areas:
            object_areas[slug] = {
                "kind": "object",
                "slug": slug,
                "label": area,
                "group": {"slug": slug, "label": area, "columns": []},
            }
        for col in group.get("columns") or []:
            key = col["key"]
            label = (col.get("label") or "").strip()
            if area:
                column_map[key] = f"{area}.{label}.Name"
            else:
                column_map[key] = f"{label}.Name"
            object_areas[slug]["group"]["columns"].append(
                {
                    "key": key,
                    "label": label,
                    "area_slug": slug,
                }
            )
    rules_layout.extend(object_areas.values())
    rules_layout.append(
        {"kind": "system", "slug": "description", "label": "Description"}
    )
    return column_map, rules_layout


def _labels_column_entries(column_map: dict[str, str]) -> list[tuple[str, str]]:
    return [
        (col_id, path)
        for col_id, path in column_map.items()
        if path.endswith(".Labels.Name")
    ]


def build_all_rules_filter_extra_aliases(column_map: dict[str, str]) -> dict[str, str]:
    """Extra lowercase filter tokens for the all-rules grid (Rulebook, LABEL, …)."""
    extra: dict[str, str] = {}
    if "rulebook" in column_map:
        extra["rulebook"] = column_map["rulebook"]
    label_entries = _labels_column_entries(column_map)
    if len(label_entries) == 1:
        extra["label"] = label_entries[0][1]
    return extra


def build_all_rules_filter_shorthand_names(
    column_map: dict[str, str],
    rules_layout: list,
) -> dict[str, str]:
    """Canonical all-rules filter export names (bare Name, Rulebook, LABEL)."""
    names = build_filter_column_shorthand_names(column_map, rules_layout)
    if "name" in column_map:
        names["name"] = BARE_NAME_FILTER_SHORTHAND
    if "rulebook" in column_map:
        names["rulebook"] = "Rulebook"
    label_entries = _labels_column_entries(column_map)
    if len(label_entries) == 1:
        names[label_entries[0][0]] = "LABEL"
    return names


def _all_rules_system_column(slug: str, label: str) -> dict:
    spec_key = "status" if slug == "enabled" else slug
    spec = _SYSTEM_COLUMN_DEFS[spec_key]
    return {"colId": slug, "headerName": label, **spec}


def build_all_rules_grid_scaffold(view_helpers) -> dict:
    """Column definitions for the global rules grid (no row data)."""
    layout_groups, _rb_maps = _build_union_layout(view_helpers)
    column_defs: list[dict] = [
        {
            "colId": "rulebook",
            "field": "rulebook",
            "headerName": "Rulebook",
            "cellRenderer": "rulebookLinkCell",
            "minWidth": 160,
            "width": 190,
            "pinned": "left",
            "lockPosition": "left",
        },
    ]

    for slug, label in (
        ("index", "Index"),
        ("enabled", "Status"),
        ("name", "Name"),
    ):
        column_defs.append(_all_rules_system_column(slug, label))

    for group in layout_groups:
        area = group["area"]
        children = [_object_column_def(col) for col in group["columns"]]
        if not children:
            continue
        column_defs.append(
            {
                "headerName": area.upper() if area else "",
                "children": children,
            }
        )

    column_defs.append(_all_rules_system_column("description", "Description"))

    column_defs.append(
        {
            "colId": "_actions",
            "field": "_actions",
            "headerName": "",
            "cellRenderer": "actionsCell",
            "pinned": "right",
            "lockPosition": "right",
            "width": 72,
            "sortable": False,
            "filter": False,
            "floatingFilter": False,
            "suppressHeaderMenuButton": True,
        }
    )
    return {"columnDefs": apply_suppress_movable(column_defs)}


def _remap_grouped_row(row: dict, rb_map: dict[str, str]) -> dict:
    if not rb_map:
        return row
    remapped = dict(row)
    cells_items: dict = {}
    cells_filter: dict = {}
    for global_key, local_key in rb_map.items():
        src_items = (row.get("cells_items") or {}).get(local_key)
        if src_items:
            cells_items[global_key] = src_items
        src_filter = (row.get("cells_filter") or {}).get(local_key)
        if src_filter:
            cells_filter[global_key] = src_filter
    remapped["cells_items"] = cells_items
    remapped["cells_filter"] = cells_filter
    return remapped


def _records_for_rules(rules, view_helpers, rb_maps, request) -> list[dict]:
    by_rb: dict[int, list] = defaultdict(list)
    for rule in rules:
        by_rb[rule.rulebook_id].append(rule)

    records: list[dict] = []
    for rb_id, rb_rules in by_rb.items():
        rb = rb_rules[0].rulebook
        grouped = view_helpers._build_grouped_rules_table_data(rb_rules, rb)
        rows_by_pk = {row["pk"]: row for row in grouped.get("rows") or []}
        rb_map = rb_maps.get(rb_id, {})
        for rule in rb_rules:
            row = rows_by_pk.get(rule.pk)
            if row is None:
                continue
            remapped = _remap_grouped_row(row, rb_map)
            record = build_rulebook_rules_grid_row(remapped)
            record["rulebook"] = rb.name
            record["_rulebook_url"] = with_branch_query(rb.get_absolute_url(), request)
            records.append(record)
    wrap_rulebook_rules_grid_row_urls(records, request)
    return records


def _build_grouped_all_rules_page(
    rules,
    *,
    start_row: int,
    end_row: int,
    request,
    view_helpers,
    rb_maps,
    group_levels: list[str],
    group_mode: str = "",
    group_mode_secondary: str = "",
    expanded_keys=None,
    collapsed_keys=None,
    rules_layout: list | None = None,
) -> tuple[list[dict], int]:
    primary = group_levels[0] if group_levels else ""
    secondary = group_levels[1] if len(group_levels) > 1 else ""
    secondary_mode = group_mode_secondary or group_mode

    def _assign_union(rules_batch, mode, *, group_mode=GROUP_MODE_SET, rulebook=None):
        del rulebook
        return assign_rules_to_groups_for_union(
            rules_batch,
            mode,
            rb_maps,
            group_mode=group_mode,
        )

    rule_to_primary, rule_to_secondary = _cached_rule_group_maps(
        rules,
        primary=primary,
        secondary=secondary,
        group_mode=group_mode,
        secondary_mode=secondary_mode,
        assign_primary=_assign_union,
        assign_secondary=_assign_union,
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
    records_by_pk = {
        int(rec["pk"]): rec
        for rec in _records_for_rules(page_rules, view_helpers, rb_maps, request)
    }
    level_labels = [
        group_by_field_label(level, rules_layout) for level in group_levels
    ]

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
        record = records_by_pk.get(item["rule"].pk)
        if record is None:
            continue
        record = dict(record)
        record["_rowType"] = "rule"
        record["_groupKey"] = item.get("group_key", 0)
        page.append(record)
    return page, total


def fetch_all_rules_grid_page(
    request,
    *,
    start_row: int,
    end_row: int,
    filter_model_raw: str | None = None,
    filter_model: dict | None = None,
    scoped_rulebook: Rulebook | None = None,
    view_helpers,
    group_levels: list[str] | None = None,
    group_by: str = "",
    group_mode: str = "",
    group_mode_secondary: str = "",
    expanded_keys=None,
    collapsed_keys=None,
    rules_layout: list | None = None,
    use_cached: bool = False,
    refresh_cache: bool = False,
) -> dict:
    start_row = max(0, int(start_row))
    end_row = max(start_row, int(end_row))
    _union_layout, rb_maps = _build_union_layout(view_helpers)
    if filter_model is None:
        filter_model = _parse_filter_model(filter_model_raw)

    rules = resolve_all_rules_filtered_rules(
        scoped_rulebook,
        filter_model,
        view_helpers,
        request,
        use_cached=use_cached,
        refresh_cache=refresh_cache,
    )

    if group_levels is None:
        group_levels = [group_by] if group_by else []
    if group_levels:
        page, total = _build_grouped_all_rules_page(
            rules,
            start_row=start_row,
            end_row=end_row,
            request=request,
            view_helpers=view_helpers,
            rb_maps=rb_maps,
            group_levels=group_levels,
            group_mode=group_mode,
            group_mode_secondary=group_mode_secondary,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
            rules_layout=rules_layout,
        )
        return {"rowData": page, "lastRow": total}

    total = len(rules)
    page_rules = rules[start_row:end_row]
    page_records = _records_for_rules(page_rules, view_helpers, rb_maps, request)
    return {"rowData": page_records, "lastRow": total}


def build_all_rules_grid_config(request, *, read_only: bool = False) -> dict:
    from django.middleware.csrf import get_token

    import netbox_nsm.views.rulebook as rulebook_views

    from netbox_nsm.rulebook_rules_grid_filter import extract_all_rules_filter_params
    from netbox_nsm.rulebook_rules_grid_payload import (
        enabled_status_labels,
    )
    from netbox_nsm.rulebook_rules_tab import (
        GRID_AUTO_LOAD_ALL_MAX,
        GRID_LOAD_MORE_STEP,
        PROGRESSIVE_LOAD_STEPS,
        PROGRESSIVE_LOAD_STEPS_FINE,
        build_rulebook_rules_group_grid_config,
        resolve_rulebook_rules_grid_initial_load_target,
        resolve_rulebook_rules_grid_load_target,
    )

    total = all_rules_count()
    column_map, rules_layout = build_all_rules_filter_maps(rulebook_views)
    scoped_rulebook, filter_q_body, filter_err = extract_all_rules_filter_params(
        request
    )
    can_change = not read_only and request.user.has_perm("netbox_nsm.change_rule")
    can_delete = not read_only and request.user.has_perm("netbox_nsm.delete_rule")
    cfg = {
        "gridDataUrl": reverse("plugins:netbox_nsm:all_rules_grid_api"),
        "queryValidateUrl": reverse("plugins:netbox_nsm:all_rules_query_validate_api"),
        "csrfToken": get_token(request),
        "readOnly": read_only,
        "permissions": {
            "change": can_change,
            "delete": can_delete,
        },
        "statusLabels": enabled_status_labels(),
        "infiniteRowModel": True,
        "cacheBlockSize": RULEBOOK_RULES_GRID_BLOCK_SIZE,
        "totalCount": total,
        "loadRowLimit": resolve_rulebook_rules_grid_load_target(total),
        "initialLoadLimit": resolve_rulebook_rules_grid_initial_load_target(total),
        "loadMoreStep": GRID_LOAD_MORE_STEP,
        "gridLoadSteps": list(PROGRESSIVE_LOAD_STEPS),
        "gridLoadStepsFine": list(PROGRESSIVE_LOAD_STEPS_FINE),
        "gridAutoLoadAllMax": GRID_AUTO_LOAD_ALL_MAX,
        "filterColumnMap": column_map,
        "filterColumnShorthand": build_all_rules_filter_shorthand_names(
            column_map, rules_layout
        ),
        "filterQueryColumnOrder": list(ALL_RULES_FILTER_QUERY_COLUMN_ORDER),
        "useServerFilterQ": True,
    }
    if scoped_rulebook is not None:
        cfg["activeRulebookId"] = scoped_rulebook.pk
        cfg["activeRulebook"] = scoped_rulebook.name
    if filter_q_body:
        cfg["activeFilterQ"] = filter_q_body
        cfg["filterQuery"] = filter_q_body
    if filter_err:
        cfg["filterQueryError"] = filter_err
    cfg["groupByOptions"] = build_rulebook_rules_group_options(
        rules_layout,
        include_rulebook=True,
    )
    cfg["groupByNotAllowedMessage"] = str(GROUP_BY_NOT_ALLOWED_MESSAGE)
    group_by = parse_rulebook_rules_group_by(
        request,
        rules_layout=rules_layout,
        include_rulebook=True,
    )
    if group_by:
        cfg.update(
            build_rulebook_rules_group_grid_config(
                request,
                rules_layout,
                include_rulebook=True,
            )
        )
    return cfg
