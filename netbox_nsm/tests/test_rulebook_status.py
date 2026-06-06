"""Rulebook status field."""

from django.test import SimpleTestCase

from netbox_nsm.models.rulebook import RulebookStatusChoices
from netbox_nsm.rulebook_status import (
    RULEBOOK_STATUS_BADGE_CLASS,
    rulebook_status_badge_html,
)


class RulebookStatusTests(SimpleTestCase):
    def test_all_status_values(self):
        self.assertEqual(len(RulebookStatusChoices.choices), 4)
        self.assertEqual(RulebookStatusChoices.ACTIVE, "active")
        self.assertEqual(RulebookStatusChoices.CONTAINER, "container")

    def test_badge_html_active(self):
        html = rulebook_status_badge_html(RulebookStatusChoices.ACTIVE)
        self.assertIn("text-bg-success", html)
        self.assertIn(RULEBOOK_STATUS_BADGE_CLASS[RulebookStatusChoices.ACTIVE], html)
