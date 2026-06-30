"""COT comments field: nsm_config YAML sync and backfill."""

from django.test import TestCase

from netbox_nsm.type_metadata.export import (
    backfill_cot_nsm_config_comments,
    sync_cot_nsm_config_comments,
)
from netbox_nsm.type_metadata.specs import TYPECONFIG_LIST_EXCLUDED_SLUGS, TYPECONFIG_UI_SPECS


class CotNsmConfigCommentsApplyDocumentTests(TestCase):
    def test_portable_schema_excludes_comments_field(self):
        from netbox_nsm.bundles.schema_builder import build_schema_document

        document = build_schema_document()
        for type_def in document["types"]:
            self.assertNotIn("comments", type_def)

    def test_sync_restores_comments_after_manual_clear(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        spec = next(s for s in TYPECONFIG_UI_SPECS if s["slug"] == "nsm_zone")
        cot, _ = CustomObjectType.objects.get_or_create(
            slug="nsm_zone",
            defaults={"name": "nsm_zone", "verbose_name": "Zones"},
        )
        sync_cot_nsm_config_comments(cot, spec=spec)
        cot.refresh_from_db()
        self.assertIn("nsm_config:", cot.comments)

        cot.comments = ""
        cot.save(update_fields=["comments"])
        sync_cot_nsm_config_comments(cot, spec=spec)
        cot.refresh_from_db()
        self.assertIn("nsm_config:", cot.comments)

    def test_backfill_populates_empty_ui_cots(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        for spec in TYPECONFIG_UI_SPECS:
            CustomObjectType.objects.get_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["slug"],
                    "verbose_name": spec["label"],
                },
            )

        updated = backfill_cot_nsm_config_comments()
        expected = len(
            [spec for spec in TYPECONFIG_UI_SPECS if spec["slug"] not in TYPECONFIG_LIST_EXCLUDED_SLUGS]
        )
        self.assertEqual(updated, expected)

        for spec in TYPECONFIG_UI_SPECS:
            if spec["slug"] in TYPECONFIG_LIST_EXCLUDED_SLUGS:
                continue
            cot = CustomObjectType.objects.get(slug=spec["slug"])
            self.assertIn("nsm_config:", cot.comments)
            self.assertNotIn(f"# {spec['label']}", cot.comments)
