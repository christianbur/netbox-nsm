"""Rule clone URL and rules-table action menu."""

from django.test import SimpleTestCase
from django.urls import reverse

from netbox_nsm.models import Rule, Rulebook, RulebookTypeChoices
from netbox_nsm.rule_copy import COPY_RULE_PARAM, rule_clone_add_url
from netbox_nsm.rulebook_rules_tab import _render_actions_cell_html
from utilities.testing import TestCase


class RuleCloneUrlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="clone-src-rb",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        cls.rule = Rule.objects.create(
            rulebook=cls.rulebook,
            name="clone-src-rule",
            index=10,
            enabled=True,
            description="keep me",
        )

    def test_clone_url_points_to_add_with_copy_from(self):
        url = rule_clone_add_url(self.rule)
        self.assertIn(reverse("plugins:netbox_nsm:rule_add"), url)
        self.assertIn(f"{COPY_RULE_PARAM}={self.rule.pk}", url)
        self.assertIn("rulebook=", url)
        self.assertNotIn("name=", url)


class RuleActionsCellHtmlTests(SimpleTestCase):
    def test_renders_edit_with_dropdown_clone_delete(self):
        html = _render_actions_cell_html(
            "/edit/",
            "/delete/",
            "/clone/",
            can_change=True,
            can_delete=True,
            can_add=True,
        )
        self.assertIn("btn btn-sm btn-warning nsm-ag-action-edit", html)
        self.assertIn("dropdown-toggle", html)
        self.assertIn("dropdown-menu", html)
        self.assertIn("nsm-ag-action-delete", html)
        self.assertIn("nsm-ag-action-clone", html)
        self.assertNotIn("btn btn-danger nsm-ag-action-delete", html)
        self.assertNotIn("btn btn-primary nsm-ag-action-clone", html)

    def test_edit_only_when_no_dropdown_actions(self):
        html = _render_actions_cell_html(
            "/edit/",
            "/delete/",
            None,
            can_change=True,
            can_delete=False,
            can_add=False,
        )
        self.assertIn("btn btn-sm btn-warning", html)
        self.assertNotIn("dropdown-menu", html)
