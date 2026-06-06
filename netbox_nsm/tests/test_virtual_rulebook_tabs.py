"""Virtual All Rules rulebook tab configuration."""

from django.test import RequestFactory
from django.urls import reverse

from netbox_nsm.virtual_rulebook import build_virtual_all_rules_row
from netbox_nsm.virtual_rulebook_tabs import (
    PRIMARY_TAB_KEY,
    build_virtual_rulebook_tabs,
)
from utilities.testing import TestCase


class VirtualRulebookTabsTests(TestCase):
    def setUp(self):
        super().setUp()
        self.add_permissions(
            "netbox_nsm.view_rulebook",
            "tenancy.view_contactassignment",
            "extras.view_journalentry",
            "core.view_objectchange",
        )

    def test_tabs_match_policy_rulebook_subpages(self):
        request = RequestFactory().get("/")
        request.user = self.user
        virtual = build_virtual_all_rules_row(rule_count=3)
        tabs = build_virtual_rulebook_tabs(request, virtual, active_key="rules")
        labels = [tab["label"] for tab in tabs]
        self.assertEqual(labels, ["Rules", "Contacts", "Journal", "Changelog"])
        rules_tab = next(tab for tab in tabs if tab["key"] == "rules")
        self.assertTrue(rules_tab["is_active"])
        self.assertEqual(
            rules_tab["url"],
            reverse("plugins:netbox_nsm:all_rules_rules"),
        )

    def test_detail_is_not_in_dynamic_tabs(self):
        request = RequestFactory().get("/")
        request.user = self.user
        tabs = build_virtual_rulebook_tabs(
            request,
            build_virtual_all_rules_row(),
            active_key=PRIMARY_TAB_KEY,
        )
        self.assertEqual(
            [tab["key"] for tab in tabs],
            ["rules", "contacts", "journal", "changelog"],
        )

    def test_matrix_tab_is_not_present(self):
        request = RequestFactory().get("/")
        request.user = self.user
        tabs = build_virtual_rulebook_tabs(
            request,
            build_virtual_all_rules_row(),
        )
        self.assertNotIn("matrix", [tab["key"] for tab in tabs])
