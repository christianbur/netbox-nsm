"""Setup wizard: Custom Object status includes core types and rulebook templates."""

from django.test import SimpleTestCase

from netbox_nsm.objects.type_config_specs import REQUIRED_COT_SLUGS
from netbox_nsm.rulebooks.templates import RULEBOOK_TEMPLATE_SLUGS
from netbox_nsm.views.setup import custom_objects


class SetupCustomObjectsStatusTests(SimpleTestCase):
    def test_required_cot_slugs_include_object_link(self):
        self.assertIn("nsm_object_link", REQUIRED_COT_SLUGS)

    def test_empty_status_covers_bundled_template_slugs(self):
        cot_status = custom_objects.empty_cot_status()
        template_status = custom_objects.empty_rulebook_template_status()
        self.assertEqual(set(cot_status), set(REQUIRED_COT_SLUGS))
        self.assertEqual(set(template_status), set(RULEBOOK_TEMPLATE_SLUGS))
        self.assertFalse(custom_objects.all_cots_ok(cot_status, template_status))

    def test_rulebook_template_entries_match_slugs(self):
        entries = custom_objects.get_rulebook_template_entries(
            template_status=custom_objects.empty_rulebook_template_status()
        )
        self.assertEqual([entry["slug"] for entry in entries], RULEBOOK_TEMPLATE_SLUGS)
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["description"])

    def test_builtin_object_entries_exclude_panel_link(self):
        entries = custom_objects.get_builtin_object_entries(
            cot_status=custom_objects.empty_cot_status()
        )
        self.assertEqual(
            [entry["slug"] for entry in entries],
            list(custom_objects.COT_BUILTIN_OBJECT_SLUGS),
        )
        self.assertNotIn("nsm_object_link", [entry["slug"] for entry in entries])
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["description"])

    def test_nsm_panel_entries_match_panel_slugs(self):
        entries = custom_objects.get_nsm_panel_entries(
            cot_status=custom_objects.empty_cot_status()
        )
        self.assertEqual(
            [entry["slug"] for entry in entries],
            list(custom_objects.NSM_PANEL_COT_SLUGS),
        )
        for entry in entries:
            self.assertTrue(entry["label"])
            self.assertTrue(entry["description"])

    def test_cot_setup_groups_cover_all_types(self):
        groups = custom_objects.get_cot_setup_groups(
            cot_status=custom_objects.empty_cot_status(),
            rulebook_template_status=custom_objects.empty_rulebook_template_status(),
        )
        self.assertEqual(len(groups), len(custom_objects.COT_SETUP_GROUPS))
        self.assertEqual(groups[0]["id"], "objects")
        self.assertEqual(groups[1]["id"], "nsm_panel")
        self.assertEqual(groups[2]["id"], "rulebook_templates")
        object_slugs = [entry["slug"] for entry in groups[0]["entries"]]
        panel_slugs = [entry["slug"] for entry in groups[1]["entries"]]
        template_slugs = [entry["slug"] for entry in groups[2]["entries"]]
        self.assertEqual(object_slugs, list(custom_objects.COT_BUILTIN_OBJECT_SLUGS))
        self.assertEqual(panel_slugs, list(custom_objects.NSM_PANEL_COT_SLUGS))
        self.assertEqual(template_slugs, RULEBOOK_TEMPLATE_SLUGS)
        self.assertEqual(
            set(object_slugs) | set(panel_slugs),
            set(REQUIRED_COT_SLUGS),
        )
