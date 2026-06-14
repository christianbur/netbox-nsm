"""Helpers for object detail → COT rulebook rules grid filter links."""

from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from netbox_nsm.rulebooks.rules_tab import RULES_FILTER_PREFIX, _rules_param_token

__all__ = (
    "build_cot_object_field_column_filter_url",
    "build_cot_rule_name_column_filter_url",
    "build_cot_rules_column_filter_url",
    "build_matrix_cell_rules_filter_url",
    "build_rulebooks_panel_url",
)


def build_matrix_cell_rules_filter_url(
    rules_url_base: str,
    *,
    src_column_key: str,
    dst_column_key: str,
    src_filter: str,
    dst_filter: str,
) -> str:
    """Rules tab URL with source and destination column quick-search filters."""
    src_text = str(src_filter or "").strip()
    dst_text = str(dst_filter or "").strip()
    if not rules_url_base or not src_column_key or not dst_column_key:
        return ""
    if not src_text or not dst_text:
        return ""
    src_param = f"{RULES_FILTER_PREFIX}{_rules_param_token(src_column_key)}"
    dst_param = f"{RULES_FILTER_PREFIX}{_rules_param_token(dst_column_key)}"
    sep = "&" if "?" in rules_url_base else "?"
    return (
        f"{rules_url_base}{sep}"
        f"{src_param}={quote(src_text, safe='')}"
        f"&{dst_param}={quote(dst_text, safe='')}"
    )


def build_cot_rules_column_filter_url(
    rulebook_slug: str,
    column_key: str,
    filter_text: str,
) -> str:
    """COT rules tab URL with a single per-column quick-search param."""
    if not rulebook_slug or column_key is None or filter_text is None:
        return ""
    text = str(filter_text).strip()
    if not text:
        return ""
    base = reverse(
        "plugins:netbox_nsm:cot_rulebook_rules",
        kwargs={"slug": rulebook_slug},
    )
    param = f"{RULES_FILTER_PREFIX}{_rules_param_token(column_key)}"
    return f"{base}?{param}={quote(text, safe='')}"


def build_cot_rule_name_column_filter_url(rulebook_slug: str, rule_name: str) -> str:
    if not rulebook_slug or not rule_name:
        return ""
    return build_cot_rules_column_filter_url(rulebook_slug, "name", rule_name)


def build_cot_object_field_column_filter_url(
    rulebook_slug: str,
    column_key: str,
    filter_text: str,
) -> str:
    return build_cot_rules_column_filter_url(rulebook_slug, column_key, filter_text)


def build_rulebooks_panel_url(rulebook_groups: list) -> str:
    """Top-level Security panel Rulebooks header link target."""
    if not rulebook_groups:
        return ""
    if len(rulebook_groups) == 1:
        rb = rulebook_groups[0].get("rulebook")
        if rb is not None:
            return rb.get_absolute_url()
    return reverse("plugins:netbox_nsm:rulebook_list")
