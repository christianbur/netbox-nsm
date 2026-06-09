"""UI tests for the COT rulebook creation wizard."""

from django.urls import reverse

from utilities.testing import TestCase


class CotRulebookCreateViewTests(TestCase):
    def test_get_requires_login(self):
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 302)

    def test_get_forbidden_without_add_permission(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 403)

    def test_get_renders_wizard_with_add_permission(self):
        self.add_permissions("netbox_nsm.add_rulebook")
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Add Rulebook")

    def test_get_shows_columns_for_selected_template(self):
        self.add_permissions("netbox_nsm.add_rulebook")
        url = reverse("plugins:netbox_nsm:cot_rulebook_add")
        response = self.client.get(
            url,
            {"template_slug": "nsm_rb_0002_template"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Addresses (Source)")
        self.assertNotContains(response, "Zones (Source)")

        response = self.client.get(
            url,
            {"template_slug": "nsm_rb_0003_template"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zones (Source)")
        self.assertNotContains(response, "Addresses (Source)")

    def test_htmx_template_change_returns_partial_columns(self):
        self.add_permissions("netbox_nsm.add_rulebook")
        url = reverse("plugins:netbox_nsm:cot_rulebook_add")
        response = self.client.get(
            url,
            {"template_slug": "nsm_rb_0004_template"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Labels (Source)")
        self.assertNotContains(response, "Zones (Source)")
        self.assertNotContains(response, "Addresses (Source)")
