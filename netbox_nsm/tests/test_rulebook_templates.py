"""Tests for bundled rulebook template definitions."""

from unittest import TestCase

from netbox_nsm.rulebooks.templates import (
    BUNDLED_RULEBOOK_TEMPLATE_SLUGS,
    DEMO_RULEBOOK_SLUG,
    DEMO_RULEBOOK_TEMPLATE_SLUG,
    RULEBOOK_TEMPLATE_BY_SLUG,
    RULEBOOK_TEMPLATE_GROUP,
    RULEBOOK_TEMPLATE_SLUGS,
    build_rulebook_document,
    build_rulebook_template_type_defs,
    format_rulebook_display_name,
    is_rulebook_template_slug,
    normalize_rulebook_display_name,
    is_deployed_rulebook_slug,
    template_wizard_columns,
)


class RulebookTemplateTests(TestCase):
    def test_four_templates_with_expected_field_counts(self):
        self.assertEqual(len(RULEBOOK_TEMPLATE_SLUGS), 4)
        self.assertEqual(
            len(RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0001_template"]["field_names"]),
            13,
        )
        self.assertEqual(
            len(RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0002_template"]["field_names"]),
            9,
        )
        self.assertEqual(
            len(RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0003_template"]["field_names"]),
            9,
        )
        self.assertEqual(
            len(RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0004_template"]["field_names"]),
            9,
        )

    def test_templates_use_rulebook_template_group(self):
        for type_def in build_rulebook_template_type_defs():
            self.assertEqual(type_def["group_name"], RULEBOOK_TEMPLATE_GROUP)

    def test_0002_omits_zones_and_labels(self):
        fields = set(
            RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0002_template"]["field_names"]
        )
        self.assertFalse(fields & {"source_zones", "destination_zones"})
        self.assertFalse(fields & {"source_labels", "destination_labels"})
        self.assertIn("source_addresses", fields)

    def test_0003_omits_addresses_and_labels(self):
        fields = set(
            RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0003_template"]["field_names"]
        )
        self.assertIn("source_zones", fields)
        self.assertFalse(fields & {"source_addresses", "destination_addresses"})
        self.assertFalse(fields & {"source_labels", "destination_labels"})

    def test_0004_omits_addresses_and_zones(self):
        fields = set(
            RULEBOOK_TEMPLATE_BY_SLUG["nsm_rb_0004_template"]["field_names"]
        )
        self.assertIn("source_labels", fields)
        self.assertFalse(fields & {"source_zones", "destination_zones"})
        self.assertFalse(fields & {"source_addresses", "destination_addresses"})

    def test_template_fields_use_sort_key_groups(self):
        from netbox_nsm.rulebooks.rulebook_groups import (
            GROUP_ACTIONS,
            GROUP_COMMON,
            GROUP_INFOS,
            GROUP_NOTES,
            GROUP_SERVICES,
            GROUP_SOURCE,
        )
        from netbox_nsm.rulebooks.templates import _FIELD_CATALOG

        source_zones = _FIELD_CATALOG["source_zones"]
        self.assertEqual(source_zones["label"], "Zones")
        self.assertEqual(source_zones["group_name"], GROUP_SOURCE)
        self.assertEqual(_FIELD_CATALOG["index"]["group_name"], GROUP_COMMON)
        self.assertEqual(_FIELD_CATALOG["services_applications"]["group_name"], GROUP_SERVICES)
        self.assertEqual(_FIELD_CATALOG["actions"]["group_name"], GROUP_ACTIONS)
        self.assertEqual(_FIELD_CATALOG["infos"]["group_name"], GROUP_INFOS)
        self.assertEqual(_FIELD_CATALOG["description"]["group_name"], GROUP_NOTES)

    def test_wizard_columns_include_allowed_objects(self):
        rows = template_wizard_columns("nsm_rb_0001_template")
        zones_row = next(row for row in rows if row["name"] == "source_zones")
        self.assertEqual(zones_row["label"], "Zones (Source)")
        services_row = next(
            row for row in rows if row["name"] == "services_applications"
        )
        self.assertEqual(services_row["label"], "Services & Applications (Services)")
        self.assertEqual(
            services_row["allowed_objects"],
            ["Service", "Service Group", "Network App"],
        )

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

    def test_build_rulebook_document_for_demo(self):
        document = build_rulebook_document(
            template_slug=DEMO_RULEBOOK_TEMPLATE_SLUG,
            rulebook_slug=DEMO_RULEBOOK_SLUG,
            verbose_name="Rulebook Demo",
        )
        type_def = document["types"][0]
        self.assertEqual(type_def["slug"], "nsm_rb_demo")
        self.assertEqual(type_def["group_name"], "NSM Rulebooks")
        self.assertEqual(type_def["verbose_name"], "Rulebook Demo")
        self.assertEqual(type_def["verbose_name_plural"], "Rulebook Demo")
        self.assertEqual(len(type_def["fields"]), 9)
        self.assertIn("nsm_rb_0003_template", type_def["description"])

    def test_build_rulebook_document_plural_matches_singular_by_default(self):
        document = build_rulebook_document(
            template_slug=DEMO_RULEBOOK_TEMPLATE_SLUG,
            rulebook_slug="nsm_rb_test_01",
            verbose_name="Rulebook Test 01",
        )
        type_def = document["types"][0]
        self.assertEqual(type_def["verbose_name_plural"], "Rulebook Test 01")
        self.assertNotEqual(type_def["verbose_name_plural"], "Rules")

    def test_build_rulebook_document_custom_description(self):
        document = build_rulebook_document(
            template_slug=DEMO_RULEBOOK_TEMPLATE_SLUG,
            rulebook_slug=DEMO_RULEBOOK_SLUG,
            verbose_name="Demo Rulebook",
            description="Production firewall policy",
        )
        self.assertEqual(
            document["types"][0]["description"],
            "Production firewall policy",
        )

    def test_deployed_rulebook_slug_detection(self):
        self.assertTrue(is_deployed_rulebook_slug("nsm_rb_demo"))
        self.assertFalse(is_deployed_rulebook_slug("nsm_rb_0001_template"))

    def test_bundled_template_slugs_alias(self):
        self.assertEqual(BUNDLED_RULEBOOK_TEMPLATE_SLUGS, RULEBOOK_TEMPLATE_SLUGS)

    def test_is_rulebook_template_slug_for_bundled(self):
        for slug in RULEBOOK_TEMPLATE_SLUGS:
            self.assertTrue(is_rulebook_template_slug(slug))
