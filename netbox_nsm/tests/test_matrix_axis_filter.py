"""Matrix corner axis filter — AND term parsing (mirrors matrix_ag_grid.js)."""

import re

from django.test import SimpleTestCase


def parse_axis_filter_terms(query: str) -> list[str]:
    raw = (query or "").strip()
    if not raw:
        return []
    return [
        part.strip().lower()
        for part in re.split(r"\s+(?:AND|&&)\s+", raw, flags=re.IGNORECASE)
        if part.strip()
    ]


def matches_all_axis_terms(text: str, terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = (text or "").lower()
    return all(term in haystack for term in terms)


class MatrixAxisFilterTests(SimpleTestCase):
    def test_parse_and_terms(self):
        self.assertEqual(parse_axis_filter_terms("ad AND app"), ["ad", "app"])
        self.assertEqual(parse_axis_filter_terms("ad and app"), ["ad", "app"])
        self.assertEqual(parse_axis_filter_terms("ad && app"), ["ad", "app"])
        self.assertEqual(parse_axis_filter_terms("  ad  AND  app  "), ["ad", "app"])

    def test_single_term(self):
        self.assertEqual(parse_axis_filter_terms("dev-1"), ["dev-1"])

    def test_matches_all_substrings(self):
        self.assertTrue(matches_all_axis_terms("admin-app-zone", ["ad", "app"]))
        self.assertTrue(matches_all_axis_terms("ad-app-server", ["ad", "app"]))
        self.assertFalse(matches_all_axis_terms("admin-only", ["ad", "app"]))
        self.assertFalse(matches_all_axis_terms("application", ["ad", "app"]))
