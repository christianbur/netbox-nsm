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

    def test_list_orders_parent_before_child(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        table = response.context["table"]
        names = [
            row.record.name
            for row in table.rows
        ]
        self.assertIn("Corp Policy", names)
        self.assertIn("Branch FW", names)
        self.assertLess(names.index("Corp Policy"), names.index("Branch FW"))

    def test_list_shows_hierarchy_marker_for_child(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        content = response.content.decode()
        self.assertIn("nsm-rb-hierarchy-dot", content)
        child_pos = content.index("Branch FW")
        dot_pos = content.rfind("nsm-rb-hierarchy-dot", 0, child_pos)
        self.assertGreater(dot_pos, -1)
