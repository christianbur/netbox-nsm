"""Tests for bundle seed apply helpers."""

from unittest.mock import patch

from django.test import SimpleTestCase

from netbox_nsm.bundles.bundle_extensions import _apply_seed_records_with_deferred_refs


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
