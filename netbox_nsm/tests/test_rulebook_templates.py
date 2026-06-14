"""Tests for rulebook schema YAML and template helpers."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from netbox_nsm.rulebooks.templates import (
    BUNDLED_RULEBOOK_TEMPLATE_SLUGS,
    DEFAULT_RULEBOOK_SCHEMA_YAML,
    DEMO_RULEBOOK_SCHEMA_YAML,
    DEMO_RULEBOOK_SLUG,
    RULEBOOK_TEMPLATE_GROUP,
    RULEBOOK_TEMPLATE_SLUGS,
    build_rulebook_document_from_schema,
    build_rulebook_template_type_defs,
    default_rulebook_schema_yaml,
    demo_rulebook_schema_yaml,
    export_rulebook_schema_yaml_for_copy,
    extract_rulebook_wizard_metadata_from_schema_yaml,
    resolve_rulebook_schema_yaml_for_validation,
    validate_substituted_rulebook_schema_yaml,
    substitute_rulebook_schema_placeholders,
    format_rulebook_display_name,
    is_rulebook_template_slug,
    normalize_rulebook_display_name,
    is_deployed_rulebook_slug,
    parse_rulebook_schema_yaml,
    wizard_columns_from_schema_yaml,
)


class RulebookTemplateTests(TestCase):
    def test_no_bundled_templates(self):
        self.assertEqual(RULEBOOK_TEMPLATE_SLUGS, [])
        self.assertEqual(BUNDLED_RULEBOOK_TEMPLATE_SLUGS, [])
        self.assertEqual(build_rulebook_template_type_defs(), [])

    @patch("netbox_custom_objects.schema.exporter.export_cot")
    def test_export_rulebook_schema_yaml_for_copy(self, mock_export_cot):
        mock_export_cot.return_value = {
            "fields": [
                {"id": 1, "name": "index", "type": "integer", "primary": True},
                {"id": 2, "name": "name", "type": "text", "required": True},
            ],
            "removed_fields": [],
        }
        yaml_text = export_rulebook_schema_yaml_for_copy(SimpleNamespace())
        self.assertIn("nsm_rb_{{name}}", yaml_text)
        self.assertIn("{{display_name}}", yaml_text)
        self.assertIn("{{description}}", yaml_text)
        resolved = substitute_rulebook_schema_placeholders(
            yaml_text,
            display_name="Rulebook Bench",
            name="bench",
            description="",
        )
        type_def = parse_rulebook_schema_yaml(resolved)
        self.assertEqual(
            [field["name"] for field in type_def["fields"]],
            ["index", "name"],
        )

    def test_extract_rulebook_wizard_metadata_from_literal_schema_yaml(self):
        yaml_text = substitute_rulebook_schema_placeholders(
            default_rulebook_schema_yaml(),
            display_name="Bench Addresses",
            name="bench_addresses",
            description="Copied from existing rulebook",
        )
        meta = extract_rulebook_wizard_metadata_from_schema_yaml(yaml_text)
        self.assertEqual(meta["name"], "bench_addresses")
        self.assertEqual(meta["verbose_name"], "Rulebook Bench Addresses")
        self.assertEqual(meta["description"], "Copied from existing rulebook")

    def test_extract_rulebook_wizard_metadata_ignores_placeholders(self):
        meta = extract_rulebook_wizard_metadata_from_schema_yaml(
            default_rulebook_schema_yaml()
        )
        self.assertEqual(meta, {})

    def test_validate_substituted_schema_yaml_uses_field_values(self):
        validate_substituted_rulebook_schema_yaml(
            default_rulebook_schema_yaml(),
            display_name="Bench Addresses",
            name="bench_addresses",
            description="Copied schema",
        )

    def test_validate_substituted_schema_yaml_uses_fallbacks_for_placeholders(self):
        validate_substituted_rulebook_schema_yaml(default_rulebook_schema_yaml())

    def test_resolve_rulebook_schema_yaml_for_validation_substitutes_placeholders(self):
        resolved = resolve_rulebook_schema_yaml_for_validation(
            default_rulebook_schema_yaml(),
            display_name="Bench Addresses",
            name="bench_addresses",
            description="Copied schema",
        )
        self.assertIn("nsm_rb_bench_addresses", resolved)
        self.assertIn("Bench Addresses", resolved)
        self.assertIn("Copied schema", resolved)

    def test_validate_substituted_schema_yaml_rejects_invalid_yaml(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_substituted_rulebook_schema_yaml("not: [valid")

    def test_default_schema_yaml_parses(self):
        type_def = parse_rulebook_schema_yaml(default_rulebook_schema_yaml())
        self.assertEqual(type_def.get("removed_fields"), [])
        field_names = [field["name"] for field in type_def["fields"]]
        self.assertEqual(
            field_names,
            [
                "index",
                "status",
                "name",
                "source",
                "destination",
                "services_applications",
                "actions",
                "infos",
                "description",
            ],
        )

    def test_default_schema_yaml_constant_matches_helper(self):
        self.assertEqual(default_rulebook_schema_yaml(), DEFAULT_RULEBOOK_SCHEMA_YAML)

    def test_default_schema_yaml_contains_placeholders(self):
        yaml_text = default_rulebook_schema_yaml()
        self.assertIn("{{display_name}}", yaml_text)
        self.assertIn("{{name}}", yaml_text)
        self.assertIn("{{description}}", yaml_text)
        self.assertIn("nsm_rb_{{name}}", yaml_text)

    def test_substitute_rulebook_schema_placeholders(self):
        resolved = substitute_rulebook_schema_placeholders(
            default_rulebook_schema_yaml(),
            display_name="Test 01",
            name="test_01",
            description="My description",
        )
        self.assertIn("slug: nsm_rb_test_01", resolved)
        self.assertIn('verbose_name: "Rulebook Test 01"', resolved)
        self.assertIn('description: "My description"', resolved)
        type_def = parse_rulebook_schema_yaml(resolved)
        self.assertEqual(type_def["slug"], "nsm_rb_test_01")

    def test_wizard_columns_from_default_schema_yaml(self):
        rows = wizard_columns_from_schema_yaml(default_rulebook_schema_yaml())
        source_row = next(row for row in rows if row["name"] == "source")
        self.assertEqual(source_row["label"], "Source")
        self.assertEqual(
            source_row["allowed_objects"],
            ["Zone", "Label", "Address", "Address Group"],
        )
        services_row = next(
            row for row in rows if row["name"] == "services_applications"
        )
        self.assertEqual(services_row["label"], "Services & Applications")

    def test_format_rulebook_display_name(self):
        self.assertEqual(format_rulebook_display_name("Test 01"), "Rulebook Test 01")
        self.assertEqual(format_rulebook_display_name("  Demo  "), "Rulebook Demo")

    def test_normalize_rulebook_display_name(self):
        self.assertEqual(
            normalize_rulebook_display_name("Test 01"),
            "Rulebook Test 01",
        )
        self.assertEqual(
            normalize_rulebook_display_name("Rulebook Test 01"),
            "Rulebook Test 01",
        )
        self.assertEqual(
            normalize_rulebook_display_name("  rulebook Demo  "),
            "rulebook Demo",
        )

    def test_demo_schema_yaml_resolves_for_starter(self):
        type_def = parse_rulebook_schema_yaml(demo_rulebook_schema_yaml())
        self.assertEqual(type_def["slug"], "nsm_rb_demo")
        self.assertEqual(type_def["group_name"], "NSM Rulebooks")
        self.assertEqual(type_def["verbose_name"], "Rulebook Demo")
        field_names = [field["name"] for field in type_def["fields"]]
        self.assertEqual(
            field_names,
            ["index", "status", "name", "source", "destination", "actions", "description"],
        )
        self.assertNotIn("group_name", type_def["fields"][3])
        source = type_def["fields"][3]
        self.assertEqual(source["related_object_types"], ["custom-objects/nsm_zone"])

    def test_demo_schema_yaml_constant_has_placeholders(self):
        self.assertIn("{{name}}", DEMO_RULEBOOK_SCHEMA_YAML)
        self.assertIn("{{display_name}}", DEMO_RULEBOOK_SCHEMA_YAML)

    def test_build_rulebook_document_from_schema(self):
        schema_type_def = parse_rulebook_schema_yaml(default_rulebook_schema_yaml())
        document = build_rulebook_document_from_schema(
            schema_type_def=schema_type_def,
            rulebook_slug="nsm_rb_custom",
            verbose_name="Rulebook Custom",
            description="Custom schema",
        )
        type_def = document["types"][0]
        self.assertEqual(type_def["slug"], "nsm_rb_custom")
        self.assertEqual(len(type_def["fields"]), 9)
        self.assertEqual(type_def["description"], "Custom schema")
        self.assertEqual(type_def["fields"][3]["name"], "source")

    def test_build_rulebook_document_from_schema_resolves_default_description(self):
        schema_type_def = parse_rulebook_schema_yaml(default_rulebook_schema_yaml())
        document = build_rulebook_document_from_schema(
            schema_type_def=schema_type_def,
            rulebook_slug="nsm_rb_bench_addresses",
            verbose_name="Rulebook Bench Addresses",
            description="",
            name="bench_addresses",
        )
        self.assertEqual(
            document["types"][0]["description"],
            "NSM rulebook created from template nsm_rb_bench_addresses.",
        )

    def test_deployed_rulebook_slug_detection(self):
        self.assertTrue(is_deployed_rulebook_slug("nsm_rb_demo"))
        self.assertFalse(is_deployed_rulebook_slug("nsm_rb_custom_template"))

    def test_is_rulebook_template_slug_pattern(self):
        self.assertTrue(is_rulebook_template_slug("nsm_rb_custom_template"))
        self.assertFalse(is_deployed_rulebook_slug("nsm_rb_custom_template"))

    def test_parse_rejects_invalid_yaml(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            parse_rulebook_schema_yaml("not: [valid")

    def test_parse_rejects_missing_fields(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            parse_rulebook_schema_yaml('schema_version: "1"\ntypes:\n  - slug: x\n')
