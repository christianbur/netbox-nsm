"""COT rulebook list view (native ORM rulebooks removed)."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views import View

from netbox_nsm.rulebooks.cot_hierarchy import build_cot_rulebook_list_rows
from netbox_nsm.rulebooks.object_actions import AddCotRulebook
from netbox_nsm.rulebooks.permissions import (
    RulebookListProxy,
    can_create_rulebook,
    filter_viewable_rulebook_rows,
    user_can_access_rulebooks,
)
from netbox_nsm.tables import RulebookTable

__all__ = ("RulebookListView",)


def _permitted_rulebook_list_actions(user):
    if can_create_rulebook(user):
        return [AddCotRulebook]
    return []


class RulebookListView(LoginRequiredMixin, View):
    template_name = "netbox_nsm/rulebook_list.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not user_can_access_rulebooks(request.user):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        rows = filter_viewable_rulebook_rows(
            build_cot_rulebook_list_rows(),
            request.user,
        )

        table = RulebookTable(rows)
        table.configure(request)

        return render(
            request,
            self.template_name,
            {
                "table": table,
                "actions": _permitted_rulebook_list_actions(request.user),
                "model": RulebookListProxy,
            },
        )
