"""Tests for rulebook field group display (COT-defined ``group_name`` only)."""

from unittest.mock import patch

from utilities.testing import TestCase

from netbox_nsm.rulebooks.rulebook_groups import (
    apply_schema_yaml_field_groups,
    resolve_group_name_for_display,
    rulebook_group_heading_parts,
    strip_rulebook_group_sort_prefix,
)
from netbox_nsm.rulebooks.templates import (
    _field_display_label,
    _field_display_label_from_cot_field,
)


class RulebookGroupDisplayTests(TestCase):
    def test_resolve_group_name_for_display_is_pass_through(self):
        self.assertEqual(resolve_group_name_for_display("2# Source"), "2# Source")
        self.assertEqual(resolve_group_name_for_display("Source"), "Source")
        self.assertEqual(resolve_group_name_for_display(""), "")

    def test_strip_rulebook_group_sort_prefix(self):
        self.assertEqual(strip_rulebook_group_sort_prefix("2# Source"), "Source")
        self.assertEqual(strip_rulebook_group_sort_prefix("2# SOURCE"), "SOURCE")
        self.assertEqual(strip_rulebook_group_sort_prefix("Source"), "Source")

    def test_rulebook_group_heading_parts_from_cot_label(self):
        heading = rulebook_group_heading_parts("1# Common")
        self.assertEqual(heading, {"index_prefix": "1==", "label": "1# Common"})

        heading = rulebook_group_heading_parts("Custom Section")
        self.assertEqual(heading, {"index_prefix": "", "label": "Custom Section"})


class RulebookGroupRulesLabelTests(TestCase):
    def test_field_display_label_uses_cot_group_name(self):
        label = _field_display_label(
            {"label": "Zones", "group_name": "2# Source"},
        )
        self.assertEqual(label, "Zones (2# Source)")

    def test_field_display_label_without_group(self):
        label = _field_display_label({"label": "Source", "group_name": ""})
        self.assertEqual(label, "Source")

    def test_field_display_label_from_cot_field(self):
        from types import SimpleNamespace

        field = SimpleNamespace(
            label="Zones",
            name="source_zones",
            group_name="Source Area",
            custom_object_type=None,
        )
        self.assertEqual(
            _field_display_label_from_cot_field(field),
            "Zones (Source Area)",
        )


class ApplySchemaYamlFieldGroupsTests(TestCase):
    def test_clears_group_name_when_not_in_schema(self):
        from types import SimpleNamespace

        field = SimpleNamespace(
            name="source",
            group_name="2# Source",
            save=SimpleNamespace(),
        )
        field.save = lambda **kwargs: None
        cot = SimpleNamespace(slug="nsm_rb_demo_zone_matrix", fields=SimpleNamespace(all=lambda: [field]))
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
        cot = SimpleNamespace(slug="nsm_rb_demo_zone_matrix", fields=SimpleNamespace(all=lambda: [field]))
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
                        "group_name": "Source",
                    }
                ],
            )
        self.assertEqual(updated, 1)
        self.assertEqual(field.group_name, "Source")
