"""Tests for dynamic rulebook template discovery via COT group membership."""

import uuid

from extras.choices import CustomFieldTypeChoices
from utilities.testing import TestCase

from netbox_nsm.rulebooks.forms.cot import CotRulebookCreateForm
from netbox_nsm.rulebooks.templates import (
    BUNDLED_RULEBOOK_TEMPLATE_SLUGS,
    RULEBOOK_TEMPLATE_GROUP,
    default_rulebook_schema_yaml,
    get_rulebook_template_slugs,
    is_deployed_rulebook_slug,
    is_rulebook_template_slug,
    template_wizard_columns,
)
from netbox_nsm.views.setup import custom_objects


class RulebookTemplateDiscoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from netbox_custom_objects.models import CustomObjectType, CustomObjectTypeField

        cls.custom_slug = f"nsm_rb_custom_tpl_{uuid.uuid4().hex[:8]}"
        cls.custom_cot = CustomObjectType.objects.create(
            name=cls.custom_slug,
            slug=cls.custom_slug,
            verbose_name="Custom Template",
            description="Manually created blueprint",
            group_name=RULEBOOK_TEMPLATE_GROUP,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.custom_cot,
            name="index",
            label="Index",
            type=CustomFieldTypeChoices.TYPE_INTEGER,
            schema_id=1,
            primary=True,
            required=True,
        )
        CustomObjectTypeField.objects.create(
            custom_object_type=cls.custom_cot,
            name="name",
            label="Name",
            type=CustomFieldTypeChoices.TYPE_TEXT,
            schema_id=2,
            required=False,
        )

    def test_custom_template_in_group_is_recognized(self):
        self.assertTrue(is_rulebook_template_slug(self.custom_slug))
        self.assertFalse(is_deployed_rulebook_slug(self.custom_slug))

    def test_no_bundled_templates(self):
        self.assertEqual(BUNDLED_RULEBOOK_TEMPLATE_SLUGS, [])

    def test_get_rulebook_template_slugs_includes_custom(self):
        slugs = get_rulebook_template_slugs()
        self.assertIn(self.custom_slug, slugs)

    def test_setup_status_includes_custom_template(self):
        status = custom_objects.get_rulebook_template_status()
        self.assertEqual(status[self.custom_slug].pk, self.custom_cot.pk)

    def test_setup_groups_include_custom_template_when_present(self):
        groups = custom_objects.get_cot_setup_groups()
        group_ids = {group["id"] for group in groups}
        self.assertIn("objects", group_ids)
        self.assertIn("nsm_panel", group_ids)
        entries = custom_objects.get_rulebook_template_entries()
        self.assertIn(
            self.custom_slug,
            [entry["slug"] for entry in entries],
        )

    def test_setup_entries_include_custom_template(self):
        entries = custom_objects.get_rulebook_template_entries()
        entry_slugs = [entry["slug"] for entry in entries]
        self.assertIn(self.custom_slug, entry_slugs)
        custom_entry = next(
            entry for entry in entries if entry["slug"] == self.custom_slug
        )
        self.assertEqual(custom_entry["label"], "Custom Template")
        self.assertEqual(custom_entry["description"], "Manually created blueprint")

    def test_create_form_prefills_default_schema_yaml(self):
        from unittest.mock import patch

        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertEqual(form.initial["schema_yaml"], default_rulebook_schema_yaml())
        self.assertIn("schema_yaml", form.fields)

    def test_wizard_columns_for_custom_template(self):
        columns = template_wizard_columns(self.custom_slug)
        self.assertEqual([row["name"] for row in columns], ["index", "name"])
        self.assertEqual(columns[0]["label"], "Index")
        self.assertTrue(columns[0]["required"])

    def test_import_rulebook_templates_syncs_groups_only(self):
        from unittest.mock import patch

        with patch(
            "netbox_custom_objects.schema.executor.apply_document"
        ) as mock_apply, patch(
            "netbox_nsm.rulebooks.rulebook_groups.sync_all_rulebook_cots"
        ) as mock_sync:
            custom_objects.import_rulebook_templates()

        mock_apply.assert_not_called()
        mock_sync.assert_called_once()
