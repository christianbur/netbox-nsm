"""UI tests for the COT rulebook creation wizard."""

from django.urls import reverse

from netbox_nsm.rulebooks.templates import default_rulebook_schema_yaml
from utilities.testing import TestCase


class CotRulebookCreateViewTests(TestCase):
    def test_get_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 302)

    def test_get_forbidden_without_add_permission(self):
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 403)

    def test_get_renders_wizard_with_add_permission(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("form", response.context)
        self.assertContains(response, "Add Rulebook")

    def test_get_renders_define_and_preview_tabs(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        url = reverse("plugins:netbox_nsm:cot_rulebook_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "YAML")
        self.assertContains(response, "Preview")
        self.assertContains(response, "schema-define")
        self.assertContains(response, "schema-preview")
        self.assertContains(response, "name: source")

    def test_get_shows_columns_from_default_schema(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        url = reverse("plugins:netbox_nsm:cot_rulebook_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Source")
        self.assertContains(response, "Destination")
        self.assertContains(response, "Zone, Label, Address, Address Group")

    def test_get_prefills_default_schema_yaml(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertEqual(
            response.context["form"]["schema_yaml"].value().splitlines()[0],
            default_rulebook_schema_yaml().splitlines()[0],
        )

    def test_get_includes_schema_validity_indicator(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        response = self.client.get(reverse("plugins:netbox_nsm:cot_rulebook_add"))
        self.assertContains(response, "nsm-schema-yaml-validity")
        self.assertContains(
            response,
            reverse("plugins:netbox_nsm:cot_rulebook_schema_validate"),
        )

    def test_schema_validate_endpoint_accepts_valid_yaml(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        url = reverse("plugins:netbox_nsm:cot_rulebook_schema_validate")
        response = self.client.post(
            url,
            {
                "schema_yaml": default_rulebook_schema_yaml(),
                "verbose_name": "Bench Addresses",
                "name": "bench_addresses",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"valid": True})

    def test_schema_validate_endpoint_rejects_invalid_yaml(self):
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        url = reverse("plugins:netbox_nsm:cot_rulebook_schema_validate")
        response = self.client.post(
            url,
            {"schema_yaml": "not: [valid"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["valid"])
        self.assertIn("error", payload)

    def test_create_access_requires_add_customobjecttype(self):
        from netbox_nsm.rulebooks.permissions import can_create_rulebook

        self.assertFalse(can_create_rulebook(self.user))
        self.add_permissions("netbox_custom_objects.add_customobjecttype")
        self.user = self.user.__class__.objects.get(pk=self.user.pk)
        self.assertTrue(can_create_rulebook(self.user))
