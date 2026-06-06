from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from django.views import View

from netbox_nsm.policy_grid_filter import (
    ALL_RULES_FILTER_QUERY_FORMAT,
    validate_all_rules_filter_query,
)

__all__ = ("AllRulesQueryValidateApiView",)


class AllRulesQueryValidateApiView(LoginRequiredMixin, View):
    """
    Validate all-rules filter query text.

    Canonical params: ``rulebook`` or ``rulebook_id`` plus unscoped ``filter_q`` / ``q``.

    Deprecated scoped-only ``q`` / ``filter_q`` (colon syntax) still accepted.
    Bracket form ``["Rulebook", ...]`` is rejected.
    """

    def get(self, request):
        if not request.user.has_perm("netbox_nsm.view_rule"):
            return HttpResponseForbidden()

        import netbox_nsm.views.rulebook as rulebook_views

        has_scope = any(
            (request.GET.get(key) or "").strip()
            for key in ("filter_q", "q", "rulebook", "rulebook_id")
        )
        if not has_scope:
            return JsonResponse(
                {"valid": True, "empty": True, "filterModel": {}, "filterQ": ""}
            )

        payload = validate_all_rules_filter_query(
            view_helpers=rulebook_views,
            request=request,
        )
        if not payload.get("valid") and "expectedFormat" not in payload:
            payload["expectedFormat"] = ALL_RULES_FILTER_QUERY_FORMAT
        status = 200 if payload.get("valid") else 400
        return JsonResponse(payload, status=status)
