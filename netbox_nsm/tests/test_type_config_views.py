"""Tests for Object Config UI views (merge-aware comments writes)."""

import yaml
from django.urls import reverse

from netbox_nsm.tests.rulebook_permission_helpers import grant_nsm_config_perms
from utilities.testing import TestCase


def _parse_comments_document(text: str) -> dict:
    from netbox_nsm.type_metadata.config import (
        _load_yaml_document,
        parse_nsm_config_document_from_comments,
    )

    raw = _load_yaml_document(text)
    if not isinstance(raw, dict):
        return {}
    merged = parse_nsm_config_document_from_comments(text) or {}
    if "operator_note" in raw:
        merged = {"operator_note": raw["operator_note"], **merged}
    return merged


def _edit_post_data(**overrides):
    data = {
        "role": "zone",
        "sort_order": 9,
        "display_template": "{{ name }}",
    }
    data.update(overrides)
    return data


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
            "      display_template: '{{ name }}'\n"
        )
        self.cot.save(update_fields=["comments"])

        response = self.client.post(
            reverse("plugins:netbox_nsm:typemetadata_edit", args=["nsm_zone"]),
            _edit_post_data(),
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        document = _parse_comments_document(self.cot.comments)
        self.assertEqual(document["operator_note"], "keep-me")
        self.assertEqual(document["rule_view"]["sort_order"], 9)

    def test_edit_persists_areas(self):
        response = self.client.post(
            reverse("plugins:netbox_nsm:typemetadata_edit", args=["nsm_zone"]),
            _edit_post_data(areas=["srcdst"]),
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        document = _parse_comments_document(self.cot.comments)
        rule_view = document["rule_view"]
        self.assertEqual(rule_view["areas"], ["srcdst"])
        self.assertNotIn("links", document)

    def test_delete_only_clears_nsm_config_block(self):
        self.cot.comments = (
            "operator_note: keep-me\n"
            "nsm_config:\n"
            "  - rule_view:\n"
            "      sort_order: 1\n"
        )
        self.cot.save(update_fields=["comments"])

        response = self.client.post(
            reverse("plugins:netbox_nsm:typemetadata_delete", args=["nsm_zone"]),
        )
        self.assertEqual(response.status_code, 302)
        self.cot.refresh_from_db()
        self.assertNotIn("nsm_config:", self.cot.comments or "")
        self.assertIn("operator_note: keep-me", self.cot.comments or "")
