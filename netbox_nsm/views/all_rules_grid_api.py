from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.views import View

from netbox_nsm.all_rules_grid_service import (
    build_all_rules_grid_scaffold,
    fetch_all_rules_grid_page,
)
from netbox_nsm.rulebook_rules_grid_filter import (
    ALL_RULES_FILTER_QUERY_FORMAT,
    extract_grid_filter_params,
    resolve_all_rules_filter_model,
)
from netbox_nsm.rulebook_rules_grouping import (
    parse_group_by_mode,
    parse_group_default_expanded,
    parse_rulebook_rules_group_by,
    parse_rulebook_rules_group_levels,
    parse_rulebook_rules_group_modes,
    resolve_request_group_expansion,
    validate_rulebook_rules_group_request,
)

__all__ = ("AllRulesGridApiView",)


class AllRulesGridApiView(LoginRequiredMixin, View):
    """
    GET /plugins/netbox-nsm/api/rules/all-grid/

    Query: startRow, endRow, filter (JSON), filter_q (unscoped body),
    rulebook / rulebook_id (canonical scope).

    Deprecated scoped filter_q (colon syntax only)::

        "Rulebook Name": Name(x) AND ...
    """

    def get(self, request):
        if not request.user.has_perm("netbox_nsm.view_rule"):
            return HttpResponseForbidden()

        import netbox_nsm.views.rulebook as rulebook_views

        if request.GET.get("meta") == "1":
            return JsonResponse(build_all_rules_grid_scaffold(rulebook_views))

        try:
            start_row = int(request.GET.get("startRow", 0))
        except (TypeError, ValueError):
            start_row = 0
        try:
            end_row = int(request.GET.get("endRow", start_row + 500))
        except (TypeError, ValueError):
            end_row = start_row + 500

        filter_raw, _filter_q_raw = extract_grid_filter_params(request)
        filter_model, scoped_rulebook, filter_err = resolve_all_rules_filter_model(
            filter_model_raw=filter_raw,
            view_helpers=rulebook_views,
            request=request,
        )
        if filter_err:
            return JsonResponse(
                {
                    "error": filter_err,
                    "expectedFormat": ALL_RULES_FILTER_QUERY_FORMAT,
                },
                status=400,
            )

        grouped_meta = (
            rulebook_views._build_grouped_rules_table_data([], scoped_rulebook)
            if scoped_rulebook
            else {"rules_layout": []}
        )
        rules_layout = grouped_meta.get("rules_layout") or []
        if not rules_layout:
            from netbox_nsm.all_rules_grid_service import build_all_rules_filter_maps

            _column_map, rules_layout = build_all_rules_filter_maps(rulebook_views)

        group_err = validate_rulebook_rules_group_request(
            request,
            rules_layout=rules_layout,
            include_rulebook=True,
        )
        if group_err:
            return JsonResponse({"error": group_err}, status=400)

        group_by = parse_rulebook_rules_group_by(
            request,
            rules_layout=rules_layout,
            include_rulebook=True,
        )
        group_levels = parse_rulebook_rules_group_levels(
            request,
            rules_layout=rules_layout,
            include_rulebook=True,
        )
        group_mode = parse_group_by_mode(request) if group_levels else ""
        group_mode_secondary = ""
        if len(group_levels) > 1:
            _primary_mode, group_mode_secondary = parse_rulebook_rules_group_modes(
                request
            )
        if group_levels:
            preview_rules = None
            if parse_group_default_expanded(request) == 1:
                from netbox_nsm.all_rules_grid_service import (
                    prepare_rules,
                    _all_rules_base_qs,
                )

                preview_rules = prepare_rules(list(_all_rules_base_qs()))
                if scoped_rulebook is not None:
                    preview_rules = [
                        rule
                        for rule in preview_rules
                        if rule.rulebook_id == scoped_rulebook.pk
                    ]
                if filter_model:
                    if scoped_rulebook is not None:
                        from netbox_nsm.all_rules_grid_service import (
                            _rules_after_ag_filter,
                        )

                        preview_rules = _rules_after_ag_filter(
                            preview_rules,
                            scoped_rulebook,
                            filter_model,
                            rulebook_views,
                        )
                    else:
                        from netbox_nsm.all_rules_grid_service import (
                            _build_union_layout,
                            _records_for_rules,
                        )
                        from netbox_nsm.rulebook_rules_grid_filter import (
                            apply_ag_grid_row_filter,
                        )

                        _union_layout, rb_maps = _build_union_layout(rulebook_views)
                        records = _records_for_rules(
                            preview_rules, rulebook_views, rb_maps, request
                        )
                        matched_pks = {
                            int(rec["pk"])
                            for rec in apply_ag_grid_row_filter(records, filter_model)
                        }
                        preview_rules = [
                            rule for rule in preview_rules if rule.pk in matched_pks
                        ]
            expanded_keys, collapsed_keys, _default_level = (
                resolve_request_group_expansion(
                    request,
                    group_levels=group_levels,
                    rules_for_preview=preview_rules,
                    group_mode=group_mode,
                    group_mode_secondary=group_mode_secondary,
                )
            )
        else:
            expanded_keys, collapsed_keys, _default_level = (None, None, None)

        refresh_cache = (
            request.GET.get("refresh") == "1" or request.GET.get("cache_bust") == "1"
        )
        use_cached = request.GET.get("use_cached") == "1" and not refresh_cache
        payload = fetch_all_rules_grid_page(
            request,
            start_row=start_row,
            end_row=end_row,
            filter_model=filter_model,
            scoped_rulebook=scoped_rulebook,
            view_helpers=rulebook_views,
            group_levels=group_levels,
            group_by=group_by,
            group_mode=group_mode,
            group_mode_secondary=group_mode_secondary,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
            rules_layout=rules_layout,
            use_cached=use_cached,
            refresh_cache=refresh_cache,
        )
        response = JsonResponse(payload)
        response["Cache-Control"] = "private, max-age=0, no-cache"
        return response
