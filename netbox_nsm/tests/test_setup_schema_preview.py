"""View tests for schema bundle detail preview UI."""

import json

from django.test import override_settings
from django.urls import reverse

from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms
from utilities.testing import TestCase

_SETUP_PLUGINS_CONFIG = {
    "netbox_nsm": {
        "setup_menu": True,
        "setup_allow_destructive_actions": True,
    },
    "netbox_branching": {},
}


@override_settings(PLUGINS_CONFIG=_SETUP_PLUGINS_CONFIG)
class SetupSchemaPreviewViewTests(TestCase):
    def test_preview_post_returns_json(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("cot_diff", data)
        self.assertIn("choice_set_diff", data)
        self.assertIn("object_diff", data)
        self.assertIn("destructive_blocked", data)
        self.assertIn("metadata", data)
        json.dumps(data)

    def test_preview_respects_allow_destructive_flag(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        blocked = self.client.post(url).json()["destructive_blocked"]
        allowed = self.client.post(url, {"allow_destructive": "1"}).json()[
            "destructive_blocked"
        ]
        if blocked:
            self.assertFalse(allowed)

    def test_detail_page_includes_preview_button(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:bundle_detail", args=["nsm_schema"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bundlePreviewToggle")
        self.assertContains(response, "bundlePreviewPanel")
        self.assertContains(response, "Preview changes")

    def test_preview_requires_view_permission(self):
        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        response = self.client.post(url)
        self.assertIn(response.status_code, (403, 302))
