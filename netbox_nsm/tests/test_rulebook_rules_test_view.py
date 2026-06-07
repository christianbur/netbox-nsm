"""Legacy /test/ URL redirects to /rules/."""

from django.urls import reverse

from netbox_nsm.models import Rulebook
from utilities.testing import TestCase


class RulebookRulesTestRedirectTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rulebook = Rulebook.objects.create(
            name="Rules Redirect Test",
            rulebook_type="security_rules",
        )

    def test_test_route_redirects_to_rules(self):
        self.add_permissions("netbox_nsm.view_rulebook")
        url = reverse(
            "plugins:netbox_nsm:rulebook_test",
            args=[self.rulebook.pk],
        )
        response = self.client.get(f"{url}?cell_mode=compact", follow=False)
        self.assertEqual(response.status_code, 301)
        location = response["Location"]
        self.assertIn(f"/rulebooks/{self.rulebook.pk}/rules/", location)
        self.assertIn("cell_mode=compact", location)
