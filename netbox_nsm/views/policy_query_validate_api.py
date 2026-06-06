from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.policy_grid_payload import (
    build_ag_grid_filter_model_from_query_text,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    serialize_ag_grid_filter_to_nsm_q,
)
from netbox_nsm.query import RulebookContext

__all__ = ("RulebookPolicyQueryValidateApiView",)


class RulebookPolicyQueryValidateApiView(LoginRequiredMixin, View):
    """
    Validate / convert policy filter query text for the Rules grid search bar.

    GET /plugins/netbox-nsm/api/rulebooks/<pk>/policy-query-validate/?q=...
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rulebook"):
            return HttpResponseForbidden()

        instance = get_object_or_404(Rulebook, pk=pk)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return JsonResponse({"error": "not a policy rulebook"}, status=404)

        import netbox_nsm.views.rulebook as rulebook_views

        raw_q = request.GET.get("q", "").strip()
        if not raw_q:
            return JsonResponse({"valid": True, "empty": True, "filterModel": {}})

        context = RulebookContext(instance)
        policy_layout = rulebook_views._build_grouped_policy_table_data([], instance)[
            "policy_layout"
        ]
        filter_model, err = build_ag_grid_filter_model_from_query_text(
            raw_q, policy_layout, context
        )
        if err:
            return JsonResponse({"valid": False, "error": err})

        column_map = build_filter_column_query_map(policy_layout, context)
        shorthand_names = build_filter_column_shorthand_names(column_map, policy_layout)
        normalized = serialize_ag_grid_filter_to_nsm_q(
            filter_model,
            column_map,
            shorthand_names=shorthand_names,
        )

        return JsonResponse(
            {
                "valid": True,
                "empty": not filter_model,
                "filterModel": filter_model,
                "normalized": normalized,
            }
        )
