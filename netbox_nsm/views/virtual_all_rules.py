"""Virtual All Rules rulebook pages with the same tab structure as policy rulebooks."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.tables import ObjectChangeTable
from extras.tables import JournalEntryTable
from tenancy.tables import ContactAssignmentTable

from netbox_nsm.virtual_rulebook import build_virtual_all_rules_row
from netbox_nsm.virtual_rulebook_detail import build_virtual_rulebook_detail_context
from netbox_nsm.virtual_rulebook_tabs import (
    PRIMARY_TAB_KEY,
    build_virtual_rulebook_tabs,
)

__all__ = (
    "AllRulesRulebookView",
    "AllRulesRulebookRulesView",
    "AllRulesRulebookContactsView",
    "AllRulesRulebookJournalView",
    "AllRulesRulebookChangelogView",
)


class _VirtualAllRulesMixin(LoginRequiredMixin, PermissionRequiredMixin):
    permission_required = "netbox_nsm.view_rulebook"
    tab_key = PRIMARY_TAB_KEY

    def get_virtual_object(self):
        return build_virtual_all_rules_row()

    def build_base_context(self, request):
        instance = self.get_virtual_object()
        return {
            "object": instance,
            "tab_key": self.tab_key,
            "virtual_rulebook_tabs": build_virtual_rulebook_tabs(
                request,
                instance,
                active_key=self.tab_key,
            ),
            "actions": [],
            "rulebook_readonly": True,
        }

    def render_virtual(self, request, extra_context=None):
        ctx = self.build_base_context(request)
        if extra_context:
            ctx.update(extra_context)
        return render(request, self.template_name, ctx)


class AllRulesRulebookView(_VirtualAllRulesMixin, View):
    """Read-only overview tab (same template as normal rulebook detail)."""

    template_name = "netbox_nsm/rulebook_virtual_detail.html"
    tab_key = PRIMARY_TAB_KEY

    def get(self, request):
        return self.render_virtual(
            request,
            build_virtual_rulebook_detail_context(self.get_virtual_object()),
        )


class AllRulesRulebookRulesView(_VirtualAllRulesMixin, View):
    """Rules tab: read-only AG Grid across all policy rulebooks."""

    template_name = "netbox_nsm/rulebook_all_rules.html"
    tab_key = "rules"

    def get(self, request):
        import netbox_nsm.views.rulebook as rulebook_views
        from netbox_nsm.all_rules_grid_service import (
            all_policy_rules_count,
            build_all_rules_grid_config,
            build_all_rules_grid_scaffold,
        )

        return self.render_virtual(
            request,
            {
                "all_rules_count": all_policy_rules_count(),
                "all_rules_grid_config": build_all_rules_grid_config(
                    request, read_only=True
                ),
                "all_rules_grid_payload": build_all_rules_grid_scaffold(rulebook_views),
                "policy_tab_label": _("Rules"),
            },
        )


class _VirtualAllRulesFeatureTabMixin(_VirtualAllRulesMixin):
    """Read-only NetBox feature tabs with empty tables (no DB object for pk=0)."""

    def _empty_table(self, table_class, request):
        table = table_class([])
        table.configure(request)
        return table


class AllRulesRulebookContactsView(_VirtualAllRulesFeatureTabMixin, View):
    permission_required = "tenancy.view_contactassignment"
    template_name = "netbox_nsm/rulebook_all_rules_contacts.html"
    tab_key = "contacts"

    def get(self, request):
        return self.render_virtual(
            request,
            {
                "table": self._empty_table(ContactAssignmentTable, request),
                "feature_tab_label": _("Contacts"),
            },
        )


class AllRulesRulebookJournalView(_VirtualAllRulesFeatureTabMixin, View):
    permission_required = "extras.view_journalentry"
    template_name = "netbox_nsm/rulebook_all_rules_journal.html"
    tab_key = "journal"

    def get(self, request):
        table = self._empty_table(JournalEntryTable, request)
        table.columns.hide("assigned_object_type")
        table.columns.hide("assigned_object")
        return self.render_virtual(
            request,
            {
                "table": table,
                "feature_tab_label": _("Journal"),
            },
        )


class AllRulesRulebookChangelogView(_VirtualAllRulesFeatureTabMixin, View):
    permission_required = "core.view_objectchange"
    template_name = "netbox_nsm/rulebook_all_rules_changelog.html"
    tab_key = "changelog"

    def get(self, request):
        return self.render_virtual(
            request,
            {
                "table": self._empty_table(ObjectChangeTable, request),
                "feature_tab_label": _("Changelog"),
            },
        )
