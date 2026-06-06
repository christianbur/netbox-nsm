"""Tests for lazy rule cell selection helpers."""

from django.test import SimpleTestCase

from netbox_nsm.rule_field_selections import parse_rules_column_key


class RuleFieldSelectionsTests(SimpleTestCase):
    def test_parse_rules_column_key_object(self):
        area, type_key = parse_rules_column_key("source::ct_12")
        self.assertEqual(area, "source")
        self.assertEqual(type_key, "ct_12")
