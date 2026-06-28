"""Tests for bundled NSM schema JSON files."""

from unittest import TestCase

from netbox_nsm.bundles.schema_builder import build_schema_document
from netbox_nsm.objects.type_config_specs import REQUIRED_COT_SLUGS

CORE_BUNDLE_TYPE_SLUGS = set(REQUIRED_COT_SLUGS) | {"nsm_rb_demo"}
from netbox_nsm.bundles.dispatch import load_bundle, normalize_bundle_metadata, to_portable_document
from netbox_nsm.bundles.paths import BUILTIN_DIR, bundle_json_path


def _assert_removed_fields_are_tombstones(type_def: dict) -> None:
    removed_ids = {f["id"] for f in type_def.get("fields", [])}
    for entry in type_def.get("removed_fields", []):
        assert isinstance(entry, dict), type_def["slug"]
        assert "id" in entry and "name" in entry and "type" in entry, entry
        assert entry["id"] not in removed_ids, type_def["slug"]


class PortableSchemaTests(TestCase):
    def test_nsm_schema_bundle(self):
        bundle = load_bundle(bundle_json_path("nsm_schema"))
        self.assertEqual(bundle["schema_type"], "nsm")
        document = to_portable_document(bundle)
        self.assertEqual(document["schema_version"], "1")
        slugs = {t["slug"] for t in document["types"]}
        self.assertEqual(slugs, CORE_BUNDLE_TYPE_SLUGS)
        for type_def in document["types"]:
            _assert_removed_fields_are_tombstones(type_def)
        self.assertIn("metadata", bundle)
        metadata = normalize_bundle_metadata(bundle)
        self.assertIn("types", metadata)
        self.assertTrue(metadata["types"])
        self.assertIn("rulebooks", metadata)
        self.assertIn("nsm_rb_demo", metadata["rulebooks"])

    def test_build_schema_document_matches_schema_policy_types(self):
        built = build_schema_document()
        bundle = load_bundle(bundle_json_path("nsm_schema"))
        self.assertTrue(
            set(REQUIRED_COT_SLUGS).issubset({t["slug"] for t in built["types"]})
        )
        self.assertTrue(
            set(REQUIRED_COT_SLUGS).issubset({t["slug"] for t in bundle["types"]})
        )

    def test_legacy_data_dir_removed(self):
        self.assertFalse((BUILTIN_DIR.parent / "data").is_dir())

    def test_nsm_schema_lives_under_builtin(self):
        path = bundle_json_path("nsm_schema")
        self.assertTrue(str(path).endswith("builtin/nsm_schema/bundle.json"))
