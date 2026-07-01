"""Tests for ``nsm_config`` REST API (CustomObjectType.comments)."""

from django.urls import reverse

from netbox_nsm.type_metadata.config import parse_nsm_config_document_from_comments

from netbox_nsm.rulebooks.templates import RULEBOOK_GROUP
from utilities.testing import APITestCase
from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms, grant_rulebook_cot_perms


class NsmConfigApiTests(APITestCase):
    def setUp(self):
        super().setUp()
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox-custom-objects not installed")
        self.zone_cot = CustomObjectType.objects.create(
            name="nsm_zone_api_test",
            slug="nsm_zone_api_test",
            verbose_name="Zone API Test",
            description="",
            group_name="NSM Panel",
        )
        self.rulebook_cot = CustomObjectType.objects.create(
            name="nsm_rb_api_test",
            slug="nsm_rb_api_test",
            verbose_name="Rulebook API Test",
            description="",
            group_name=RULEBOOK_GROUP,
        )

    def _url(self, slug: str) -> str:
        return reverse(
            "plugins-api:netbox_nsm-api:nsmconfig-detail",
            kwargs={"slug": slug},
        )

    def test_get_requires_permission(self):
        self.client.force_authenticate(self.user)
        response = self.client.get(self._url(self.zone_cot.slug))
        self.assertEqual(response.status_code, 403)

    def test_get_returns_nsm_config(self):
        self.zone_cot.comments = "nsm_config:\n  - rule_view:\n      sort_order: 7\n"
        self.zone_cot.save(update_fields=["comments"])
        grant_nsm_config_perms(self, view=True)
        self.client.force_authenticate(self.user)

        response = self.client.get(self._url(self.zone_cot.slug))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.zone_cot.slug)
        self.assertEqual(response.data["nsm_config"]["rule_view"]["sort_order"], 7)
        self.assertIn("nsm_config:", response.data["comments"])

    def test_patch_updates_rule_view(self):
        grant_nsm_config_perms(self, change=True)
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self._url(self.zone_cot.slug),
            {"rule_view": {"sort_order": 15, "display_template": "{{ name }}"}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.zone_cot.refresh_from_db()
        parsed = parse_nsm_config_document_from_comments(self.zone_cot.comments)
        self.assertEqual(parsed["rule_view"]["sort_order"], 15)

    def test_patch_rulebook_preserves_rule_view(self):
        self.zone_cot.comments = (
            "nsm_config:\n  - rule_view:\n      sort_order: 3\n      display_template: '{{ name }}'\n"
        )
        self.zone_cot.save(update_fields=["comments"])
        self.rulebook_cot.comments = self.zone_cot.comments
        self.rulebook_cot.save(update_fields=["comments"])
        grant_rulebook_cot_perms(self, self.rulebook_cot, change=True)
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self._url(self.rulebook_cot.slug),
            {"rulebook": {"matrix_tab_enabled": False}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.rulebook_cot.refresh_from_db()
        document = parse_nsm_config_document_from_comments(self.rulebook_cot.comments)
        self.assertIn("rule_view", document)
        self.assertIn("rulebook", document)

    def test_delete_clears_nsm_config(self):
        self.zone_cot.comments = "nsm_config:\n  - rule_view:\n      sort_order: 1\n"
        self.zone_cot.save(update_fields=["comments"])
        grant_nsm_config_perms(self, change=True)
        self.client.force_authenticate(self.user)

        response = self.client.delete(self._url(self.zone_cot.slug))
        self.assertEqual(response.status_code, 204)
        self.zone_cot.refresh_from_db()
        self.assertEqual(self.zone_cot.comments, "")

    def test_patch_invalid_parent_slug_returns_400(self):
        # Model-level ValidationError (invalid rulebook parent) must surface as
        # HTTP 400, not a 500 server error.
        grant_rulebook_cot_perms(self, self.rulebook_cot, change=True)
        self.client.force_authenticate(self.user)

        response = self.client.patch(
            self._url(self.rulebook_cot.slug),
            {"rulebook": {"parent_slug": "nsm_rb_does_not_exist"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_slug_returns_404(self):
        grant_nsm_config_perms(self, view=True)
        self.client.force_authenticate(self.user)
        response = self.client.get(self._url("does-not-exist"))
        self.assertEqual(response.status_code, 404)
