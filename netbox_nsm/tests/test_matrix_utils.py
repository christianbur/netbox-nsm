"""Tests for zone matrix helper utilities."""

from types import SimpleNamespace

from django.test import SimpleTestCase

from netbox_nsm.matrix_utils import (
    MATRIX_FILTER_AUTO_COUNT,
    MATRIX_FILTER_AUTO_THRESHOLD,
    apply_default_matrix_axis_filters,
    dedupe_matrix_object_types,
    matrix_axis_display_label,
    resolve_matrix_object_type_selection,
)


class DedupeMatrixObjectTypesTests(SimpleTestCase):
    def test_keeps_one_entry_per_label_case_insensitive(self):
        entries = [
            {"ct_id": 10, "label": "Zones"},
            {"ct_id": 20, "label": "zones"},
            {"ct_id": 30, "label": "Prefixes"},
        ]
        deduped = dedupe_matrix_object_types(entries)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["ct_id"], 10)
        self.assertEqual(deduped[0]["label"], "Zones")
        self.assertEqual(deduped[1]["label"], "Prefixes")

    def test_resolve_maps_removed_duplicate_to_canonical_ct(self):
        raw = [
            {"ct_id": 10, "label": "Zones"},
            {"ct_id": 20, "label": "Zones"},
        ]
        available = dedupe_matrix_object_types(raw)
        resolved = resolve_matrix_object_type_selection(
            20,
            raw_types=raw,
            available_types=available,
        )
        self.assertEqual(resolved, 10)


class DefaultMatrixAxisFilterTests(SimpleTestCase):
    def _zones(self, count: int):
        return [SimpleNamespace(pk=i) for i in range(1, count + 1)]

    def test_leaves_explicit_filters_unchanged(self):
        zones = self._zones(250)
        src, dst = apply_default_matrix_axis_filters(
            zones,
            src_filter_pks={5},
            dst_filter_pks=set(),
        )
        self.assertEqual(src, {5})
        self.assertEqual(dst, set())

    def test_no_default_when_at_or_below_threshold(self):
        zones = self._zones(MATRIX_FILTER_AUTO_THRESHOLD)
        src, dst = apply_default_matrix_axis_filters(
            zones,
            src_filter_pks=set(),
            dst_filter_pks=set(),
        )
        self.assertEqual(src, set())
        self.assertEqual(dst, set())

    def test_selects_first_ten_when_above_threshold(self):
        zones = self._zones(MATRIX_FILTER_AUTO_THRESHOLD + 1)
        src, dst = apply_default_matrix_axis_filters(
            zones,
            src_filter_pks=set(),
            dst_filter_pks=set(),
        )
        expected = set(range(1, MATRIX_FILTER_AUTO_COUNT + 1))
        self.assertEqual(src, expected)
        self.assertEqual(dst, expected)


class MatrixAxisDisplayLabelTests(SimpleTestCase):
    def test_keeps_label_up_to_max_chars_without_ellipsis(self):
        text = "a" * 100
        self.assertEqual(matrix_axis_display_label(text), text)
        self.assertNotIn("…", matrix_axis_display_label(text))
        self.assertNotIn("...", matrix_axis_display_label(text))

    def test_truncates_beyond_max_without_ellipsis(self):
        text = "b" * 120
        result = matrix_axis_display_label(text)
        self.assertEqual(len(result), 100)
        self.assertEqual(result, "b" * 100)
