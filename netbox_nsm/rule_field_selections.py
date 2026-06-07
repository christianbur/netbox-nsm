"""Helpers for lazy-loaded rule cell editing in the Rules tab."""

from __future__ import annotations

from django.db import transaction

from netbox_nsm.display_utils import (
    get_display_template_map,
    render_object_display,
    type_name_for_field_content_type,
)
from netbox_nsm.branch_db import (
    branch_aware_manager,
    branch_aware_related,
    junction_transaction,
)
from netbox_nsm.models import (
    ObjectGroup,
    Rule,
    Rulebook,
    RulebookField,
    RuleGroupItem,
    RuleObjectItem,
)
from netbox_nsm.models.rulebook import RulebookFieldKind
from netbox_nsm.rulebook_field_utils import get_visible_rulebook_fields


def parse_rules_column_key(column_key: str) -> tuple[str, str]:
    area_slug, type_key = column_key.split("::", 1)
    return area_slug, type_key


def rules_column_keys_for_rulebook(rulebook: Rulebook) -> list[str]:
    """Grid column keys (area::ct_N / area::Groups) for visible object fields."""
    groups_field_slugs: set[str] = set()
    for group in ObjectGroup.objects.only("field_slugs"):
        for slug in group.field_slugs or []:
            groups_field_slugs.add(str(slug))

    keys: list[str] = []
    for field in get_visible_rulebook_fields(rulebook):
        if field.field_kind != RulebookFieldKind.OBJECT:
            continue
        for ft in field.type_configs.select_related("type_config").all():
            if not ft.visible:
                continue
            tc = ft.type_config
            if tc and tc.content_type_id:
                keys.append(f"{field.slug}::ct_{tc.content_type_id}")
        if field.slug in groups_field_slugs:
            keys.append(f"{field.slug}::Groups")
    return keys


def _matching_class_map() -> dict[int, str]:
    from netbox_nsm.models import TypeConfig

    return {
        tc.content_type_id: tc.matching_class or ""
        for tc in TypeConfig.objects.only("content_type_id", "matching_class")
    }


def get_column_selections(rule: Rule, column_key: str) -> list[dict]:
    """Current picker selections for one grid column (field + type slice)."""
    area_slug, type_key = parse_rules_column_key(column_key)
    mc_map = _matching_class_map()
    selections: list[dict] = []

    if type_key == "Groups":
        for item in rule.group_items.filter(field__slug=area_slug).select_related(
            "field", "security_group"
        ):
            selections.append(
                {
                    "area": area_slug,
                    "placement": str(item.field.placement) if item.field else "",
                    "kind": "group",
                    "id": str(item.security_group.pk),
                    "name": str(item.security_group.name),
                    "typeName": "Groups",
                    "exclude": bool(item.exclude),
                }
            )
        return selections

    if not type_key.startswith("ct_"):
        return selections

    try:
        ct_id = int(type_key[3:])
    except (TypeError, ValueError):
        return selections

    field = (
        RulebookField.objects.filter(rulebook=rule.rulebook, slug=area_slug)
        .prefetch_related("type_configs__type_config__content_type")
        .first()
    )

    for item in rule.object_items.filter(
        field__slug=area_slug, content_type_id=ct_id
    ).select_related("field", "content_type"):
        assigned = item.assigned_object
        try:
            name = getattr(assigned, "name", None) or str(assigned)
        except Exception:
            name = None
        if not name:
            name = f"#{item.object_id}"
        selections.append(
            {
                "area": area_slug,
                "placement": str(item.field.placement) if item.field else "",
                "kind": "object",
                "id": f"{item.content_type_id}.{item.object_id}",
                "name": str(name),
                "typeName": type_name_for_field_content_type(
                    item.field or field, item.content_type_id
                ),
                "matchingClass": mc_map.get(item.content_type_id, ""),
                "color": getattr(assigned, "color", "") or "",
                "exclude": bool(item.exclude),
            }
        )
    return selections


def get_all_column_selections(rule: Rule, rulebook: Rulebook) -> dict[str, list[dict]]:
    return {
        key: get_column_selections(rule, key)
        for key in rules_column_keys_for_rulebook(rulebook)
    }


def save_column_selections(
    rule: Rule, column_key: str, selections: list[dict], request=None
) -> None:
    """Replace object/group items for one grid column."""
    with junction_transaction(rule, request):
        _write_column_selections(rule, column_key, selections, request)


