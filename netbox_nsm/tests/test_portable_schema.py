"""Tests for bundled NSM schema JSON files."""

from unittest import TestCase

from netbox_nsm.bundles.schema_builder import build_schema_document
from netbox_nsm.type_metadata.specs import REQUIRED_COT_SLUGS
from netbox_nsm.rulebooks.templates import (
    DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG,
    DEMO_ZONE_MATRIX_RULEBOOK_SLUG,
    SCHEMA_DEMO_RULEBOOK_SLUG,
)

CORE_BUNDLE_TYPE_SLUGS = set(REQUIRED_COT_SLUGS) | {SCHEMA_DEMO_RULEBOOK_SLUG}
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
        self.assertNotIn(DEMO_ZONE_MATRIX_RULEBOOK_SLUG, slugs)
        for type_def in document["types"]:
            _assert_removed_fields_are_tombstones(type_def)
        self.assertIn("metadata", bundle)
        metadata = normalize_bundle_metadata(bundle)
        self.assertIn("types", metadata)
        self.assertTrue(metadata["types"])
        self.assertIn("rulebooks", metadata)
        self.assertIn(SCHEMA_DEMO_RULEBOOK_SLUG, metadata["rulebooks"])
        self.assertNotIn(DEMO_ZONE_MATRIX_RULEBOOK_SLUG, metadata["rulebooks"])

    def test_zone_matrix_demo_bundle_carries_rulebook_cot(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_matrix"))
        slugs = {t["slug"] for t in bundle.get("types") or []}
        self.assertEqual(slugs, {DEMO_ZONE_MATRIX_RULEBOOK_SLUG})
        metadata = normalize_bundle_metadata(bundle)
        self.assertIn(DEMO_ZONE_MATRIX_RULEBOOK_SLUG, metadata["rulebooks"])
        matrix_meta = metadata["rulebooks"][DEMO_ZONE_MATRIX_RULEBOOK_SLUG]
        self.assertTrue(matrix_meta["rulebook"].get("matrix_tab_enabled"))

    def test_zone_address_demo_bundle_carries_rulebook_cot(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        slugs = {t["slug"] for t in bundle.get("types") or []}
        self.assertEqual(slugs, {DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG})
        metadata = normalize_bundle_metadata(bundle)
        self.assertIn(DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG, metadata["rulebooks"])
        object_types = {entry.get("type") for entry in bundle.get("objects") or []}
        self.assertIn("nsm_zone", object_types)
        self.assertIn("nsm_address", object_types)
        self.assertIn(DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG, object_types)

    def test_zone_address_demo_bundle_seed_counts(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        counts = {
            entry.get("type"): len(entry.get("records") or [])
            for entry in bundle.get("objects") or []
        }
        self.assertEqual(counts["nsm_zone"], 20)
        self.assertEqual(counts["nsm_address"], 500)
        self.assertEqual(counts["nsm_address_group"], 100)
        self.assertEqual(counts[DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG], 500)

    def test_zone_address_demo_showcase_rules_have_varied_address_counts(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        rules = next(
            entry
            for entry in bundle.get("objects") or []
            if entry.get("type") == DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG
        )
        by_index = {record["index"]: record for record in rules.get("records") or []}
        for rule_index in range(1, 21):
            record = by_index[rule_index]
            src_count = len(record.get("source_addresses") or [])
            dst_count = len(record.get("destination_addresses") or [])
            self.assertGreaterEqual(src_count, 1)
            self.assertLessEqual(src_count, 20)
            self.assertGreaterEqual(dst_count, 1)
            self.assertLessEqual(dst_count, 20)
            for ref in (record.get("source_addresses") or []) + (
                record.get("destination_addresses") or []
            ):
                self.assertTrue(
                    ref.startswith("nsm_address/")
                    or ref.startswith("nsm_address_group/")
                    or ref.startswith("nsm_address_custom/")
                )

    def test_zone_address_demo_rulebook_allows_custom_addresses(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        rb_type = next(
            t for t in bundle.get("types") or [] if t.get("slug") == DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG
        )
        for field_name in ("source_addresses", "destination_addresses"):
            field = next(f for f in rb_type.get("fields") or [] if f.get("name") == field_name)
            self.assertIn(
                "custom-objects/nsm_address_custom",
                field.get("related_object_types") or [],
            )
        rules = next(
            entry
            for entry in bundle.get("objects") or []
            if entry.get("type") == DEMO_ZONE_ADDRESSES_RULEBOOK_SLUG
        )
        rule1 = next(r for r in rules.get("records") or [] if r.get("index") == 1)
        self.assertIn("nsm_address_custom/ANY", rule1.get("destination_addresses") or [])

    def test_zone_matrix_demo_bundle_has_matrix_seed_objects(self):
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_matrix"))
        object_types = {entry.get("type") for entry in bundle.get("objects") or []}
        self.assertIn("nsm_zone", object_types)
        self.assertIn(DEMO_ZONE_MATRIX_RULEBOOK_SLUG, object_types)
        rules = next(
            entry
            for entry in bundle.get("objects") or []
            if entry.get("type") == DEMO_ZONE_MATRIX_RULEBOOK_SLUG
        )
        self.assertEqual(len(rules.get("records") or []), 900)

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
        self.assertTrue(str(path).endswith("builtin/nsm_schema.json"))

    def test_nsm_object_link_is_link_table(self):
        bundle = load_bundle(bundle_json_path("nsm_schema"))
        object_link = next(
            t for t in bundle.get("types") or [] if t.get("slug") == "nsm_object_link"
        )
        self.assertTrue(object_link.get("link_table"))
        metadata = normalize_bundle_metadata(bundle)
        self.assertTrue(metadata["types"]["nsm_object_link"]["link_table"])
