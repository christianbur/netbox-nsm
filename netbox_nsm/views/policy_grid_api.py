"""Lazy JSON API for the policy AG Grid (Community infinite row model)."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.policy_grid_filter import (
    extract_grid_filter_params,
    resolve_policy_filter_model,
)
from netbox_nsm.policy_grid_service import (
    POLICY_GRID_BLOCK_SIZE,
    fetch_policy_grid_page,
    policy_grid_column_defs,
    policy_grid_filtered_rules,
    policy_grid_filtered_rules_after_ag_filter,
)
from netbox_nsm.policy_rule_grouping import (
    parse_group_by_mode,
    parse_group_default_expanded,
    parse_policy_group_by,
    parse_policy_group_levels,
    parse_policy_group_modes,
    resolve_request_group_expansion,
    validate_policy_group_request,
)

__all__ = ("RulebookPolicyGridApiView",)


class RulebookPolicyGridApiView(LoginRequiredMixin, View):
    """
    GET /plugins/netbox-nsm/api/rulebooks/<pk>/policy-grid/

    Query: startRow, endRow, filter (JSON), filter_q (shorthand text)
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rulebook"):
            return HttpResponseForbidden()

        instance = get_object_or_404(Rulebook, pk=pk)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return JsonResponse({"error": "not a policy rulebook"}, status=404)

        import netbox_nsm.views.rulebook as rulebook_views

        if request.GET.get("meta") == "1":
            return JsonResponse(
                {
                    "columnDefs": policy_grid_column_defs(instance, rulebook_views),
                    "cacheBlockSize": POLICY_GRID_BLOCK_SIZE,
                }
            )

        try:
            start_row = int(request.GET.get("startRow", 0))
        except (TypeError, ValueError):
            start_row = 0
        try:
            end_row = int(request.GET.get("endRow", start_row + POLICY_GRID_BLOCK_SIZE))
        except (TypeError, ValueError):
            end_row = start_row + POLICY_GRID_BLOCK_SIZE

        grouped_meta = rulebook_views._build_grouped_policy_table_data([], instance)
        policy_layout = grouped_meta.get("policy_layout") or []

        filter_raw, filter_q_raw = extract_grid_filter_params(request)
        filter_model, filter_err = resolve_policy_filter_model(
            filter_model_raw=filter_raw,
            filter_q_raw=filter_q_raw,
            rulebook=instance,
            view_helpers=rulebook_views,
            policy_layout=policy_layout,
        )
        if filter_err:
            return JsonResponse({"error": filter_err}, status=400)

        group_err = validate_policy_group_request(
            request,
            policy_layout=policy_layout,
        )
        if group_err:
            return JsonResponse({"error": group_err}, status=400)

        group_by = parse_policy_group_by(request, policy_layout=policy_layout)
        group_levels = parse_policy_group_levels(request, policy_layout=policy_layout)
        group_mode = parse_group_by_mode(request) if group_levels else ""
        group_mode_secondary = ""
        if len(group_levels) > 1:
            _primary_mode, group_mode_secondary = parse_policy_group_modes(request)
        if group_levels:
            preview_rules = None
            if parse_group_default_expanded(request) == 1:
                preview_rules = policy_grid_filtered_rules(instance)
                if filter_model:
                    preview_rules = policy_grid_filtered_rules_after_ag_filter(
                        preview_rules,
                        instance,
                        filter_model,
                        rulebook_views,
                    )
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
        payload = fetch_policy_grid_page(
            request,
            instance,
            start_row=start_row,
            end_row=end_row,
            filter_model=filter_model,
            group_levels=group_levels,
            group_by=group_by,
            group_mode=group_mode,
            group_mode_secondary=group_mode_secondary,
            expanded_keys=expanded_keys,
            collapsed_keys=collapsed_keys,
            view_helpers=rulebook_views,
            policy_layout=policy_layout,
            use_cached=use_cached,
            refresh_cache=refresh_cache,
        )
        response = JsonResponse(payload)
        response["Cache-Control"] = "private, max-age=0, no-cache"
        return response
