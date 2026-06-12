"""COT comments field: nsm_config YAML sync and backfill."""

from unittest.mock import patch

from django.test import TestCase

from netbox_nsm.objects.type_config_export import (
    backfill_cot_nsm_config_comments,
    sync_cot_nsm_config_comments,
)
from netbox_nsm.objects.type_config_specs import TYPECONFIG_UI_SPECS


class CotNsmConfigCommentsImportTests(TestCase):
    @patch("netbox_nsm.objects.type_config_export.sync_cot_nsm_config_comments_for_slugs")
    @patch("netbox_nsm.views.custom_objects_sync._seed_default_objects")
    @patch("netbox_nsm.views.custom_objects_sync._ensure_choice_sets")
    @patch("netbox_custom_objects.schema.executor.apply_document")
    def test_import_single_type_syncs_comments_after_apply(
        self,
        mock_apply,
        _mock_choice_sets,
        _mock_seed,
        mock_sync_comments,
    ):
        from netbox_nsm.views.setup.custom_objects import import_single_type

        import_single_type("nsm_zone")
        mock_apply.assert_called_once()
        mock_sync_comments.assert_called_once_with(["nsm_zone"])

    @patch("netbox_nsm.objects.type_config_export.sync_cot_nsm_config_comments_for_slugs")
    @patch("netbox_nsm.views.setup.custom_objects.import_rulebook_templates")
    @patch("netbox_nsm.views.custom_objects_sync._seed_default_objects")
    @patch("netbox_nsm.views.custom_objects_sync._prune_stale")
    @patch("netbox_nsm.views.custom_objects_sync._ensure_choice_sets")
    @patch("netbox_custom_objects.schema.executor.apply_document")
    def test_import_all_types_syncs_comments_after_apply(
        self,
        mock_apply,
        _mock_choice_sets,
        _mock_prune,
        _mock_seed,
        _mock_rulebook_templates,
        mock_sync_comments,
    ):
        from netbox_nsm.views.setup.custom_objects import import_all_types

        import_all_types()
        mock_apply.assert_called_once()
        document = mock_apply.call_args[0][0]
        expected_slugs = [t["slug"] for t in document["types"]]
        actual_slugs = list(mock_sync_comments.call_args[0][0])
        self.assertEqual(actual_slugs, expected_slugs)


class CotNsmConfigCommentsApplyDocumentTests(TestCase):
    def test_portable_schema_excludes_comments_field(self):
        from netbox_nsm.objects.custom_objects_schema import build_schema_document

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
        self.assertEqual(updated, len(TYPECONFIG_UI_SPECS))

        for spec in TYPECONFIG_UI_SPECS:
            cot = CustomObjectType.objects.get(slug=spec["slug"])
            self.assertIn("nsm_config:", cot.comments)
            self.assertNotIn(f"# {spec['label']}", cot.comments)
