"""Tests for rulebook field group sort keys and display labels."""

from utilities.testing import TestCase

from netbox_nsm.rulebooks.rulebook_groups import (
    GROUP_COMMON,
    GROUP_SOURCE,
    default_group_name_map,
    resolve_group_name_for_display,
    rulebook_group_heading_parts,
    strip_rulebook_group_sort_prefix,
)
from netbox_nsm.rulebooks.templates import (
    _field_display_label,
    _field_display_label_from_cot_field,
)


class RulebookGroupDisplayTests(TestCase):
    def test_resolve_group_name_for_display_uses_defaults(self):
        self.assertEqual(resolve_group_name_for_display("2# Source"), "Source")
        self.assertEqual(resolve_group_name_for_display("1# Common"), "")
        self.assertEqual(resolve_group_name_for_display("5# Actions"), "")

    def test_strip_rulebook_group_sort_prefix(self):
        self.assertEqual(strip_rulebook_group_sort_prefix("2# Source"), "Source")
        self.assertEqual(strip_rulebook_group_sort_prefix("2# SOURCE"), "SOURCE")
        self.assertEqual(strip_rulebook_group_sort_prefix("Source"), "Source")

    def test_resolve_unknown_group_strips_sort_prefix(self):
        self.assertEqual(resolve_group_name_for_display("9# Other"), "Other")

    def test_resolve_group_name_is_case_insensitive_for_sort_key(self):
        self.assertEqual(resolve_group_name_for_display("2# SOURCE"), "Source")

    def test_rulebook_group_heading_parts_uses_fallback_label(self):
        heading = rulebook_group_heading_parts(GROUP_COMMON)
        self.assertEqual(heading, {"index_prefix": "1==", "label": "Common"})

    def test_rulebook_group_heading_parts_uses_display_label(self):
        heading = rulebook_group_heading_parts(GROUP_SOURCE)
        self.assertEqual(heading, {"index_prefix": "2==", "label": "Source"})


class RulebookGroupRulesLabelTests(TestCase):
    def test_field_display_label_resolves_sort_key(self):
        label = _field_display_label(
            {"label": "Zones", "group_name": GROUP_SOURCE},
        )
        self.assertEqual(label, "Zones (Source)")

    def test_field_display_label_empty_group_after_resolve(self):
        label = _field_display_label(
            {"label": "Actions", "group_name": "5# Actions"},
        )
        self.assertEqual(label, "Actions")

    def test_field_display_label_from_cot_field(self):
        from types import SimpleNamespace

        field = SimpleNamespace(
            label="Zones",
            name="source_zones",
            group_name=GROUP_SOURCE,
            custom_object_type=None,
        )
        self.assertEqual(
            _field_display_label_from_cot_field(field),
            "Zones (Source)",
        )

    def test_default_map_has_expected_entries(self):
        mapping = default_group_name_map()
        self.assertEqual(mapping[GROUP_SOURCE], "Source")
        self.assertEqual(mapping[GROUP_COMMON], "")
