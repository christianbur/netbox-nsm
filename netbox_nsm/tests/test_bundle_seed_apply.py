"""Tests for bundle seed apply helpers."""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from netbox_nsm.bundles.bundle_extensions import (
    _apply_seed_records_with_deferred_refs,
    diff_seed_objects,
)
from netbox_nsm.bundles.dispatch import load_bundle
from netbox_nsm.bundles.paths import bundle_json_path


class DiffSeedPendingRefTests(TestCase):
    def test_collect_pending_portable_refs_includes_all_seed_rows(self):
        from netbox_nsm.bundles.bundle_extensions import _collect_pending_portable_refs

        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        pending = _collect_pending_portable_refs(bundle.get("objects"))
        self.assertIn("nsm_address/demo-addr-host-001", pending)
        self.assertIn("nsm_zone/demo-addr-zone-01", pending)

    def test_diff_seed_objects_tolerates_missing_address_rows(self):
        from netbox_custom_objects.models import CustomObjectType

        cot = CustomObjectType.objects.filter(slug="nsm_address").first()
        if cot is None:
            self.skipTest("nsm_address COT not deployed")

        cot.get_model().objects.filter(name__startswith="demo-addr-host-").delete()
        bundle = load_bundle(bundle_json_path("nsm_demo_zone_address_adressgroup"))
        diffs = diff_seed_objects(bundle.get("objects"))
        self.assertIsInstance(diffs, list)
        self.assertGreater(len(diffs), 0)


class ApplySeedDeferredRefTests(SimpleTestCase):
    def test_retries_forward_portable_references(self):
        records = [
            {"name": "demo-ipa-grp-1"},
            {"name": "demo-ipa-grp-2"},
            {"name": "demo-ipa-grp-3"},
        ]
        attempts: dict[str, int] = {}

        def fake_apply(*, cot, model, serializer_class, record):
            name = record["name"]
            attempts[name] = attempts.get(name, 0) + 1
            if name == "demo-ipa-grp-1" and attempts[name] == 1:
                raise ValueError(
                    "Object not found for portable reference: "
                    "'nsm_address_group/demo-ipa-grp-2'"
                )
            return True

        with patch(
            "netbox_nsm.bundles.bundle_extensions._apply_one_seed_record",
            side_effect=fake_apply,
        ):
            seeded = _apply_seed_records_with_deferred_refs(
                records,
                cot=object(),
                model=object(),
                serializer_class=object(),
            )

        self.assertEqual(seeded, 3)
        self.assertEqual(attempts["demo-ipa-grp-1"], 2)
