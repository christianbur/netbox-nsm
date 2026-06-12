"""Tests for rulebook field group sort keys and display labels."""

from unittest.mock import patch

from utilities.testing import TestCase

from netbox_nsm.rulebooks.rulebook_groups import (
    GROUP_COMMON,
    GROUP_SOURCE,
    apply_schema_yaml_field_groups,
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
    def test_resolve_group_name_for_display_shows_sort_prefix(self):
        self.assertEqual(resolve_group_name_for_display("2# Source"), "2# Source")
        self.assertEqual(resolve_group_name_for_display("1# Common"), "1# Common")
        self.assertEqual(resolve_group_name_for_display("5# Actions"), "5# Actions")

    def test_strip_rulebook_group_sort_prefix(self):
        self.assertEqual(strip_rulebook_group_sort_prefix("2# Source"), "Source")
        self.assertEqual(strip_rulebook_group_sort_prefix("2# SOURCE"), "SOURCE")
        self.assertEqual(strip_rulebook_group_sort_prefix("Source"), "Source")

    def test_resolve_unknown_group_keeps_sort_prefix(self):
        self.assertEqual(resolve_group_name_for_display("9# Other"), "9# Other")

    def test_resolve_group_name_is_case_insensitive_for_sort_key(self):
        self.assertEqual(resolve_group_name_for_display("2# SOURCE"), "2# Source")

    def test_rulebook_group_heading_parts_uses_full_label(self):
        heading = rulebook_group_heading_parts(GROUP_COMMON)
        self.assertEqual(heading, {"index_prefix": "1==", "label": "1# Common"})

    def test_rulebook_group_heading_parts_uses_display_label(self):
        heading = rulebook_group_heading_parts(GROUP_SOURCE)
        self.assertEqual(heading, {"index_prefix": "2==", "label": "2# Source"})


class RulebookGroupRulesLabelTests(TestCase):
    def test_field_display_label_resolves_sort_key(self):
        label = _field_display_label(
            {"label": "Zones", "group_name": GROUP_SOURCE},
        )
        self.assertEqual(label, "Zones (2# Source)")

    def test_field_display_label_shows_group_with_sort_prefix(self):
        label = _field_display_label(
            {"label": "Actions", "group_name": "5# Actions"},
        )
        self.assertEqual(label, "Actions (5# Actions)")

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
            "Zones (2# Source)",
        )

    def test_default_map_has_expected_entries(self):
        mapping = default_group_name_map()
        self.assertEqual(mapping[GROUP_SOURCE], GROUP_SOURCE)
        self.assertEqual(mapping[GROUP_COMMON], GROUP_COMMON)


class ApplySchemaYamlFieldGroupsTests(TestCase):
    def test_clears_group_name_when_not_in_schema(self):
        from types import SimpleNamespace

        field = SimpleNamespace(
            name="source",
            group_name="2# Source",
            save=SimpleNamespace(),
        )
        field.save = lambda **kwargs: None
        cot = SimpleNamespace(slug="nsm_rb_demo", fields=SimpleNamespace(all=lambda: [field]))
        with patch(
            "netbox_nsm.rulebooks.rulebook_groups._is_rulebook_cot_slug",
            return_value=True,
        ), patch(
            "netbox_nsm.rulebooks.rulebook_groups.clear_legacy_nsm_setting_comments",
            return_value=False,
        ):
            updated = apply_schema_yaml_field_groups(
                cot,
                [{"name": "source", "type": "multiobject", "label": "Source"}],
            )
        self.assertEqual(updated, 1)
        self.assertEqual(field.group_name, "")

    def test_keeps_group_name_when_declared_in_schema(self):
        from types import SimpleNamespace

        field = SimpleNamespace(name="source", group_name="", save=SimpleNamespace())
        saved = {}

        def _save(**kwargs):
            saved.update(kwargs)

        field.save = _save
        cot = SimpleNamespace(slug="nsm_rb_demo", fields=SimpleNamespace(all=lambda: [field]))
        with patch(
            "netbox_nsm.rulebooks.rulebook_groups._is_rulebook_cot_slug",
            return_value=True,
        ), patch(
            "netbox_nsm.rulebooks.rulebook_groups.clear_legacy_nsm_setting_comments",
            return_value=False,
        ):
            updated = apply_schema_yaml_field_groups(
                cot,
                [
                    {
                        "name": "source",
                        "type": "multiobject",
                        "label": "Source",
                        "group_name": "2# Source",
                    }
                ],
            )
        self.assertEqual(updated, 1)
        self.assertEqual(field.group_name, "2# Source")
