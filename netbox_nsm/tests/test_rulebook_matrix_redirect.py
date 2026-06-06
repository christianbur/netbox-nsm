"""Matrix tab removed from rulebook nav; legacy /matrix/ URL redirects to Rules."""

from django.urls import reverse

from netbox_nsm.models import Rulebook, RulebookTypeChoices
from netbox_nsm.rulebook_field_utils import ensure_system_rulebook_fields
from utilities.testing import TestCase


class RulebookMatrixRedirectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rb = Rulebook.objects.create(
            name="Matrix Redirect RB",
            rulebook_type=RulebookTypeChoices.SECURITY_RULES,
        )
        ensure_system_rulebook_fields(cls.rb)

    def test_matrix_tab_not_in_rulebook_nav(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse("plugins:netbox_nsm:rulebook", args=[self.rb.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        self.assertNotIn(matrix_url, content)

    def test_matrix_url_redirects_to_rules_preserving_query(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        matrix_url = reverse("plugins:netbox_nsm:rulebook_matrix", args=[self.rb.pk])
        response = self.client.get(
            f"{matrix_url}?obj_type=10&mode=undirected&src_q=dmz"
        )
        self.assertEqual(response.status_code, 301)
        expected = reverse("plugins:netbox_nsm:rulebook_rules", args=[self.rb.pk])
        self.assertEqual(
            response["Location"],
            f"{expected}?obj_type=10&mode=undirected&src_q=dmz",
        )
