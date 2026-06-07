"""Detail-page context for the virtual All Rules rulebook."""

from __future__ import annotations

from collections import OrderedDict
from types import SimpleNamespace

from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import Rulebook, RulebookFieldKind, RulebookTypeChoices
from netbox_nsm.rulebook_field_utils import load_rulebook_fields_for_detail

__all__ = (
    "build_virtual_all_rules_rulebook_display_field",
    "build_virtual_rulebook_detail_context",
    "load_virtual_all_rules_fields_for_detail",
    "sort_rulebook_fields_for_display",
)

VIRTUAL_ALL_RULES_FIELD_SLUG = "rulebook"


def sort_rulebook_fields_for_display(fields) -> list:
    """Stable column order: sort_order ascending, then slug."""
    return sorted(fields, key=lambda row: (row.sort_order, row.slug or ""))


def build_virtual_all_rules_rulebook_display_field():
    """Synthetic system field for All Rules (sort order 0, not stored in DB)."""
    return SimpleNamespace(
        slug=VIRTUAL_ALL_RULES_FIELD_SLUG,
        name=str(_("Rulebook")),
        sort_order=0,
        field_kind=RulebookFieldKind.SYSTEM,
        placement="system",
        visible=True,
        searchable=False,
        filterable=False,
        facet_mode="disabled",
        max_visible_pills=3,
        show_colored_pills=True,
        is_system_field=True,
        is_container_field=False,
        shows_field_level_facets=False,
        field_type_list=[],
        pk=None,
    )


def load_virtual_all_rules_fields_for_detail() -> list:
    """
    Union of rulebook fields across all policy rulebooks for read-only display.

    The first occurrence of each field slug wins for field-level attributes; nested
    type rows are merged by ``type_config_id``. Result is sorted by ``sort_order``,
    with the synthetic All Rules ``rulebook`` column first (sort order 0).
    """
    field_map: OrderedDict[str, object] = OrderedDict()
    type_ids_seen: dict[str, set[int]] = {}

    rulebooks = Rulebook.objects.filter(
        rulebook_type=RulebookTypeChoices.SECURITY_RULES
    ).order_by("name", "pk")

    for rulebook in rulebooks:
        for field in load_rulebook_fields_for_detail(rulebook):
            slug = field.slug
            if slug not in field_map:
                field_map[slug] = field
                field.field_type_list = list(field.field_type_list)
                type_ids_seen[slug] = {
                    ft.type_config_id for ft in field.field_type_list
                }
                continue

            existing = field_map[slug]
            if field.sort_order < existing.sort_order:
                existing.sort_order = field.sort_order
            for ft in field.field_type_list:
                tc_id = ft.type_config_id
                if tc_id in type_ids_seen[slug]:
                    continue
                existing.field_type_list.append(ft)
                type_ids_seen[slug].add(tc_id)

    fields = list(field_map.values())
    fields.append(build_virtual_all_rules_rulebook_display_field())
    return sort_rulebook_fields_for_display(fields)


def build_virtual_rulebook_detail_context(instance) -> dict:
    """Mirror ``RulebookView.get_extra_context`` for the virtual rulebook."""
    rulebook_fields = load_virtual_all_rules_fields_for_detail()
    rulebook_fields_system = [f for f in rulebook_fields if f.is_system_field]
    rulebook_fields_object = [f for f in rulebook_fields if not f.is_system_field]
    matching_classes: set[str] = set()
    for field in rulebook_fields_object:
        for ft in field.field_type_list:
            tc = ft.type_config
            if tc and tc.matching_class:
                matching_classes.add(tc.matching_class)

    return {
        "assignments": [],
        "rulebook_fields": rulebook_fields,
        "rulebook_fields_system": rulebook_fields_system,
        "rulebook_fields_object": rulebook_fields_object,
        "has_object_rulebook_fields": bool(rulebook_fields_object),
        "matching_classes": sorted(matching_classes),
        "rulebook_readonly": True,
    }
