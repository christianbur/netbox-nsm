"""Tests for bundled portable schema documents."""

import json
from pathlib import Path
from unittest import TestCase

from netbox_nsm.objects.custom_objects_schema import (
    CHOICE_SETS_PATH,
    PORTABLE_SCHEMA_PATH,
    build_choice_set_specs,
    build_portable_schema_preview_types,
    build_schema_document,
    choice_set_names_in_document,
    export_portable_schema_yaml,
    load_choice_set_specs,
    load_portable_schema_document,
)
from netbox_nsm.rulebooks.templates import (
    RULEBOOK_TEMPLATE_SLUGS,
    build_rulebook_template_type_defs,
)
from netbox_nsm.objects.type_config_specs import REQUIRED_COT_SLUGS, TYPECONFIG_UI_SPECS


def _assert_removed_fields_are_tombstones(type_def: dict) -> None:
    removed_ids = {f["id"] for f in type_def.get("fields", [])}
    for entry in type_def.get("removed_fields", []):
        assert isinstance(entry, dict), (
            f"{type_def['slug']}: removed_fields must be tombstone dicts, "
            f"not {type_def.get('removed_fields')!r}"
        )
        assert "id" in entry and "name" in entry and "type" in entry, entry
        assert entry["id"] not in removed_ids, (
            f"{type_def['slug']}: removed_fields id {entry['id']} "
            "must not appear in fields"
        )


class PortableSchemaTests(TestCase):
    def test_schema_file_exists_and_matches_spec(self):
        document = load_portable_schema_document()
        self.assertEqual(document["schema_version"], "1")
        self.assertIsInstance(document["types"], list)
        slugs = {t["slug"] for t in document["types"]}
        self.assertEqual(slugs, set(REQUIRED_COT_SLUGS))
        self.assertEqual(RULEBOOK_TEMPLATE_SLUGS, [])
        for type_def in document["types"]:
            self.assertEqual(type_def["name"], type_def["slug"])
            self.assertIn("fields", type_def)
            self.assertIn("removed_fields", type_def)
            field_ids = [f["id"] for f in type_def["fields"]]
            self.assertEqual(len(field_ids), len(set(field_ids)))
            for field_def in type_def["fields"]:
                self.assertGreaterEqual(field_def["id"], 1)
                self.assertIn("name", field_def)
                self.assertIn("type", field_def)
            _assert_removed_fields_are_tombstones(type_def)

    def test_rulebook_template_defs_use_tombstone_removed_fields(self):
        for type_def in build_rulebook_template_type_defs():
            _assert_removed_fields_are_tombstones(type_def)

    def test_all_object_types_have_status_field_after_name(self):
        document = load_portable_schema_document()
        for type_def in document["types"]:
            fields = type_def["fields"]
            status = next((f for f in fields if f.get("name") == "status"), None)
            self.assertIsNotNone(status, type_def["slug"])
            self.assertEqual(status["type"], "select")
            self.assertEqual(status["weight"], 2)
            self.assertEqual(status["default"], "active")
            self.assertEqual(status["choice_set"], "nsm_object_status")
            name = next(f for f in fields if f.get("name") == "name")
            self.assertLess(name["weight"], status["weight"])

    def test_object_status_choice_set_values(self):
        specs = {row["name"]: row["choices"] for row in load_choice_set_specs()}
        self.assertEqual(
            specs["nsm_object_status"],
            ["active", "reserved", "deprecated"],
        )

    def test_choice_sets_cover_schema_references(self):
        document = load_portable_schema_document()
        needed = choice_set_names_in_document(document)
        available = {spec["name"] for spec in load_choice_set_specs()}
        self.assertTrue(needed.issubset(available), needed - available)

    def test_build_schema_document_returns_same_as_loader(self):
        self.assertEqual(build_schema_document(), load_portable_schema_document())

    def test_build_choice_set_specs_matches_file_when_unfiltered(self):
        self.assertEqual(build_choice_set_specs(), load_choice_set_specs())

    def test_json_files_are_valid_utf8(self):
        for path in (PORTABLE_SCHEMA_PATH, CHOICE_SETS_PATH):
            with path.open(encoding="utf-8") as fh:
                json.load(fh)

    def test_export_portable_schema_yaml_contains_bundled_type_definitions(self):
        import yaml

        yaml_text = export_portable_schema_yaml(include_rulebook_templates=False)
        self.assertIn("schema_version: '1'", yaml_text)
        self.assertIn("nsm_action", yaml_text)
        bundled = load_portable_schema_document(include_rulebook_templates=False)
        for type_def in bundled["types"]:
            type_yaml = yaml.dump(
                [type_def],
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            ).strip()
            self.assertIn(type_yaml, yaml_text)

    def test_export_portable_schema_yaml_includes_nsm_config_for_ui_types(self):
        yaml_text = export_portable_schema_yaml(include_rulebook_templates=False)
        self.assertEqual(yaml_text.count("nsm_config:"), len(TYPECONFIG_UI_SPECS))
        self.assertIn("comments:", yaml_text)
        self.assertIn("rule_view:", yaml_text)
        self.assertNotIn("panel:", yaml_text)
        zone_pos = yaml_text.find("- slug: nsm_zone")
        zone_block = yaml_text[zone_pos : zone_pos + 600]
        self.assertIn("sort_order: 10", zone_block)
        self.assertIn("display_template:", zone_block)

    def test_build_portable_schema_preview_types_lists_core_types(self):
        preview_types = build_portable_schema_preview_types(
            include_rulebook_templates=False
        )
        self.assertEqual(
            {row["slug"] for row in preview_types},
            set(REQUIRED_COT_SLUGS),
        )
        action = next(row for row in preview_types if row["slug"] == "nsm_action")
        self.assertEqual(action["label"], "Action")
        self.assertTrue(action["fields"])
        name_field = next(f for f in action["fields"] if f["name"] == "name")
        self.assertEqual(name_field["type"], "text")
        self.assertTrue(name_field["required"])

    def test_build_portable_schema_preview_includes_nsm_config_yaml(self):
        preview_types = build_portable_schema_preview_types(
            include_rulebook_templates=False
        )
        zone = next(row for row in preview_types if row["slug"] == "nsm_zone")
        self.assertNotIn("# Zones\n", zone["nsm_config_yaml"])
        self.assertIn("nsm_config:", zone["nsm_config_yaml"])
        self.assertIn("sort_order: 10", zone["nsm_config_yaml"])
        object_link = next(row for row in preview_types if row["slug"] == "nsm_object_link")
        self.assertEqual(object_link["nsm_config_yaml"], "")
