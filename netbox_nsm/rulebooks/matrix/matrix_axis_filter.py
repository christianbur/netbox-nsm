"""OR/AND text filters for matrix axis search."""

from __future__ import annotations

import re


def parse_axis_filter_groups(query: str) -> list[list[str]]:
    raw = (query or "").strip()
    if not raw:
        return []
    groups: list[list[str]] = []
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


def filter_objects_by_axis_query(objects, query: str, label_fn) -> list:
    """Keep objects whose label matches the corner filter query."""
    groups = parse_axis_filter_groups(query)
    if not groups:
        return list(objects)
    return [obj for obj in objects if matches_axis_filter_groups(label_fn(obj), groups)]
