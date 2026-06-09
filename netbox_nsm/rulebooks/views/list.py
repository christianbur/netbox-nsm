"""COT rulebook list view (native ORM rulebooks removed)."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.views import View

from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.rulebooks.cot_hierarchy import build_cot_rulebook_list_rows
from netbox_nsm.rulebooks.object_actions import AddCotRulebook
from netbox_nsm.tables import RulebookTable

__all__ = ("RulebookListView",)


def _permitted_rulebook_list_actions(user):
    if user.has_perm("netbox_nsm.add_rulebook"):
        return [AddCotRulebook]
    return []


class RulebookListView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.view_rulebook"
    template_name = "netbox_nsm/rulebook_list.html"

    def get(self, request):
        rows = build_cot_rulebook_list_rows()

        table = RulebookTable(rows)
        table.configure(request)

        return render(
            request,
            self.template_name,
            {
                "table": table,
                "actions": _permitted_rulebook_list_actions(request.user),
                # Proxy for generic/object_list.html (rows are VirtualCotRulebook).
                "model": CotRulebookAssignment,
            },
        )
