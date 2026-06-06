from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.rulebook_rules_grid_payload import (
    build_ag_grid_filter_model_from_query_text,
    build_filter_column_query_map,
    build_filter_column_shorthand_names,
    serialize_ag_grid_filter_to_nsm_q,
)
from netbox_nsm.query import RulebookContext

__all__ = ("RulebookRulesGridValidateApiView",)


class RulebookRulesGridValidateApiView(LoginRequiredMixin, View):
    """
    Validate / convert Rules grid filter query text for the search bar.

    GET /plugins/netbox-nsm/api/rulebooks/<pk>/rules-grid/validate/?q=...
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rulebook"):
            return HttpResponseForbidden()

        instance = get_object_or_404(Rulebook, pk=pk)
        if instance.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
            return JsonResponse({"error": "not a security rules rulebook"}, status=404)

        import netbox_nsm.views.rulebook as rulebook_views

        raw_q = request.GET.get("q", "").strip()
        if not raw_q:
            return JsonResponse({"valid": True, "empty": True, "filterModel": {}})

        context = RulebookContext(instance)
        rules_layout = rulebook_views._build_grouped_rules_table_data([], instance)[
            "rules_layout"
        ]
        filter_model, err = build_ag_grid_filter_model_from_query_text(
            raw_q, rules_layout, context
        )
        if err:
            return JsonResponse({"valid": False, "error": err})

        column_map = build_filter_column_query_map(rules_layout, context)
        shorthand_names = build_filter_column_shorthand_names(column_map, rules_layout)
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
