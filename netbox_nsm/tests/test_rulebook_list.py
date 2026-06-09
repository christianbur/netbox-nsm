"""Rulebook list: COT-backed virtual rows."""

from django.urls import reverse

from utilities.testing import TestCase

from netbox_nsm.models import CotRulebookAssignment
from netbox_nsm.rulebooks.object_actions import AddCotRulebook


class RulebookListViewTests(TestCase):
    def test_list_renders_without_native_rulebooks(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("table", response.context)

    def test_list_hides_add_without_permission(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.context["actions"], [])

    def test_list_shows_add_with_permission(self):
        self.add_permissions("netbox_nsm.view_rulebook", "netbox_nsm.add_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:rulebook_list"))
        self.assertEqual(response.context["actions"], [AddCotRulebook])
        self.assertEqual(
            AddCotRulebook.get_url(CotRulebookAssignment),
            reverse("plugins:netbox_nsm:cot_rulebook_add"),
        )
