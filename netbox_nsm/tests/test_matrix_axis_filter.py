"""Matrix corner axis filter — OR / AND parsing (mirrors matrix_ag_grid.js)."""

import re

from django.test import SimpleTestCase


def parse_axis_filter_groups(query: str) -> list[list[str]]:
    raw = (query or "").strip()
    if not raw:
        return []
    groups = []
    for or_part in re.split(r"\s+OR\s+", raw, flags=re.IGNORECASE):
        and_terms = [
            part.strip().lower()
            for part in re.split(r"\s+(?:AND|&&)\s+", or_part, flags=re.IGNORECASE)
            if part.strip()
        ]
        if and_terms:
            groups.append(and_terms)
    return groups


def matches_axis_filter_groups(text: str, groups: list[list[str]]) -> bool:
    if not groups:
        return True
    haystack = (text or "").lower()
    return any(all(term in haystack for term in and_terms) for and_terms in groups)


class MatrixAxisFilterTests(SimpleTestCase):
    def test_parse_or_terms(self):
        self.assertEqual(parse_axis_filter_groups("dmz OR mgmt"), [["dmz"], ["mgmt"]])
        self.assertEqual(parse_axis_filter_groups("dmz or mgmt"), [["dmz"], ["mgmt"]])

    def test_parse_and_terms(self):
        self.assertEqual(parse_axis_filter_groups("ad AND app"), [["ad", "app"]])
        self.assertEqual(parse_axis_filter_groups("ad and app"), [["ad", "app"]])
        self.assertEqual(parse_axis_filter_groups("ad && app"), [["ad", "app"]])

    def test_parse_or_and_combined(self):
        self.assertEqual(
            parse_axis_filter_groups("dmz OR mgmt AND prod"),
            [["dmz"], ["mgmt", "prod"]],
        )
        self.assertEqual(
            parse_axis_filter_groups("ad AND app OR dev-1"),
            [["ad", "app"], ["dev-1"]],
        )

    def test_single_term(self):
        self.assertEqual(parse_axis_filter_groups("dev-1"), [["dev-1"]])

    def test_matches_or_substrings(self):
        self.assertTrue(matches_axis_filter_groups("dmz", [["dmz"], ["mgmt"]]))
        self.assertTrue(matches_axis_filter_groups("mgmt", [["dmz"], ["mgmt"]]))
        self.assertFalse(matches_axis_filter_groups("trust", [["dmz"], ["mgmt"]]))

    def test_matches_and_substrings(self):
        self.assertTrue(matches_axis_filter_groups("admin-app-zone", [["ad", "app"]]))
        self.assertFalse(matches_axis_filter_groups("admin-only", [["ad", "app"]]))

    def test_matches_or_and_combined(self):
        self.assertTrue(
            matches_axis_filter_groups("mgmt-production", [["dmz"], ["mgmt", "prod"]])
        )
        self.assertFalse(
            matches_axis_filter_groups("mgmt-staging", [["dmz"], ["mgmt", "prod"]])
        )
