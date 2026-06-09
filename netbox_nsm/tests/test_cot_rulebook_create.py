"""Tests for COT rulebook creation helpers."""

from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from netbox_nsm.rulebooks.create import (
    create_cot_rulebook_from_template,
    resolve_rulebook_slug,
)
from netbox_nsm.rulebooks.templates import template_wizard_columns


class CotRulebookCreateTests(TestCase):
    def test_resolve_rulebook_slug(self):
        self.assertEqual(resolve_rulebook_slug("Demo"), "nsm_rb_demo")
        self.assertEqual(resolve_rulebook_slug("My Prod"), "nsm_rb_my_prod")

    def test_resolve_rejects_template_slug(self):
        with self.assertRaises(ValidationError):
            resolve_rulebook_slug("0001_template")

    @patch("netbox_nsm.rulebooks.cot_hierarchy.set_cot_rulebook_parent")
    @patch("netbox_custom_objects.schema.executor.apply_document")
    @patch("netbox_nsm.rulebooks.templates._query_rulebook_template_cots")
    @patch("netbox_custom_objects.models.CustomObjectType")
    def test_create_sets_matching_verbose_names(
        self, mock_cot_model, mock_template_cots, mock_apply_document, mock_set_parent
    ):
        mock_template_cots.return_value.none.return_value = mock_template_cots.return_value
        mock_template_cots.return_value.filter.return_value.exists.return_value = False
        mock_template_cots.return_value.filter.return_value.first.return_value = None
        from types import SimpleNamespace

        mock_cot_model.objects.filter.return_value.exists.return_value = False
        created = SimpleNamespace(slug="nsm_rb_test_01", verbose_name="Rulebook Test 01")
        mock_cot_model.objects.get.return_value = created

        create_cot_rulebook_from_template(
            template_slug="nsm_rb_0001_template",
            name="Test 01",
        )

        document = mock_apply_document.call_args[0][0]
        type_def = document["types"][0]
        self.assertEqual(type_def["verbose_name"], "Rulebook Test 01")
        self.assertEqual(type_def["verbose_name_plural"], "Rulebook Test 01")

    def test_wizard_columns_for_each_template(self):
        for slug in (
            "nsm_rb_0001_template",
            "nsm_rb_0002_template",
            "nsm_rb_0003_template",
            "nsm_rb_0004_template",
        ):
            columns = template_wizard_columns(slug)
            self.assertGreater(len(columns), 0)
            self.assertEqual(columns[0]["name"], "index")
