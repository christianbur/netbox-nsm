"""Setup wizard: Custom Object status includes core types only."""

from django.test import SimpleTestCase

from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS
from netbox_nsm.bundles import setup_context


class SetupCustomObjectsStatusTests(SimpleTestCase):
    def test_required_cot_slugs_include_object_link(self):
        self.assertIn("nsm_object_link", REQUIRED_COT_SLUGS)

    def test_all_cots_ok_when_core_types_present(self):
        cot_status = {slug: object() for slug in REQUIRED_COT_SLUGS}
        self.assertTrue(setup_context.all_cots_ok(cot_status))

    def test_all_cots_ok_false_when_type_missing(self):
        cot_status = setup_context.empty_cot_status()
        self.assertFalse(setup_context.all_cots_ok(cot_status))

    def test_builtin_object_entries_exclude_panel_link(self):
        entries = setup_context.get_builtin_object_entries(
            cot_status=setup_context.empty_cot_status()
        )
        self.assertEqual(
            [entry["slug"] for entry in entries],
            list(setup_context.COT_BUILTIN_OBJECT_SLUGS),
        )
        self.assertNotIn("nsm_object_link", [entry["slug"] for entry in entries])
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["description"])

    def test_nsm_panel_entries_match_panel_slugs(self):
        entries = setup_context.get_nsm_panel_entries(
            cot_status=setup_context.empty_cot_status()
        )
        self.assertEqual(
            [entry["slug"] for entry in entries],
            list(setup_context.NSM_PANEL_COT_SLUGS),
        )
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["description"])

    def test_cot_setup_groups_cover_core_types_only(self):
        groups = setup_context.get_cot_setup_groups(
            cot_status=setup_context.empty_cot_status(),
            rulebook_template_status={},
        )
        self.assertEqual(len(groups), len(setup_context.COT_SETUP_GROUPS))
        self.assertEqual(groups[0]["id"], "objects")
        self.assertEqual(groups[1]["id"], "nsm_panel")
        object_slugs = [entry["slug"] for entry in groups[0]["entries"]]
        panel_slugs = [entry["slug"] for entry in groups[1]["entries"]]
        self.assertEqual(object_slugs, list(setup_context.COT_BUILTIN_OBJECT_SLUGS))
        self.assertEqual(panel_slugs, list(setup_context.NSM_PANEL_COT_SLUGS))
        self.assertEqual(
            set(object_slugs) | set(panel_slugs),
            set(REQUIRED_COT_SLUGS),
        )

    def test_cot_setup_groups_omit_rulebook_templates_when_empty(self):
        groups = setup_context.get_cot_setup_groups(
            cot_status=setup_context.empty_cot_status(),
            rulebook_template_status={},
        )
        self.assertEqual(
            [group["id"] for group in groups],
            ["objects", "nsm_panel"],
        )

    def test_cot_schema_yaml_contains_bundled_types(self):
        yaml_text = setup_context.get_cot_schema_yaml()
        self.assertIn("schema_version", yaml_text)
        self.assertIn("nsm_zone", yaml_text)
        self.assertIn("nsm_object_link", yaml_text)

    def test_cot_schema_preview_covers_required_slugs(self):
        preview = setup_context.get_cot_schema_preview()
        self.assertEqual(
            {row["slug"] for row in preview},
            set(REQUIRED_COT_SLUGS),
        )
        for row in preview:
            self.assertTrue(row["label"])
            self.assertTrue(row["fields"])

    def test_cot_schema_preview_includes_nsm_config_for_ui_types(self):
        preview = setup_context.get_cot_schema_preview()
        zone = next(row for row in preview if row["slug"] == "nsm_zone")
        self.assertIn("nsm_config:", zone["nsm_config_yaml"])
        object_link = next(row for row in preview if row["slug"] == "nsm_object_link")
        self.assertEqual(object_link["nsm_config_yaml"], "")
