"""Tests for rulebook template slug helpers (legacy blueprint group)."""

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

    def test_create_form_prefills_default_schema_json(self):
        from unittest.mock import patch

        with patch(
            "netbox_nsm.rulebooks.forms.cot.deployed_rulebook_parent_choices",
            return_value=[("", "—")],
        ):
            form = CotRulebookCreateForm()
        self.assertTrue(form.initial["schema_json"].strip().startswith("{"))
        self.assertIn("schema_json", form.fields)

    def test_wizard_columns_for_custom_template(self):
        columns = template_wizard_columns(self.custom_slug)
        self.assertEqual([row["name"] for row in columns], ["index", "name"])
        self.assertEqual(columns[0]["label"], "Index")
        self.assertTrue(columns[0]["required"])
