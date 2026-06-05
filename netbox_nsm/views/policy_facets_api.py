from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.policy_facets import compute_policy_facets

__all__ = ("RulebookPolicyFacetsApiView",)


class RulebookPolicyFacetsApiView(LoginRequiredMixin, View):
    """
    Lazy-load filter facet HTML for the policy table sidebar.

    GET /plugins/netbox-nsm/api/rulebooks/<pk>/policy-facets/?nsm_q=...
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rulebook"):
            return HttpResponseForbidden()

        instance = get_object_or_404(Rulebook, pk=pk)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return HttpResponseNotFound()

        nsm_q, facets = compute_policy_facets(request, instance)
        html = render_to_string(
            "netbox_nsm/inc/rulebook_facet_sections.html",
            {
                "nsm_facets": facets,
                "nsm_q": nsm_q,
                "policy_clear_url": reverse(
                    "plugins:netbox_nsm:rulebook_rules", args=[instance.pk]
                ),
            },
            request=request,
        )
        return HttpResponse(html, content_type="text/html; charset=utf-8")
