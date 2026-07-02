"""Tests that builtin schema bundles ship with the installed package."""

from importlib import resources

from django.test import SimpleTestCase

from netbox_nsm.bundles.dispatch import discover_schema_files
from netbox_nsm.bundles.paths import BUILTIN_DIR, find_bundle_paths

BUILTIN_BUNDLE_SLUGS = (
    "nsm_schema",
    "nsm_demo_zone_matrix",
    "nsm_demo_zone_address_adressgroup",
)


class BuiltinBundleDiscoveryTests(SimpleTestCase):
    def test_builtin_json_files_are_packaged(self):
        package = resources.files("netbox_nsm")
        for slug in BUILTIN_BUNDLE_SLUGS:
            path = package / "bundles" / "builtin" / f"{slug}.json"
            self.assertTrue(path.is_file(), f"missing packaged bundle: {path}")

    def test_find_bundle_paths_discovers_builtin_slugs(self):
        paths = find_bundle_paths()
        self.assertEqual(set(BUILTIN_BUNDLE_SLUGS), set(paths))
        for slug in BUILTIN_BUNDLE_SLUGS:
            self.assertTrue(paths[slug].is_file(), slug)
            self.assertEqual(paths[slug].parent, BUILTIN_DIR)

    def test_discover_schema_files_returns_all_builtin_bundles(self):
        discovered = {path.stem for path in discover_schema_files()}
        self.assertEqual(set(BUILTIN_BUNDLE_SLUGS), discovered)
