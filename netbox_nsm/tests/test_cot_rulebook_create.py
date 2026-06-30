"""Tests for COT rulebook creation helpers."""

from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError

from netbox_nsm.rulebooks.create import (
    apply_copy_prefix,
    build_rulebook_clone_form_initial,
    create_cot_rulebook_from_schema_yaml,
    create_cot_rulebook_from_template,
    resolve_rulebook_slug,
    rulebook_name_from_slug,
)
from netbox_nsm.rulebooks.templates import (
    default_rulebook_schema_yaml,
    wizard_columns_from_schema_yaml,
)


class CotRulebookCreateTests(TestCase):
    def test_resolve_rulebook_slug(self):
        self.assertEqual(resolve_rulebook_slug("Demo"), "nsm_rb_demo")
        self.assertEqual(resolve_rulebook_slug("My Prod"), "nsm_rb_my_prod")

    def test_resolve_rejects_template_slug(self):
        with self.assertRaises(ValidationError):
            resolve_rulebook_slug("0001_template")

    @patch("netbox_nsm.type_metadata.config.save_nsm_config_document_for_cot")
    @patch("netbox_nsm.rulebooks.templates.is_deployed_rulebook_slug", return_value=True)
    @patch("netbox_nsm.rulebooks.create.is_deployed_rulebook_slug", return_value=True)
    @patch("netbox_nsm.rulebooks.rulebook_groups.apply_schema_yaml_field_groups")
    @patch("netbox_nsm.objects.rulebook_config.save_rulebook_config_for_cot")
    @patch("netbox_custom_objects.schema.executor.apply_document")
    @patch("netbox_nsm.rulebooks.templates._query_rulebook_template_cots")
    @patch("netbox_custom_objects.models.CustomObjectType")
    def test_create_from_schema_yaml_sets_matching_verbose_names(
        self,
        mock_cot_model,
        mock_template_cots,
        mock_apply_document,
        mock_set_parent,
        mock_apply_field_groups,
        _mock_create_deployed,
        _mock_templates_deployed,
        _mock_save_nsm_config,
    ):
        mock_template_cots.return_value.none.return_value = mock_template_cots.return_value
        mock_template_cots.return_value.filter.return_value.exists.return_value = False
        mock_template_cots.return_value.filter.return_value.first.return_value = None
        from types import SimpleNamespace

        mock_cot_model.objects.filter.return_value.exists.return_value = False
        created = SimpleNamespace(
            slug="nsm_rb_test_01",
            verbose_name="Rulebook Test 01",
            comments="",
        )
        mock_cot_model.objects.get.return_value = created

        create_cot_rulebook_from_schema_yaml(
            schema_yaml=default_rulebook_schema_yaml(),
            name="Test 01",
        )

        document = mock_apply_document.call_args[0][0]
        type_def = document["types"][0]
        self.assertEqual(type_def["verbose_name"], "Rulebook Test 01")
        self.assertEqual(type_def["verbose_name_plural"], "Rulebook Test 01")
        self.assertEqual(type_def["fields"][3]["name"], "source")
        self.assertNotIn("group_name", type_def["fields"][3])

    @patch("netbox_nsm.type_metadata.config.save_nsm_config_document_for_cot")
    @patch("netbox_nsm.rulebooks.templates.is_deployed_rulebook_slug", return_value=True)
    @patch("netbox_nsm.rulebooks.create.is_deployed_rulebook_slug", return_value=True)
    @patch("netbox_nsm.rulebooks.rulebook_groups.apply_schema_yaml_field_groups")
    @patch("netbox_nsm.objects.rulebook_config.save_rulebook_config_for_cot")
    @patch("netbox_custom_objects.schema.executor.apply_document")
    @patch("netbox_nsm.rulebooks.templates.get_template")
    @patch("netbox_nsm.rulebooks.templates._query_rulebook_template_cots")
    @patch("netbox_custom_objects.models.CustomObjectType")
    def test_create_from_template_still_supported(
        self,
        mock_cot_model,
        mock_template_cots,
        mock_get_template,
        mock_apply_document,
        mock_set_parent,
        mock_apply_field_groups,
        _mock_create_deployed,
        _mock_templates_deployed,
        _mock_save_nsm_config,
    ):
        mock_template_cots.return_value.none.return_value = mock_template_cots.return_value
        mock_template_cots.return_value.filter.return_value.exists.return_value = False
        mock_template_cots.return_value.filter.return_value.first.return_value = None
        mock_get_template.return_value = {
            "slug": "nsm_rb_custom_template",
            "field_names": ("index", "name", "source", "destination", "actions"),
        }
        from types import SimpleNamespace

        mock_cot_model.objects.filter.return_value.exists.return_value = False
        created = SimpleNamespace(
            slug="nsm_rb_test_01",
            verbose_name="Rulebook Test 01",
            comments="",
        )
        mock_cot_model.objects.get.return_value = created

        create_cot_rulebook_from_template(
            template_slug="nsm_rb_custom_template",
            name="Test 01",
        )

        document = mock_apply_document.call_args[0][0]
        type_def = document["types"][0]
        self.assertEqual(type_def["verbose_name"], "Rulebook Test 01")

    def test_wizard_columns_for_default_schema(self):
        columns = wizard_columns_from_schema_yaml(default_rulebook_schema_yaml())
        self.assertGreater(len(columns), 0)
        self.assertEqual(columns[0]["name"], "index")
        self.assertEqual(next(c for c in columns if c["name"] == "source")["label"], "Source")

    def test_apply_copy_prefix(self):
        self.assertEqual(apply_copy_prefix("demo"), "copy_demo")
        self.assertEqual(apply_copy_prefix("copy_demo"), "copy_demo")

    def test_build_rulebook_clone_form_initial(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        cot = SimpleNamespace(
            slug="nsm_rb_demo",
            verbose_name="Demo",
            name="nsm_rb_demo",
            description="Starter demo",
        )
        with patch(
            "netbox_nsm.rulebooks.templates.export_rulebook_schema_yaml_for_copy",
            return_value='schema_version: "1"\ntypes:\n  - slug: nsm_rb_{{name}}\n',
        ) as mock_export:
            initial = build_rulebook_clone_form_initial(cot)
        mock_export.assert_called_once_with(cot)
        self.assertEqual(initial["name"], "copy_demo")
        self.assertEqual(initial["verbose_name"], "Rulebook copy_Demo")
        self.assertEqual(initial["description"], "Starter demo")
        self.assertIn("copy_demo", initial["schema_yaml"])

    def test_rulebook_name_from_slug(self):
        self.assertEqual(rulebook_name_from_slug("nsm_rb_demo"), "demo")

