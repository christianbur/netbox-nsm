"""Matrix tab URL and navigation."""

from django.urls import reverse

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase


class RulebookMatrixTabTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rb = Rulebook.objects.create(
            name="Matrix Redirect RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        ensure_system_rulebook_fields(cls.rb)

    def test_matrix_tab_in_rulebook_nav(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rb.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        self.assertIn(matrix_url, content)

    def test_matrix_url_renders_without_mode_param(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        response = self.client.get(matrix_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(">Matrix</strong>", response.content.decode())
        self.assertNotIn('id="matrix-mode"', response.content.decode())

    def test_matrix_tab_hidden_when_disabled(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        self.rb.matrix_tab_enabled = False
        self.rb.save(update_fields=["matrix_tab_enabled"])
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rb.pk])
        content = self.client.get(url).content.decode()
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        self.assertNotIn(matrix_url, content)

    def test_matrix_url_returns_404_when_disabled(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        self.rb.matrix_tab_enabled = False
        self.rb.save(update_fields=["matrix_tab_enabled"])
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        response = self.client.get(matrix_url)
        self.assertEqual(response.status_code, 404)