def _write_column_selections(
    rule: Rule, column_key: str, selections: list[dict], request=None
) -> None:
    area_slug, type_key = parse_rules_column_key(column_key)
    field = (
        branch_aware_manager(RulebookField, rule, request)
        .filter(rulebook=rule.rulebook, slug=area_slug)
        .first()
    )
    if field is None:
        raise ValueError(f"Unknown field slug: {area_slug}")

    cleaned = [sel for sel in selections if isinstance(sel, dict)]

    if type_key == "Groups":
        branch_aware_related(rule.group_items, rule, request).filter(
            field=field
        ).delete()
        for sel in cleaned:
            if str(sel.get("kind", "")).strip() != "group":
                continue
            try:
                group_pk = int(sel.get("id"))
            except (TypeError, ValueError):
                continue
            if (
                not branch_aware_manager(ObjectGroup, rule, request)
                .filter(pk=group_pk)
                .exists()
            ):
                continue
            branch_aware_manager(RuleGroupItem, rule, request).get_or_create(
                rule_id=rule.pk,
                field_id=field.pk,
                security_group_id=group_pk,
                defaults={"exclude": bool(sel.get("exclude", False))},
            )
        return

    if not type_key.startswith("ct_"):
        raise ValueError(f"Unsupported column type: {type_key}")

    try:
        ct_id = int(type_key[3:])
    except (TypeError, ValueError):
        raise ValueError(f"Invalid content type in column: {column_key}")

    branch_aware_related(rule.object_items, rule, request).filter(
        field=field, content_type_id=ct_id
    ).delete()
    for sel in cleaned:
        if str(sel.get("kind", "")).strip() != "object":
            continue
        obj_id = str(sel.get("id", ""))
        parts = obj_id.split(".", 1)
        if len(parts) != 2:
            continue
        try:
            sel_ct_id, real_obj_id = int(parts[0]), int(parts[1])
        except (TypeError, ValueError):
            continue
        if sel_ct_id != ct_id:
            continue
        branch_aware_manager(RuleObjectItem, rule, request).get_or_create(
            rule_id=rule.pk,
            field_id=field.pk,
            content_type_id=sel_ct_id,
            object_id=real_obj_id,
            defaults={"exclude": bool(sel.get("exclude", False))},
        )


@transaction.atomic
def save_all_column_selections(
    rule: Rule, columns: dict[str, list], rulebook: Rulebook, request=None
) -> None:
    valid_keys = set(rules_column_keys_for_rulebook(rulebook))
    for key, selections in columns.items():
        if key not in valid_keys or not isinstance(selections, list):
            continue
        save_column_selections(rule, key, selections, request=request)


def build_column_cell_payload(rule: Rule, rulebook: Rulebook, column_key: str) -> dict:
    """Render rules table cell HTML + filter text for one column after save."""
    from netbox_nsm.rulebook_rules_cell_html import render_rules_cell_ag as _render_rules_cell_ag

    area_slug, type_key = parse_rules_column_key(column_key)
    field = RulebookField.objects.filter(rulebook=rulebook, slug=area_slug).first()
    if field is None:
        return {
            "html": '<span class="nsm-cell-empty">-</span>',
            "filter": "",
            "column_key": column_key,
        }
    ct_display_template_map = get_display_template_map()
    items: list[dict] = []

    if type_key == "Groups":
        for item in rule.group_items.filter(field=field).select_related(
            "security_group"
        ):
            items.append(
                {
                    "url": item.security_group.get_absolute_url(),
                    "name": item.security_group.name,
                    "color": "",
                    "excluded": bool(item.exclude),
                }
            )
    elif type_key.startswith("ct_"):
        try:
            ct_id = int(type_key[3:])
        except (TypeError, ValueError):
            ct_id = None
        if ct_id is not None:
            from netbox_nsm.models import TypeConfig as _TC
            from netbox_nsm.views.rulebook import _object_is_addr_analyzable

            matching_class_map = {
                tc.content_type_id: tc.matching_class
                for tc in _TC.objects.only("content_type_id", "matching_class")
            }
            for item in rule.object_items.filter(
                field=field, content_type_id=ct_id
            ).select_related("content_type"):
                assigned = item.assigned_object
                if assigned is None:
                    continue
                try:
                    display_name = render_object_display(
                        assigned, item.content_type_id, ct_display_template_map
                    )
                except Exception:
                    display_name = getattr(assigned, "name", None) or str(assigned)
                items.append(
                    {
                        "url": (
                            assigned.get_absolute_url()
                            if hasattr(assigned, "get_absolute_url")
                            else "#"
                        ),
                        "name": str(display_name),
                        "color": getattr(assigned, "color", "") or "",
                        "excluded": bool(item.exclude),
                        "ct": item.content_type_id,
                        "pk": item.object_id,
                        "addrAnalyzable": _object_is_addr_analyzable(
                            assigned, item.content_type_id, matching_class_map
                        ),
                    }
                )

    max_pills = field.max_visible_pills if field is not None else None
    use_colored = field.show_colored_pills if field is not None else True
    html = _render_rules_cell_ag(items, max_pills=max_pills, colored=use_colored)
    filter_text = " ".join(item["name"] for item in items)
    return {"html": html, "filter": filter_text, "column_key": column_key}


def build_all_column_cells_payload(rule: Rule, rulebook: Rulebook) -> dict[str, dict]:
    return {
        key: build_column_cell_payload(rule, rulebook, key)
        for key in rules_column_keys_for_rulebook(rulebook)
    }
