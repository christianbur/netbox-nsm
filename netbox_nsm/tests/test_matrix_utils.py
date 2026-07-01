"""Tests for zone matrix helper utilities."""

from django.test import SimpleTestCase

from netbox_nsm.rulebooks.matrix.matrix_utils import (
    MATRIX_VIEWPORT_DEFAULT_COLS,
    MATRIX_VIEWPORT_DEFAULT_ROWS,
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


class MatrixViewportDefaultsTests(SimpleTestCase):
    def test_default_viewport_is_fifty_by_fifty(self):
        self.assertEqual(MATRIX_VIEWPORT_DEFAULT_ROWS, 50)
        self.assertEqual(MATRIX_VIEWPORT_DEFAULT_COLS, 50)


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
