"""Rulebook list: hierarchy, status badges, rule-count pills."""

from django.urls import reverse

from netbox_nsm.models import Rulebook, RulebookStatusChoices, RulebookTypeChoices
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase


class RulebookListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = Rulebook.objects.create(
            name="Corp Policy",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status=RulebookStatusChoices.CONTAINER,
        )
        cls.child = Rulebook.objects.create(
            name="Branch FW",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
            status=RulebookStatusChoices.ACTIVE,
            parent=cls.parent,
        )
        ensure_system_rulebook_fields(cls.child)

    def test_list_shows_status_badges_and_rule_count_pill(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("text-bg-success", content)
        self.assertIn("text-bg-secondary", content)
        self.assertIn("nsm-rule-pill--counter", content)
        self.assertIn("Branch FW", content)
        self.assertIn("Corp Policy", content)
        self.assertNotIn('aria-label="Select all"', content)
        self.assertNotIn("Delete Selected", content)

    def test_list_hides_delete_action_when_rulebook_has_rules(self):
        rb = Rulebook.objects.create(
            name="list-del-blocked",
            rulebook_type="security_rules",
        )
        Rule.objects.create(rulebook=rb, name="blocking-rule", index=10)
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.delete_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        content = response.content.decode()
        delete_url = reverse("plugins:netbox_nsm:rulebook_delete", args=[rb.pk])
        self.assertNotIn(f'href="{delete_url}', content)

    def test_list_orders_parent_before_child(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        table = response.context["table"]
        names = [row.record.name for row in table.rows]
        self.assertIn("Corp Policy", names)
        self.assertIn("Branch FW", names)
        self.assertLess(names.index("Corp Policy"), names.index("Branch FW"))

    def test_list_shows_hierarchy_marker_for_child(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        content = response.content.decode()
        self.assertIn('class="record-depth"', content)
        child_pos = content.index("Branch FW")
        depth_pos = content.rfind('class="record-depth"', 0, child_pos)
        self.assertGreater(depth_pos, -1)
