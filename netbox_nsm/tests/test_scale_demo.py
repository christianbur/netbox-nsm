"""Scale demo constants and helpers."""

import random

from django.test import SimpleTestCase

from netbox_nsm.demos.scale_test import (
    ACTION_RANDOM_SEED,
    GRID_SIZE,
    RULE_COUNT,
    ZONE_COUNT,
    ZONE_NAME_PREFIX,
    _matrix_indices,
)


class ScaleDemoTests(SimpleTestCase):
    def test_grid_dimensions(self):
        self.assertEqual(GRID_SIZE, 100)
        self.assertEqual(ZONE_COUNT, 100)
        self.assertEqual(RULE_COUNT, 10_000)

    def test_zone_name_range(self):
        self.assertEqual(ZONE_NAME_PREFIX, "demo-")
        self.assertEqual(f"{ZONE_NAME_PREFIX}0001", "demo-0001")
        self.assertEqual(f"{ZONE_NAME_PREFIX}{ZONE_COUNT:04d}", "demo-0100")

    def test_matrix_indices_cover_full_grid(self):
        pairs = {_matrix_indices(i) for i in range(RULE_COUNT)}
        self.assertEqual(len(pairs), RULE_COUNT)
        self.assertEqual(_matrix_indices(0), (0, 0))
        self.assertEqual(_matrix_indices(99), (0, 99))
        self.assertEqual(_matrix_indices(100), (1, 0))
        self.assertEqual(_matrix_indices(RULE_COUNT - 1), (99, 99))

    def test_random_permit_deny_mix(self):
        rng = random.Random(ACTION_RANDOM_SEED)
        permit_hits = sum(1 for _ in range(RULE_COUNT) if rng.random() < 0.5)
        self.assertGreater(permit_hits, RULE_COUNT // 4)
        self.assertLess(permit_hits, 3 * RULE_COUNT // 4)
