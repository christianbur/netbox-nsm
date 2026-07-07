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
        self.assertContains(response, "Refresh preview")
        self.assertContains(response, "bundleJsonEditor")
        self.assertContains(response, "bundle_preview.js")
        self.assertContains(response, "NSMBundlePreview.init")
        self.assertContains(response, "bundlePreviewI18n")
        self.assertNotContains(response, 'id="bundlePreviewPanel" class="card mb-3 nsm-bundle-preview-panel d-none"')
        self.assertContains(response, 'id="bundlePreviewLoading" class="text-center py-4 text-muted"')

    def test_detail_page_i18n_json_is_valid(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:bundle_detail", args=["nsm_schema"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        import re

        html = response.content.decode()
        match = re.search(
            r'<script id="bundlePreviewI18n"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "bundlePreviewI18n script block missing")
        json.loads(match.group(1).strip())

    def test_preview_accepts_edited_bundle_json(self):
        grant_nsm_config_perms(self, view=True)
        from netbox_nsm.bundles.dispatch import load_bundle
        from netbox_nsm.bundles.paths import bundle_json_path

        bundle = load_bundle(bundle_json_path("nsm_schema"))
        service_type = next(
            t for t in bundle.get("types", []) if t.get("slug") == "nsm_service"
        )
        field_names = {f["name"] for f in service_type.get("fields", [])}
        self.assertIn("port_end", field_names)

        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        response = self.client.post(
            url,
            {"bundle_json": json.dumps(bundle)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("cot_diff", response.json())

    def test_preview_rejects_invalid_bundle_json(self):
        grant_nsm_config_perms(self, view=True)
        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        response = self.client.post(url, {"bundle_json": "{not-json"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_preview_requires_view_permission(self):
        url = reverse("plugins:netbox_nsm:bundle_preview", args=["nsm_schema"])
        response = self.client.post(url)
        self.assertIn(response.status_code, (403, 302))
