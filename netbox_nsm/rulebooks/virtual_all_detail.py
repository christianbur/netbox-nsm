"""Detail-page context for the virtual All Rules rulebook."""

from __future__ import annotations

from types import SimpleNamespace

from django.utils.translation import gettext_lazy as _

from netbox_nsm.rulebooks.registry import iter_deployed_cot_rulebooks

__all__ = (
    "build_virtual_rulebook_detail_context",
    "sort_rulebook_fields_for_display",
)

VIRTUAL_ALL_RULES_FIELD_SLUG = "rulebook"


def sort_rulebook_fields_for_display(fields) -> list:
    return sorted(fields, key=lambda row: (row.sort_order, row.slug or ""))


def _field_from_cot(cot_field) -> SimpleNamespace:
    from extras.choices import CustomFieldTypeChoices

    field_kind = "system" if cot_field.name in {
        "index",
        "status",
        "name",
        "description",
    } else "object"
    type_list = []
    if cot_field.type == CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        if cot_field.is_polymorphic:
            for ot in cot_field.related_object_types.all():
                type_list.append(
                    SimpleNamespace(
                        type_config=SimpleNamespace(
                            name=ot.model,
                            content_type_id=None,
                        ),
                        type_config_id=None,
                        visible=True,
                    )
                )
        elif cot_field.related_object_type_id:
            ot = cot_field.related_object_type
            type_list.append(
                SimpleNamespace(
                    type_config=SimpleNamespace(
                        name=ot.model,
                        content_type_id=None,
                    ),
                    type_config_id=None,
                    visible=True,
                )
            )

    return SimpleNamespace(
        slug=cot_field.name,
        name=cot_field.label or cot_field.name,
        sort_order=cot_field.weight,
        field_kind=field_kind,
        placement="system" if field_kind == "system" else "object",
        visible=True,
        searchable=True,
        filterable=True,
        facet_mode="disabled",
        max_visible_pills=5,
        show_colored_pills=True,
        is_system_field=field_kind == "system",
        is_container_field=bool(type_list),
        shows_field_level_facets=False,
        field_type_list=type_list,
        pk=None,
    )


def _load_all_rules_union_fields() -> list:
    seen: dict[str, object] = {}
    for cot in iter_deployed_cot_rulebooks():
        for field in cot.fields.exclude(ui_visible="hidden").order_by("weight", "name"):
            if field.name not in seen:
                seen[field.name] = _field_from_cot(field)
    fields = list(seen.values())
    fields.insert(
        0,
        SimpleNamespace(
            slug=VIRTUAL_ALL_RULES_FIELD_SLUG,
            name=str(_("Rulebook")),
            sort_order=0,
            field_kind="system",
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
        ),
    )
    return sort_rulebook_fields_for_display(fields)


def build_virtual_rulebook_detail_context(instance) -> dict:
    rulebook_fields = _load_all_rules_union_fields()
    rulebook_fields_system = [f for f in rulebook_fields if f.is_system_field]
    rulebook_fields_object = [f for f in rulebook_fields if not f.is_system_field]

    return {
        "assignments": [],
        "assigned_objects_panel": {
            "hosts": [],
            "add_url": None,
            "can_add": False,
            "can_delete": False,
            "can_assign_links": False,
            "is_empty": True,
        },
        "rulebook_fields": rulebook_fields,
        "rulebook_fields_system": rulebook_fields_system,
        "rulebook_fields_object": rulebook_fields_object,
        "has_object_rulebook_fields": bool(rulebook_fields_object),
        "matching_classes": [],
        "rulebook_readonly": True,
    }
