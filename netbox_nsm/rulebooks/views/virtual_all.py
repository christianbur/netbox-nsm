"""Virtual All Rules rulebook pages with the same tab structure as rulebooks."""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from django.views import View

from core.tables import ObjectChangeTable
from extras.tables import JournalEntryTable
from tenancy.tables import ContactAssignmentTable

from netbox_nsm.rulebooks.virtual_all import build_virtual_all_rules_row
from netbox_nsm.rulebooks.virtual_all_detail import build_virtual_rulebook_detail_context
from netbox_nsm.rulebooks.virtual_all_tabs import (
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
    """Read-only rules tab with the same HTML table as rulebooks."""

    template_name = "netbox_nsm/rulebook_all_rules_rules.html"
    tab_key = "rules"
    permission_required = "netbox_nsm.view_rulebook"

    def get(self, request):
        from netbox_nsm.rulebooks.virtual_all_rules_tab import (
            build_virtual_all_rules_rules_tab_context,
        )

        return self.render_virtual(
            request,
            build_virtual_all_rules_rules_tab_context(
                request,
                self.get_virtual_object(),
            ),
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
