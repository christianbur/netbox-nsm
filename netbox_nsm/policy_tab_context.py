"""Shared context for Rulebook Policy and Rules (AG Grid) tabs."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.middleware.csrf import get_token
from django.urls import reverse
from django.utils.translation import gettext as _

from netbox_nsm.models import Rule
from netbox_nsm.policy_rule_grouping import (
    COLLAPSE_ALL,
    EXPAND_ALL,
    GROUP_BY_NOT_ALLOWED_MESSAGE,
    build_policy_group_options,
    parse_group_default_expanded,
    parse_policy_group_levels,
    resolve_group_expansion,
)
from netbox_nsm.policy_grid_payload import (
    build_ag_grid_filter_model,
    build_policy_ag_grid_column_defs,
    build_policy_ag_grid_payload,
    enabled_status_labels,
)
from netbox_nsm.query import (
    RulebookContext,
    build_query_help_sections,
    filter_rules,
    parse,
)
from netbox_nsm.query.engine import prepare_rules

# Staged client download (AG Grid Community, client-side row model).
PROGRESSIVE_LOAD_STEPS = (
    10,
    20,
    40,
    80,
    160,
    320,
    640,
    1280,
    2560,
    5120,
    10240,
    20480,
    40960,
    50000,
)
PROGRESSIVE_LOAD_STEPS_FINE = (5, 10, 20, 50, 100, 250)
POLICY_GRID_CLIENT_MAX = 50000
GRID_INITIAL_LOAD_LIMIT = POLICY_GRID_CLIENT_MAX
GRID_LOAD_MORE_STEP = 2000
DEFAULT_GRID_LOAD_LIMIT = POLICY_GRID_CLIENT_MAX
GRID_AUTO_LOAD_ALL_MAX = POLICY_GRID_CLIENT_MAX


def resolve_policy_grid_load_target(total_count: int | None = None) -> int:
    """Maximum client-side row count (staged fetch runs until this target)."""
    if not total_count or total_count <= 0:
        return DEFAULT_GRID_LOAD_LIMIT
    return min(int(total_count), POLICY_GRID_CLIENT_MAX)


def resolve_policy_grid_initial_load_target(total_count: int | None = None) -> int:
    """Rows to fetch on first open (full staged load to loadRowLimit)."""
    return resolve_policy_grid_load_target(total_count)


def build_policy_group_grid_config(
    request,
    policy_layout: list,
    *,
    include_rulebook: bool = False,
) -> dict:
    """Client-side row grouping state (Community custom group rows)."""
    cfg: dict = {
        "groupByOptions": build_policy_group_options(
            policy_layout,
            include_rulebook=include_rulebook,
        ),
        "groupByNotAllowedMessage": str(GROUP_BY_NOT_ALLOWED_MESSAGE),
    }
    group_levels = parse_policy_group_levels(
        request,
        policy_layout=policy_layout,
        include_rulebook=include_rulebook,
    )
    if not group_levels:
        return cfg
    group_by = group_levels[0]
    cfg["groupBy"] = group_by
    cfg["groupByEnabled"] = True
    cfg["groupColumnLabel"] = str(_("Group"))
    cfg["groupDefaultExpanded"] = parse_group_default_expanded(request)
    if len(group_levels) > 1:
        cfg["groupBy2"] = group_levels[1]
    preview_items = [{"kind": "group", "group_key": "preview", "group_level": 1}]
    if len(group_levels) > 1:
        preview_items.append(
            {"kind": "group", "group_key": "preview::nested", "group_level": 2}
        )
    expanded_keys, collapsed_keys, _default_level = resolve_group_expansion(
        request,
        group_by=group_by,
        display_items=preview_items,
    )
    if expanded_keys is not None:
        if EXPAND_ALL in expanded_keys:
            cfg["groupExpansionMode"] = "all_expanded"
        else:
            cfg["groupExpansionMode"] = "expanded"
            cfg["groupExpandedKeys"] = sorted(expanded_keys)
    elif collapsed_keys is not None:
        if COLLAPSE_ALL in collapsed_keys:
            cfg["groupExpansionMode"] = "all_collapsed"
        else:
            cfg["groupExpansionMode"] = "collapsed"
            cfg["groupCollapsedKeys"] = sorted(collapsed_keys)
    return cfg


def build_rules_grid_config(
    request,
    instance,
    *,
    query=None,
    policy_layout=None,
    rulebook_context=None,
    total_count=None,
) -> dict:
    """Client config for the AG Grid Rules tab (filters, bulk actions)."""
    from netbox_nsm.policy_grid_service import POLICY_GRID_BLOCK_SIZE

    cfg = {
        "apiBase": "/api/plugins/netbox-nsm/rules/",
        "rulebookId": instance.pk,
        "csrfToken": get_token(request),
        "permissions": {
            "add": request.user.has_perm("netbox_nsm.add_rule"),
            "change": request.user.has_perm("netbox_nsm.change_rule"),
            "delete": request.user.has_perm("netbox_nsm.delete_rule"),
        },
        "statusLabels": enabled_status_labels(),
        "gridDataUrl": reverse(
            "plugins:netbox_nsm:rulebook_policy_grid_api",
            args=[instance.pk],
        ),
        "queryValidateUrl": reverse(
            "plugins:netbox_nsm:rulebook_policy_query_validate_api",
            args=[instance.pk],
        ),
        "infiniteRowModel": True,
        "cacheBlockSize": POLICY_GRID_BLOCK_SIZE,
        "totalCount": int(total_count or 0),
        "loadRowLimit": resolve_policy_grid_load_target(total_count),
        "initialLoadLimit": resolve_policy_grid_initial_load_target(total_count),
        "loadMoreStep": GRID_LOAD_MORE_STEP,
        "gridLoadSteps": list(PROGRESSIVE_LOAD_STEPS),
        "gridLoadStepsFine": list(PROGRESSIVE_LOAD_STEPS_FINE),
        "gridAutoLoadAllMax": GRID_AUTO_LOAD_ALL_MAX,
    }
    if policy_layout is not None:
        cfg.update(build_policy_group_grid_config(request, policy_layout))
    if query is not None and policy_layout is not None and rulebook_context is not None:
        filter_model = build_ag_grid_filter_model(
            query, policy_layout, rulebook_context
        )
        if filter_model:
            cfg["initialFilterModel"] = filter_model
    nsm_q_raw = request.GET.get("nsm_q", "").strip()
    if nsm_q_raw:
        cfg["nsmQ"] = nsm_q_raw
    clear_params = request.GET.copy()
    clear_params.pop("nsm_q", None)
    clear_params.pop("page", None)
    clear_url = request.path
    if clear_params:
        clear_url = f"{clear_url}?{clear_params.urlencode()}"
    from netbox_nsm.branch_urls import with_branch_query

    cfg["clearFiltersUrl"] = with_branch_query(clear_url, request)
    return cfg


def build_policy_tab_context(
    request, instance, *, view_helpers, grid_all_rules: bool = False
) -> dict:
    """
    Build template context for policy/rules tabs.

    view_helpers: module with _available_policy_columns, _get_policy_table_config,
    _build_policy_table_class, _build_grouped_policy_table_data, SECURITY_RULES_COLUMNS.
    """
    availability = view_helpers._available_policy_columns(instance)
    base_rules_qs = (
        Rule.objects.filter(rulebook=instance)
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

    nsm_q_raw = request.GET.get("nsm_q", "").strip()
    query = parse(nsm_q_raw)
    context = RulebookContext(instance)

    if grid_all_rules and not nsm_q_raw:
        total_count = base_rules_qs.count()
        filtered_rules = []
        all_rules = []
    else:
        all_rules = prepare_rules(base_rules_qs)
        filtered_rules = filter_rules(all_rules, query, context)
        total_count = len(filtered_rules)

    config = view_helpers._get_policy_table_config(request, instance)
    selected_columns = config["selected_columns"]
    custom_columns = config["custom_columns"]

    all_columns = [name for name, _ in view_helpers.SECURITY_RULES_COLUMNS]
    excluded_columns = [name for name in all_columns if name not in selected_columns]
    custom_keys = [f"custom_column_{idx}" for idx in range(1, len(custom_columns) + 1)]

    VALID_PER_PAGE = [25, 50, 100, 250, 500, 1000]

    if grid_all_rules:
        per_page = total_count or 1
        page_obj = None
        paginator = None
        paged_rules = filtered_rules
    else:
        try:
            per_page = int(request.GET.get("per_page", 100))
            if per_page not in VALID_PER_PAGE:
                per_page = 100
        except (ValueError, TypeError):
            per_page = 100
        paginator = Paginator(filtered_rules, per_page)
        try:
            page_num = int(request.GET.get("page", 1))
        except (ValueError, TypeError):
            page_num = 1
        page_num = max(1, min(page_num, paginator.num_pages or 1))
        page_obj = paginator.get_page(page_num)
        paged_rules = list(page_obj.object_list)

    get_params = request.GET.copy()
    get_params.pop("page", None)
    base_qs_str = get_params.urlencode()

    paged_pks = [r.pk for r in paged_rules]
    paged_qs = Rule.objects.filter(pk__in=paged_pks).prefetch_related(
        "source_users",
        "destination_users",
        "object_items__field",
        "object_items__content_type",
        "group_items__field",
        "group_items__security_group",
    )
    paged_qs_list = list(paged_qs)
    cached_map = {r.pk: r for r in paged_rules}
    for rule in paged_qs_list:
        src = cached_map.get(rule.pk)
        if src:
            rule._cached_object_items = src._cached_object_items
            rule._cached_group_items = src._cached_group_items
    paged_qs_ordered = sorted(paged_qs_list, key=lambda r: paged_pks.index(r.pk))

    policy_table_class = view_helpers._build_policy_table_class(
        custom_columns, selected_columns
    )
    table_sequence = ("pk",) + tuple(selected_columns) + tuple(custom_keys) + ("...",)
    policy_table = policy_table_class(
        paged_qs_ordered,
        orderable=False,
        exclude=excluded_columns,
        sequence=table_sequence,
    )
    policy_table.configure(request)

    grouped = view_helpers._build_grouped_policy_table_data(paged_qs_ordered, instance)

    from netbox_nsm.branch_urls import wrap_policy_row_urls, with_branch_query

    wrap_policy_row_urls(grouped.get("rows") or [], request)

    ctx = {
        "table": policy_table,
        "is_nsm_rules": True,
        "security_rules_columns": view_helpers.SECURITY_RULES_COLUMNS,
        "selected_security_rules_columns": selected_columns,
        "nsm_available_policy_areas": availability,
        "nsm_q": nsm_q_raw,
        "nsm_query": query,
        "nsm_query_error": query.parse_error,
        "nsm_show_facet_panel": True,
        "nsm_query_help_sections": build_query_help_sections(instance),
        "policy_layout": grouped["policy_layout"],
        "policy_header_groups": grouped["header_groups"],
        "policy_grouped_column_count": grouped["column_count"],
        "policy_total_column_count": grouped["total_column_count"],
        "policy_grouped_rows": grouped["rows"],
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "valid_per_page": VALID_PER_PAGE,
        "total_count": total_count,
        "base_qs_str": base_qs_str,
        "policy_ag_grid_payload": (
            build_policy_ag_grid_column_defs(grouped)
            if grid_all_rules
            else build_policy_ag_grid_payload(grouped)
        ),
    }
    if grid_all_rules:
        ctx["rules_grid_config"] = build_rules_grid_config(
            request,
            instance,
            query=query,
            policy_layout=grouped["policy_layout"],
            rulebook_context=context,
            total_count=total_count,
        )
    from urllib.parse import quote

    from django.urls import reverse

    return_path = with_branch_query(request.path, request)
    ctx["nsm_rule_add_url"] = with_branch_query(
        reverse("plugins:netbox_nsm:rule_add")
        + f"?rulebook={instance.pk}&return_url={quote(return_path, safe='')}",
        request,
    )
    return ctx
