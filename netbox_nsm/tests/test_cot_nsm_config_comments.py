"""COT comments field: nsm_config YAML sync from bundle metadata."""

from django.test import TestCase

from netbox_nsm.type_metadata.config import apply_schema_bundle_metadata, metadata_block_for_cot_slug
from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS, TYPECONFIG_LIST_EXCLUDED_SLUGS


class CotNsmConfigCommentsApplyDocumentTests(TestCase):
    def test_portable_schema_excludes_comments_field(self):
        from netbox_nsm.bundles.schema_builder import build_schema_document

        document = build_schema_document()
        for type_def in document["types"]:
            self.assertNotIn("comments", type_def)

    def test_apply_schema_bundle_metadata_restores_comments(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        cot, _ = CustomObjectType.objects.get_or_create(
            slug="nsm_zone",
            defaults={"name": "nsm_zone", "verbose_name": "Zones"},
        )
        counts = apply_schema_bundle_metadata()
        self.assertGreaterEqual(counts.get("types", 0), 1)
        cot.refresh_from_db()
        self.assertIn("nsm_config:", cot.comments)

        cot.comments = ""
        cot.save(update_fields=["comments"])
        counts = apply_schema_bundle_metadata()
        self.assertGreaterEqual(counts.get("types", 0), 1)
        cot.refresh_from_db()
        self.assertIn("nsm_config:", cot.comments)

    def test_apply_schema_bundle_metadata_populates_ui_cots(self):
        try:
            from netbox_custom_objects.models import CustomObjectType
        except ImportError:
            self.skipTest("netbox_custom_objects not installed")

        for slug in REQUIRED_COT_SLUGS:
            CustomObjectType.objects.get_or_create(
                slug=slug,
                defaults={"name": slug, "verbose_name": slug},
            )

        counts = apply_schema_bundle_metadata()
        expected = len(
            [
                slug
                for slug in REQUIRED_COT_SLUGS
                if slug not in TYPECONFIG_LIST_EXCLUDED_SLUGS
                and metadata_block_for_cot_slug(slug)
            ]
        )
        self.assertGreaterEqual(counts.get("types", 0), expected)

        for slug in REQUIRED_COT_SLUGS:
            if slug in TYPECONFIG_LIST_EXCLUDED_SLUGS:
                continue
            cot = CustomObjectType.objects.get(slug=slug)
            self.assertIn("nsm_config:", cot.comments)

    def test_bundle_service_metadata_has_port_range_template(self):
        from netbox_nsm.core.display_template import SERVICE_DISPLAY_TEMPLATE

        block = metadata_block_for_cot_slug("nsm_service")
        self.assertIsNotNone(block)
        rule_view = block.get("rule_view") or {}
        self.assertEqual(rule_view.get("display_template"), SERVICE_DISPLAY_TEMPLATE)
