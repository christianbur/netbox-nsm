"""Helpers for RulebookField layout (system + object columns)."""

from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _

from netbox_nsm.models import (
    RulebookField,
    RulebookFieldKind,
    RulebookFieldType,
    RulebookTypeChoices,
)

SYSTEM_RULEBOOK_FIELD_DEFAULTS = (
    {"slug": "index", "name": _("Index"), "sort_order": 1},
    {"slug": "status", "name": _("Status"), "sort_order": 2},
    {"slug": "name", "name": _("Name"), "sort_order": 3},
    {"slug": "description", "name": _("Description"), "sort_order": 100},
)

SYSTEM_FIELD_SLUGS = frozenset(spec["slug"] for spec in SYSTEM_RULEBOOK_FIELD_DEFAULTS)


def ensure_system_rulebook_fields(rulebook):
    """Create default system columns (Index, Status, Name, Description) if missing."""
    if rulebook.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
        return
    for spec in SYSTEM_RULEBOOK_FIELD_DEFAULTS:
        RulebookField.objects.get_or_create(
            rulebook=rulebook,
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "sort_order": spec["sort_order"],
                "field_kind": RulebookFieldKind.SYSTEM,
                "placement": "system",
                "visible": True,
                "searchable": spec["slug"] in {"name", "description"},
                "filterable": spec["slug"] in {"name", "description"},
                "facet_mode": "disabled",
            },
        )


def get_visible_rulebook_fields(rulebook):
    ensure_system_rulebook_fields(rulebook)
    return list(
        RulebookField.objects.filter(rulebook=rulebook, visible=True)
        .prefetch_related("type_configs__type_config__content_type")
        .order_by("sort_order", "slug")
    )


def load_rulebook_fields_for_detail(rulebook):
    """
    Rulebook detail: all fields with ordered type_configs on ``field.field_type_list``.
    """
    ensure_system_rulebook_fields(rulebook)
    type_qs = RulebookFieldType.objects.select_related(
        "type_config__content_type"
    ).order_by("sort_order", "pk")
    fields = list(
        RulebookField.objects.filter(rulebook=rulebook)
        .prefetch_related(Prefetch("type_configs", queryset=type_qs))
        .order_by("sort_order", "slug")
    )
    for field in fields:
        field.field_type_list = list(field.type_configs.all())
    return fields


def get_rules_column_slugs(rulebook):
    return [field.slug for field in get_visible_rulebook_fields(rulebook)]


def get_rules_column_labels(rulebook):
    return {field.slug: field.name for field in get_visible_rulebook_fields(rulebook)}


def rulebook_has_object_field(rulebook, slug):
    return RulebookField.objects.filter(
        rulebook=rulebook,
        slug=slug,
        field_kind=RulebookFieldKind.OBJECT,
        visible=True,
    ).exists()


def serialize_rulebook_fields_layout(rulebook):
    """Compact field layout for Rulebook changelog snapshots (dict, not list).

    NetBox ``deep_compare_dict`` only recurses into nested dicts. Lists are
    replaced wholesale in the diff view — use slug/type keys so small edits
    stay readable.
    """
    layout = {}
    for field in load_rulebook_fields_for_detail(rulebook):
        type_rows = {}
        for ft in field.field_type_list:
            tc_key = str(ft.type_config_id)
            type_rows[tc_key] = {
                "sort_order": ft.sort_order,
                "visible": ft.visible,
                "max_items": ft.max_items,
                "name_filter_regex": ft.name_filter_regex or "",
            }
        layout[field.slug] = {
            "name": field.name,
            "sort_order": field.sort_order,
            "placement": field.placement,
            "field_kind": field.field_kind,
            "visible": field.visible,
            "searchable": field.searchable,
            "filterable": field.filterable,
            "facet_mode": field.facet_mode,
            "max_visible_pills": field.max_visible_pills,
            "types": type_rows,
        }
    return layout
