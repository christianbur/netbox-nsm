"""Scale demo constants and helpers."""

import random

from django.test import SimpleTestCase

from netbox_nsm.demos.scale_test import (
    ACTION_RANDOM_SEED,
    RULE_COUNT,
    ZONE_COUNT,
    ZONE_NAME_PREFIX,
)


class ScaleDemoTests(SimpleTestCase):
    def test_zone_name_range(self):
        self.assertEqual(ZONE_NAME_PREFIX, "demo-")
        self.assertEqual(f"{ZONE_NAME_PREFIX}0001", "demo-0001")
        self.assertEqual(f"{ZONE_NAME_PREFIX}{ZONE_COUNT:04d}", "demo-0300")

    def test_random_permit_deny_mix(self):
        rng = random.Random(ACTION_RANDOM_SEED)
        permit_hits = sum(1 for _ in range(RULE_COUNT) if rng.random() < 0.5)
        self.assertGreater(permit_hits, RULE_COUNT // 4)
        self.assertLess(permit_hits, 3 * RULE_COUNT // 4)
