"""Tests for Object Config UI views (merge-aware comments writes)."""

import yaml
from django.urls import reverse

from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms
from utilities.testing import TestCase


class ObjectConfigViewMergeTests(TestCase):
    def setUp(self):
        super().setUp()
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")
        self.cot = CustomObjectType.objects.create(
            name="nsm_zone_merge_test",
            slug="nsm_zone",
            verbose_name="Zones",
        )
        grant_nsm_config_perms(self, view=True, change=True)

    def test_edit_preserves_non_nsm_config_yaml(self):
        self.cot.comments = (
            "operator_note: keep-me\n"
            "nsm_config:\n"
            "  - rule_view:\n"
            "      sort_order: 5\n"
            "      display_template: '{name}'\n"
        )
        self.cot.save(update_fields=["comments"])

        response = self.client.post(
            reverse("plugins:netbox_nsm:objectconfig_edit", args=["nsm_zone"]),
            {"sort_order": 9, "display_template": "{name}"},
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        document = yaml.safe_load(self.cot.comments)
        self.assertEqual(document["operator_note"], "keep-me")
        self.assertEqual(
            document["nsm_config"][0]["rule_view"]["sort_order"],
            9,
        )

    def test_delete_only_clears_nsm_config_block(self):
        self.cot.comments = (
            "operator_note: keep-me\n"
            "nsm_config:\n"
            "  - rule_view:\n"
            "      sort_order: 1\n"
        )
        self.cot.save(update_fields=["comments"])

        response = self.client.post(
            reverse("plugins:netbox_nsm:objectconfig_delete", args=["nsm_zone"]),
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        document = yaml.safe_load(self.cot.comments)
        self.assertEqual(document, {"operator_note": "keep-me"})
        self.assertNotIn("nsm_config", document)
