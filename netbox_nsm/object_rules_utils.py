"""Helpers for object detail → rulebook rules grid filter links."""

from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from netbox_nsm.display_utils import get_display_template_map, render_object_display
from netbox_nsm.rulebook_rules_tab import RULES_FILTER_PREFIX, _rules_param_token

__all__ = (
    "build_matrix_cell_rules_filter_url",
    "build_object_field_column_filter_url",
    "build_object_field_rules_filter_url",
    "build_rule_name_column_filter_url",
    "build_rulebooks_panel_url",
    "build_rules_column_filter_url",
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


def build_rules_column_filter_url(
    rulebook,
    column_key: str,
    filter_text: str,
) -> str:
    """Rules tab URL with a single per-column quick-search param (``f_*``)."""
    if not rulebook or column_key is None or filter_text is None:
        return ""
    text = str(filter_text).strip()
    if not text:
        return ""
    base = reverse("plugins:netbox_nsm:rulebook_rules", args=[rulebook.pk])
    param = f"{RULES_FILTER_PREFIX}{_rules_param_token(column_key)}"
    return f"{base}?{param}={quote(text, safe='')}"


def build_rule_name_column_filter_url(rulebook, rule) -> str:
    """Rules tab filtered to rows whose Name column contains *rule*.name."""
    if not rulebook or not rule:
        return ""
    return build_rules_column_filter_url(rulebook, "name", rule.name)


def build_object_field_column_filter_url(
    rulebook,
    field,
    obj,
    content_type,
    *,
    display_template_map=None,
) -> str:
    """
    Rules tab URL with the object-type column quick filter for *field*.

    Uses the column key ``{field.slug}::ct_{content_type.pk}`` and the rendered
    display name of *obj* as the search string.
    """
    if not rulebook or not field or obj is None or content_type is None:
        return ""
    slug = getattr(field, "slug", None) or ""
    if not slug:
        return ""
    tmpl_map = (
        display_template_map
        if display_template_map is not None
        else get_display_template_map()
    )
    obj_name = render_object_display(obj, content_type.pk, tmpl_map)
    column_key = f"{slug}::ct_{content_type.pk}"
    return build_rules_column_filter_url(rulebook, column_key, obj_name)


def build_object_field_rules_filter_url(
    rulebook,
    field,
    obj,
    content_type,
    *,
    display_template_map=None,
) -> str:
    """Backward-compatible alias for the column quick-filter URL."""
    return build_object_field_column_filter_url(
        rulebook,
        field,
        obj,
        content_type,
        display_template_map=display_template_map,
    )


def build_rulebooks_panel_url(rulebook_groups: list) -> str:
    """Top-level Security panel Rulebooks header link target."""
    if not rulebook_groups:
        return ""
    if len(rulebook_groups) == 1:
        rb = rulebook_groups[0].get("rulebook")
        if rb is not None:
            return rb.get_absolute_url()
    return reverse("plugins:netbox_nsm:rulebook_list")
