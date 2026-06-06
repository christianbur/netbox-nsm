"""Tests for bundled portable schema documents."""

import json
from pathlib import Path
from unittest import TestCase

from netbox_nsm.custom_objects_schema import (
    CHOICE_SETS_PATH,
    PORTABLE_SCHEMA_PATH,
    build_choice_set_specs,
    build_schema_document,
    choice_set_names_in_document,
    load_choice_set_specs,
    load_portable_schema_document,
)
from netbox_nsm.type_config_specs import REQUIRED_COT_SLUGS


class PortableSchemaTests(TestCase):
    def test_schema_file_exists_and_matches_spec(self):
        document = load_portable_schema_document()
        self.assertEqual(document["schema_version"], "1")
        self.assertIsInstance(document["types"], list)
        slugs = {t["slug"] for t in document["types"]}
        self.assertEqual(slugs, set(REQUIRED_COT_SLUGS))

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
