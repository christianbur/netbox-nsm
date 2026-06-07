from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.html import escape, conditional_escape
from django.db.models import Count, Max, Q
from django.views import View
from netbox.object_actions import AddObject, BulkDelete
import json

import markdown
import django_tables2 as tables

from utilities.views import ViewTab, register_model_view
from netbox.views import generic

from netbox_nsm.filtersets import (
    RuleFilterSet,
    RulebookAssignmentFilterSet,
    RulebookFilterSet,
)
from netbox_nsm.forms import (
    RulebookAssignmentFilterForm,
    RulebookAssignmentForm,
    RulebookBulkAssignForm,
    RulebookBulkEditForm,
    RulebookFilterForm,
    RulebookForm,
    RuleFilterForm,
    RuleForm,
    RuleBulkEditForm,
)
from netbox_nsm.models import (
    ObjectGroup,
    RuleObjectItem,
    RuleGroupItem,
    RulebookFieldKind,
    RulebookTypeChoices,
    Rule,
    Rulebook,
    RulebookAssignment,
    RulebookField,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.models.type_config import MatchingClassChoices
from netbox_nsm.api_urls import (
    get_api_url_for_content_type as _get_api_url_for_content_type,
)
from netbox_nsm.rulebook_field_utils import (
    ensure_system_rulebook_fields,
    get_rules_column_labels,
    get_rules_column_slugs,
    get_visible_rulebook_fields,
    get_visible_virtual_all_rules_fields,
    load_rulebook_fields_for_detail,
)
from netbox_nsm.rulebook_rules_cell_html import ipa_loupe_button_html
from netbox_nsm.virtual_rulebook import is_virtual_all_rules_rulebook
from netbox_nsm.tables import (
    RulebookAssignmentTable,
    RulebookTable,
    RuleTable,
)


def _rules_placement_for_area(area_slug):
    if area_slug == "source":
        return "source"
    if area_slug == "destination":
        return "destination"
    return "fixed"


def _render_vgroup_cell(items):
    """Render items as a single AND-group bubble: ⟨item1 | item2 | item3⟩."""
    if not items:
        return '<span class="text-muted small">-</span>'
    sorted_items = sorted(items, key=lambda x: x["name"].lower())
    parts = []
    for item in sorted_items:
        parts.append(
            f'<a href="{conditional_escape(item["url"])}" '
            f'class="nsm-vgroup-item" '
            f'title="{conditional_escape(item["name"])}" >'
            f'{conditional_escape(item["name"])}</a>'
        )
    inner = '<span class="nsm-vgroup-sep">|</span>'.join(parts)
    return f'<div class="nsm-vgroup-bubble">{inner}</div>'


DEFAULT_MAX_VISIBLE_PILLS = 5


def _rules_pill_html(item, *, hidden=False, colored=True):
    color = (item.get("color") or "").strip() if colored else ""
    style_parts = []
    if color:
        try:
            hex_val = color.lstrip("#")
            r = int(hex_val[0:2], 16)
            g = int(hex_val[2:4], 16)
            b = int(hex_val[4:6], 16)
            luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            text_color = "#111111" if luminance > 0.6 else "#ffffff"
        except (ValueError, IndexError):
            text_color = "#ffffff"
        style_parts.extend(
            [
                f"background-color: {conditional_escape(color)};",
                f"border-color: {conditional_escape(color)};",
                f"color: {text_color};",
            ]
        )
    if hidden:
        style_parts.append("display:none;")
    style_attr = f' style="{"".join(style_parts)}"' if style_parts else ""
    hidden_class = " nsm-pill-hidden" if hidden else ""
    colored_class = " nsm-rule-pill-colored" if color else ""
    excluded_class = " nsm-pill-excluded" if item.get("excluded") else ""
    return (
        f'<a href="{conditional_escape(item["url"])}" '
        f' class="nsm-rule-pill{colored_class}{hidden_class} text-decoration-none{excluded_class}"'
        f"{style_attr}"
        f' title="{conditional_escape(item["name"])}">'
        f'{conditional_escape(item["name"])}'
        f"</a>"
    )


def _render_rules_cell(items, max_pills=None, *, colored=True):
    if not items:
        return '<span class="text-muted small">-</span>'
    try:
        limit = max(
            1, int(max_pills if max_pills is not None else DEFAULT_MAX_VISIBLE_PILLS)
        )
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_VISIBLE_PILLS
    shown = items[:limit]
    hidden = items[limit:]
    parts = [_rules_pill_html(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(_rules_pill_html(item, hidden=True, colored=colored))
    if hidden:
        parts.append(
            '<button type="button"'
            ' class="nsm-rule-pill nsm-rule-pill-muted nsm-pill-more"'
            ' style="border:none;cursor:pointer;flex-shrink:0;max-width:none;overflow:visible;"'
            " onclick=\"var c=this.closest('.nsm-rule-pills');"
            "c.querySelectorAll('.nsm-pill-hidden').forEach(function(e){e.style.display='';});"
            'this.remove();"'
            f">+{len(hidden)}</button>"
        )
    return f'<div class="nsm-rule-pills">{"".join(parts)}</div>'


def _virtual_all_rules_union_key(field_name: str, type_label: str) -> str:
    return f"{field_name}::{type_label}"


def _build_virtual_all_rules_rb_maps(
    *,
    ct_label_map: dict,
    groups_field_slugs: set[str],
    union_field_names: dict[str, str],
) -> dict[int, dict[str, str]]:
    """Map union column keys (Area::TypeLabel) to per-rulebook local keys (slug::ct_N)."""
    rb_maps: dict[int, dict[str, str]] = {}
    for rulebook in Rulebook.objects.filter(
        rulebook_type=RulebookTypeChoices.SECURITY_RULES
    ).order_by("pk"):
        rb_map: dict[str, str] = {}
        for field in get_visible_rulebook_fields(rulebook):
            if field.field_kind != RulebookFieldKind.OBJECT:
                continue
            union_name = union_field_names.get(field.slug, field.name)
            ct_ids = [
                ft.type_config.content_type_id
                for ft in field.type_configs.all()
                if ft.visible and ft.type_config and ft.type_config.content_type_id
            ]
            for ct_id in ct_ids:
                type_label = ct_label_map.get(ct_id, f"Type {ct_id}")
                union_key = _virtual_all_rules_union_key(union_name, type_label)
                rb_map[union_key] = f"{field.slug}::ct_{ct_id}"
            if field.slug in groups_field_slugs:
                groups_label = str(_("Groups"))
                union_key = _virtual_all_rules_union_key(union_name, groups_label)
                rb_map[union_key] = f"{field.slug}::Groups"
        rb_maps[rulebook.pk] = rb_map
    return rb_maps


def _build_virtual_all_rules_grouped_table_data(rules):
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    rules = list(rules)
    ct_display_template_map = get_display_template_map()
    visible_fields = get_visible_virtual_all_rules_fields()
    union_field_names = {field.slug: field.name for field in visible_fields}

    ct_label_map = {}
    for tc in TypeConfig.objects.select_related("content_type"):
        mc = tc.content_type.model_class()
        if mc:
            vc = getattr(mc._meta, "verbose_name", tc.content_type.model)
            ct_label_map[tc.content_type.pk] = str(vc).capitalize()

    fields_by_slug = {}
    field_ct_ids_map = {}
    for field in visible_fields:
        if field.field_kind != RulebookFieldKind.OBJECT:
            continue
        fields_by_slug[field.slug] = field
        field_ct_ids_map[field.slug] = [
            ft.type_config.content_type_id
            for ft in field.type_configs.all()
            if ft.visible and ft.type_config and ft.type_config.content_type_id
        ]

    groups_field_slugs = set()
    for group in ObjectGroup.objects.only("field_slugs"):
        for slug in group.field_slugs or []:
            groups_field_slugs.add(str(slug))

    rules_layout = [
        {
            "kind": "system",
            "slug": "rulebook",
            "label": str(_("Rulebook")),
        }
    ]
    header_groups = []
    grouped_columns = []
    group_idx = 0

    for field in visible_fields:
        if field.field_kind == RulebookFieldKind.SYSTEM:
            rules_layout.append(
                {"kind": "system", "slug": field.slug, "label": field.name}
            )
            continue

        field_slug = field.slug
        ct_ids = field_ct_ids_map.get(field_slug, [])
        types = [
            (f"ct_{ct_id}", ct_label_map.get(ct_id, f"Type {ct_id}"))
            for ct_id in ct_ids
        ]
        if field_slug in groups_field_slugs:
            types.append(("Groups", str(_("Groups"))))
        if not types:
            continue

        cols = []
        for type_key, type_label in types:
            key = _virtual_all_rules_union_key(field.name, type_label)
            col_def = {
                "key": key,
                "label": type_label,
                "area_slug": field_slug,
                "type_name": type_key,
            }
            cols.append(col_def)
            grouped_columns.append(col_def)

        group = {"label": field.name, "slug": field_slug, "columns": cols}
        for idx, col in enumerate(cols):
            col["is_group_start"] = idx == 0
            col["is_group_end"] = idx == len(cols) - 1
            col["group_band"] = "odd" if (group_idx % 2) else "even"
        header_groups.append(group)
        rules_layout.append(
            {
                "kind": "object",
                "slug": field_slug,
                "label": field.name,
                "group": group,
            }
        )
        group_idx += 1

    col_index = 1
    for entry in rules_layout:
        if entry["kind"] == "system":
            entry["col_index"] = col_index
            col_index += 1
        else:
            for col in entry["group"]["columns"]:
                col["col_index"] = col_index
                col_index += 1

    matching_class_map = {
        tc.content_type_id: tc.matching_class
        for tc in TypeConfig.objects.only("content_type_id", "matching_class")
    }

    rb_maps = _build_virtual_all_rules_rb_maps(
        ct_label_map=ct_label_map,
        groups_field_slugs=groups_field_slugs,
        union_field_names=union_field_names,
    )

    col_area_slug = {col["key"]: col["area_slug"] for col in grouped_columns}
    rows = []
    for rule in rules:
        per_key = {col["key"]: [] for col in grouped_columns}
        rb_map = rb_maps.get(rule.rulebook_id, {})
        local_to_union = {local: union for union, local in rb_map.items()}

        for item in rule.object_items.all():
            if item.field is None:
                continue
            local_key = f"{item.field.slug}::ct_{item.content_type_id}"
            key = local_to_union.get(local_key)
            if not key or key not in per_key:
                continue
            assigned = item.assigned_object
            if assigned is None:
                continue
            display_name = render_object_display(
                assigned, item.content_type_id, ct_display_template_map
            )
            per_key[key].append(
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

        for item in rule.group_items.all():
            if item.field is None:
                continue
            local_key = f"{item.field.slug}::Groups"
            key = local_to_union.get(local_key)
            if not key or key not in per_key:
                continue
            per_key[key].append(
                {
                    "url": item.security_group.get_absolute_url(),
                    "name": item.security_group.name,
                    "color": "",
                }
            )

        cells = {}
        cells_items = {}
        cells_filter = {}
        for k, v in per_key.items():
            area_slug = col_area_slug.get(k, k.split("::", 1)[0])
            field = fields_by_slug.get(area_slug)
            max_pills = (
                field.max_visible_pills
                if field is not None
                else DEFAULT_MAX_VISIBLE_PILLS
            )
            use_colored = field.show_colored_pills if field is not None else True
            cells_items[k] = v
            cells[k] = _render_rules_cell(v, max_pills=max_pills, colored=use_colored)
            cells_filter[k] = " ".join(item["name"] for item in v)

        rows.append(
            {
                "pk": rule.pk,
                "index": rule.index,
                "enabled": rule.enabled,
                "name": rule.name,
                "url": rule.get_absolute_url(),
                "description": rule.description or "-",
                "edit_url": f"/plugins/netbox-nsm/rules/{rule.pk}/edit/",
                "delete_url": f"/plugins/netbox-nsm/rules/{rule.pk}/delete/",
                "system": {
                    "index": rule.index,
                    "enabled": rule.enabled,
                    "name": rule.name,
                    "url": rule.get_absolute_url(),
                    "description": rule.description or "-",
                    "rulebook": rule.rulebook.name,
                    "rulebook_url": rule.rulebook.get_absolute_url(),
                },
                "cells": cells,
                "cells_items": cells_items,
                "cells_filter": cells_filter,
            }
        )

    return {
        "rules_layout": rules_layout,
        "header_groups": header_groups,
        "column_count": len(grouped_columns),
        "total_column_count": col_index + 1,
        "rows": rows,
        "rb_maps": rb_maps,
    }


def _build_grouped_rules_table_data(rules, rulebook):
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    if is_virtual_all_rules_rulebook(rulebook):
        return _build_virtual_all_rules_grouped_table_data(rules)

    rules = list(rules)
    ct_display_template_map = get_display_template_map()
    visible_fields = get_visible_rulebook_fields(rulebook)

    ct_label_map = {}
    for tc in TypeConfig.objects.select_related("content_type"):
        mc = tc.content_type.model_class()
        if mc:
            vc = getattr(mc._meta, "verbose_name", tc.content_type.model)
            ct_label_map[tc.content_type.pk] = str(vc).capitalize()

    fields_by_slug = {}
    field_ct_ids_map = {}
    for field in visible_fields:
        if field.field_kind != RulebookFieldKind.OBJECT:
            continue
        fields_by_slug[field.slug] = field
        field_ct_ids_map[field.slug] = [
            ft.type_config.content_type_id
            for ft in field.type_configs.all()
            if ft.visible and ft.type_config and ft.type_config.content_type_id
        ]

    groups_field_slugs = set()
    for group in ObjectGroup.objects.only("field_slugs"):
        for slug in group.field_slugs or []:
            groups_field_slugs.add(str(slug))

    rules_layout = []
    header_groups = []
    grouped_columns = []
    group_idx = 0

    for field in visible_fields:
        if field.field_kind == RulebookFieldKind.SYSTEM:
            rules_layout.append(
                {"kind": "system", "slug": field.slug, "label": field.name}
            )
            continue

        field_slug = field.slug
        ct_ids = field_ct_ids_map.get(field_slug, [])
        types = [
            (f"ct_{ct_id}", ct_label_map.get(ct_id, f"Type {ct_id}"))
            for ct_id in ct_ids
        ]
        if field_slug in groups_field_slugs:
            types.append(("Groups", str(_("Groups"))))
        if not types:
            continue

        cols = []
        for type_key, type_label in types:
            key = f"{field_slug}::{type_key}"
            col_def = {
                "key": key,
                "label": type_label,
                "area_slug": field_slug,
                "type_name": type_key,
            }
            cols.append(col_def)
            grouped_columns.append(col_def)

        group = {"label": field.name, "slug": field_slug, "columns": cols}
        for idx, col in enumerate(cols):
            col["is_group_start"] = idx == 0
            col["is_group_end"] = idx == len(cols) - 1
            col["group_band"] = "odd" if (group_idx % 2) else "even"
        header_groups.append(group)
        rules_layout.append(
            {
                "kind": "object",
                "slug": field_slug,
                "label": field.name,
                "group": group,
            }
        )
        group_idx += 1

    col_index = 1
    for entry in rules_layout:
        if entry["kind"] == "system":
            entry["col_index"] = col_index
            col_index += 1
        else:
            for col in entry["group"]["columns"]:
                col["col_index"] = col_index
                col_index += 1

    matching_class_map = {
        tc.content_type_id: tc.matching_class
        for tc in TypeConfig.objects.only("content_type_id", "matching_class")
    }

    rows = []
    for rule in rules:
        per_key = {col["key"]: [] for col in grouped_columns}

        for item in rule.object_items.all():
            if item.field is None:
                continue
            key = f"{item.field.slug}::ct_{item.content_type_id}"
            if key not in per_key:
                continue
            assigned = item.assigned_object
            if assigned is None:
                continue
            display_name = render_object_display(
                assigned, item.content_type_id, ct_display_template_map
            )
            per_key[key].append(
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

        for item in rule.group_items.all():
            if item.field is None:
                continue
            key = f"{item.field.slug}::Groups"
            if key not in per_key:
                continue
            per_key[key].append(
                {
                    "url": item.security_group.get_absolute_url(),
                    "name": item.security_group.name,
                    "color": "",
                }
            )

        cells = {}
        cells_items = {}
        cells_filter = {}
        for k, v in per_key.items():
            area_slug = k.split("::", 1)[0]
            field = fields_by_slug.get(area_slug)
            max_pills = (
                field.max_visible_pills
                if field is not None
                else DEFAULT_MAX_VISIBLE_PILLS
            )
            use_colored = field.show_colored_pills if field is not None else True
            cells_items[k] = v
            cells[k] = _render_rules_cell(v, max_pills=max_pills, colored=use_colored)
            cells_filter[k] = " ".join(item["name"] for item in v)

        rows.append(
            {
                "pk": rule.pk,
                "index": rule.index,
                "enabled": rule.enabled,
                "name": rule.name,
                "url": rule.get_absolute_url(),
                "description": rule.description or "-",
                "edit_url": f"/plugins/netbox-nsm/rules/{rule.pk}/edit/",
                "delete_url": f"/plugins/netbox-nsm/rules/{rule.pk}/delete/",
                "system": {
                    "index": rule.index,
                    "enabled": rule.enabled,
                    "name": rule.name,
                    "url": rule.get_absolute_url(),
                    "description": rule.description or "-",
                },
                "cells": cells,
                "cells_items": cells_items,
                "cells_filter": cells_filter,
            }
        )

    return {
        "rules_layout": rules_layout,
        "header_groups": header_groups,
        "column_count": len(grouped_columns),
        "total_column_count": col_index + 1,
        "rows": rows,
    }


SECURITY_RULES_COLUMNS = (
    ("index", _("Index")),
    ("status", _("Status")),
    ("name", _("Name")),
    ("source", _("Source")),
    ("destination", _("Destination")),
    ("service", _("Service")),
    ("action", _("Action")),
    ("info", _("Info")),
    ("description", _("Description")),
)

RULES_TABLE_COLUMN_NAMES = frozenset(name for name, _ in SECURITY_RULES_COLUMNS)

MAX_CUSTOM_COLUMNS = 10


def _build_security_rule_picker_data(rulebook=None):
    """
    Build minimal picker metadata for the rule editor.
    Uses RulebookField/RulebookFieldType/TypeConfig instead of the legacy SecurityArea model.
    """
    fields = {}

    if rulebook:
        ensure_system_rulebook_fields(rulebook)
    fields_qs = (
        RulebookField.objects.filter(
            rulebook=rulebook,
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
        )
        if rulebook
        else RulebookField.objects.none()
    ).order_by("sort_order", "slug")

    for field in fields_qs:
        fields[field.slug] = {
            "slug": str(field.slug),
            "name": str(field.name),
            "display_name": str(field.name),
            "placement": str(field.placement),
            "sort_order": int(field.sort_order),
            "show_colored_pills": bool(field.show_colored_pills),
            "types": [],
        }

    if rulebook:
        for ftype in (
            RulebookFieldType.objects.filter(field__rulebook=rulebook)
            .select_related("field", "type_config__content_type")
            .order_by("sort_order", "type_config__content_type__model")
        ):
            field_data = fields.get(ftype.field.slug)
            if not field_data or not ftype.visible:
                continue
            tc = ftype.type_config
            if not tc or not tc.content_type_id:
                continue
            model_class = tc.content_type.model_class()
            api_url = _get_api_url_for_content_type(tc.content_type) or ""
            label = (tc.name or "").strip()
            if not label and model_class:
                label = str(model_class._meta.verbose_name_plural).title()
            if not label:
                label = tc.content_type.model
            field_data["types"].append(
                {
                    "name": label,
                    "ct_id": tc.content_type.pk,
                    "api_url": api_url,
                    "kind": "object",
                    "allow_virtual_groups": True,
                    "matching_class": tc.matching_class or "",
                    "name_filter_regex": (ftype.name_filter_regex or "").strip(),
                }
            )

    groups_by_slug = {}
    for group in ObjectGroup.objects.order_by("name"):
        for slug in group.field_slugs or []:
            groups_by_slug.setdefault(str(slug), []).append(
                {"id": str(group.pk), "name": str(group.name)}
            )
    for field_slug, group_entries in groups_by_slug.items():
        field_data = fields.get(field_slug)
        if field_data:
            field_data["types"].append(
                {
                    "name": "Groups",
                    "kind": "group",
                    "entries": group_entries,
                }
            )

    ordered_areas = [
        {
            "slug": d["slug"],
            "name": d["name"],
            "display_name": d["display_name"],
            "placement": d["placement"],
            "sort_order": d["sort_order"],
            "show_colored_pills": d.get("show_colored_pills", True),
            "types": d["types"],
        }
        for _, d in sorted(
            fields.items(),
            key=lambda pair: (pair[1]["sort_order"], pair[1]["name"].lower(), pair[0]),
        )
    ]
    return {"areas": ordered_areas}


def _available_rules_columns(rulebook=None):
    slugs = ("source", "destination", "service", "action", "info")
    if rulebook is None:
        return {
            slug: RulebookField.objects.filter(slug=slug).exists() for slug in slugs
        }
    ensure_system_rulebook_fields(rulebook)
    visible_object_slugs = set(
        RulebookField.objects.filter(
            rulebook=rulebook,
            field_kind=RulebookFieldKind.OBJECT,
            visible=True,
        ).values_list("slug", flat=True)
    )
    return {slug: slug in visible_object_slugs for slug in slugs}


def _build_rule_edit_rule_slots(rulebook=None):
    """Visible src/dst/service/action/info columns for the rule editor grid."""
    if rulebook is None:
        return []
    availability = _available_rules_columns(rulebook)
    labels = get_rules_column_labels(rulebook)
    slots = []
    for slug in ("source", "destination", "service", "action", "info"):
        if not availability.get(slug):
            continue
        slots.append(
            {
                "slug": slug,
                "label": str(labels.get(slug) or slug.replace("_", " ").title()),
                "kind": "object",
            }
        )
    return slots


def _filter_rules_columns(columns, availability):
    filtered = []
    for column in columns:
        if column in availability and not availability.get(column, False):
            continue
        filtered.append(column)
    return filtered


def _rules_columns_session_key(rulebook_pk):
    return f"netbox_nsm_rules_columns_{rulebook_pk}"


def _default_security_rules_columns():
    return [
        column
        for column in RuleTable.Meta.default_columns
        if column in RULES_TABLE_COLUMN_NAMES
    ]


def _normalize_rules_table_columns(columns, availability=None):
    """Keep only columns that exist on RuleTable (ignore rulebook-only slugs)."""
    normalized = []
    for column in columns:
        if column not in RULES_TABLE_COLUMN_NAMES:
            continue
        if availability is not None and not availability.get(column, True):
            continue
        normalized.append(column)
    if normalized:
        return normalized
    defaults = _default_security_rules_columns()
    if availability is None:
        return defaults
    return [col for col in defaults if availability.get(col, True)] or defaults


def _sanitize_custom_columns(custom_columns):
    sanitized = []
    for column in custom_columns[:MAX_CUSTOM_COLUMNS]:
        title = str(column.get("title", "")).strip()
        body = str(column.get("body", "")).strip()
        if not title or not body:
            continue
        sanitized.append(
            {
                "title": title[:80],
                "body": body[:4000],
            }
        )
    return sanitized


def _get_rules_table_config(request, rulebook):
    ensure_system_rulebook_fields(rulebook)
    availability = _available_rules_columns(rulebook)
    selected_columns = _normalize_rules_table_columns(
        get_rules_column_slugs(rulebook),
        availability,
    )
    key = _rules_columns_session_key(rulebook.pk)
    config = request.session.get(key, {})
    custom_columns = _sanitize_custom_columns(config.get("custom_columns") or [])
    return {
        "selected_columns": selected_columns,
        "custom_columns": custom_columns,
    }


def _selected_security_rules_columns(request):
    allowed_columns = {name for name, _ in SECURITY_RULES_COLUMNS}
    requested = request.GET.getlist("columns")
    if not requested:
        raw = request.GET.get("columns")
        if raw:
            requested = [col.strip() for col in raw.split(",") if col.strip()]

    selected = [col for col in requested if col in allowed_columns]
    if selected:
        return selected

    return [
        column for column in RuleTable.Meta.default_columns if column in allowed_columns
    ]


def _render_custom_markdown(content):
    return markdown.markdown(
        escape(content),
        extensions=["extra", "nl2br"],
    )


def _build_rules_table_class(custom_columns, selected_columns):
    attrs = {}
    custom_keys = []
    for index, custom_column in enumerate(custom_columns, start=1):
        key = f"custom_column_{index}"
        custom_keys.append(key)
        attrs[key] = tables.TemplateColumn(
            template_code=_render_custom_markdown(custom_column["body"]),
            verbose_name=custom_column["title"],
            orderable=False,
        )
    attrs["Meta"] = type(
        "Meta",
        (RuleTable.Meta,),
        {
            "model": Rule,
            "fields": tuple(RuleTable.Meta.fields) + tuple(custom_keys),
            "default_columns": tuple(selected_columns) + tuple(custom_keys),
        },
    )
    return type("ConfiguredRuleTable", (RuleTable,), attrs)


__all__ = (
    "RulebookView",
    "RulebookListView",
    "RulebookEditView",
    "RulebookDeleteView",
    "RulebookBulkEditView",
    "RulebookBulkDeleteView",
    "RulebookRulesColumnsView",
    "RulebookRulesView",
    "RulebookBulkAssignView",
    "RuleView",
    "RuleListView",
    "RuleEditView",
    "RuleDeleteView",
    "RuleBulkEditView",
    "RuleBulkDeleteView",
    "RulebookAssignmentListView",
    "RulebookAssignmentEditView",
    "RulebookAssignmentDeleteView",
    "RulebookAssignmentBulkDeleteView",
    "GlobalRulesSearchView",
)


ZONE_TYPE_NAME = "Zones"
_NONE_ZONE_PK = 0


def _make_none_zone():
    from types import SimpleNamespace

    return SimpleNamespace(pk=_NONE_ZONE_PK, name="(none)")


def _load_rules_qs(instance):
    """Shared helper: load all rules with needed prefetches."""
    return list(
        Rule.objects.filter(rulebook=instance)
        .prefetch_related(
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
        )
        .order_by("index")
    )


def _rulebook_field_for_ct(instance, placement, ct_id):
    """Return the rulebook field for placement that accepts the given content type."""
    fields = (
        RulebookField.objects.filter(rulebook=instance, placement=placement)
        .prefetch_related("type_configs__type_config")
        .order_by("sort_order", "pk")
    )
    for field in fields:
        for ft in field.type_configs.all():
            if ft.type_config.content_type_id == ct_id:
                return field
    return fields.first()


def _matrix_rules_href(
    base_url,
    src_field_name,
    dst_field_name,
    src_obj,
    dst_obj,
    *,
    bidirectional=False,
    zone_content_type_id=None,
    type_segment=None,
    display_template_map=None,
    src_field_slug=None,
    dst_field_slug=None,
):
    from urllib.parse import quote

    from netbox_nsm.display_utils import get_display_template_map, render_object_display
    from netbox_nsm.object_rules_utils import build_matrix_cell_rules_filter_url
    from netbox_nsm.query.parser import Condition, conditions_to_query_param

    tmpl_map = (
        display_template_map
        if display_template_map is not None
        else get_display_template_map()
    )

    if zone_content_type_id:
        src_name = render_object_display(src_obj, zone_content_type_id, tmpl_map)
        dst_name = render_object_display(dst_obj, zone_content_type_id, tmpl_map)
    else:
        src_name = getattr(src_obj, "name", str(src_obj))
        dst_name = getattr(dst_obj, "name", str(dst_obj))

    src_slug = (src_field_slug or "source").strip()
    dst_slug = (dst_field_slug or "destination").strip()
    if zone_content_type_id:
        column_href = build_matrix_cell_rules_filter_url(
            base_url,
            src_column_key=f"{src_slug}::ct_{zone_content_type_id}",
            dst_column_key=f"{dst_slug}::ct_{zone_content_type_id}",
            src_filter=src_name,
            dst_filter=dst_name,
        )
        if column_href:
            return column_href

    def _zone_condition(field_name, obj_name):
        if type_segment:
            return Condition(
                field=field_name,
                type_segment=type_segment,
                sub_field="name",
                operator="=",
                value=obj_name,
            )
        return Condition(
            field=field_name,
            sub_field="Name",
            operator="=",
            value=obj_name,
        )

    def _pair_query(s_name, d_name):
        return conditions_to_query_param(
            [
                _zone_condition(src_field_name, s_name),
                _zone_condition(dst_field_name, d_name),
            ]
        )

    if bidirectional and src_name.lower() != dst_name.lower():
        q = f"{_pair_query(src_name, dst_name)} OR {_pair_query(dst_name, src_name)}"
    else:
        q = _pair_query(src_name, dst_name)
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}filter_q={quote(q, safe='')}"


def _rulebook_matrix_tab_visible(instance) -> bool:
    if is_virtual_all_rules_rulebook(instance):
        return False
    return bool(getattr(instance, "matrix_tab_enabled", True))


@register_model_view(Rulebook, name="matrix", path="matrix")
class RulebookMatrixView(generic.ObjectView):
    """Classic HTML zone matrix (source × destination heatmap)."""

    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/rulebook_matrix.html"
    tab = ViewTab(
        label=_("Matrix"),
        permission="netbox_nsm.view_rulebook",
        weight=300,
        hide_if_empty=True,
        visible=_rulebook_matrix_tab_visible,
    )

    def get(self, request, **kwargs):
        instance = self.get_object(**kwargs)
        if not _rulebook_matrix_tab_visible(instance):
            raise Http404
        return super().get(request, **kwargs)

    def get_extra_context(self, request, instance):
        from netbox_nsm.matrix_tab_context import build_matrix_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        ctx = build_matrix_tab_context(
            request,
            instance,
            view_helpers=rulebook_views,
        )
        ctx["matrix_tab_label"] = self.tab.label
        return ctx


def _build_ip_analysis_groups(rules_qs):
    """Collect all unique src/dst objects across all types, grouped by type label."""
    from django.apps import apps as django_apps

    _ip_all_objs: dict = {}
    for rule in rules_qs:
        for item in rule.object_items.all():
            if not item.field or item.field.placement not in ("source", "destination"):
                continue
            obj = item.assigned_object
            if obj is None:
                continue
            key = (item.content_type_id, obj.pk)
            if key not in _ip_all_objs:
                ct = item.content_type
                try:
                    mc = ct.model_class() if ct else None
                    if mc:
                        type_label = str(
                            getattr(mc._meta, "verbose_name", ct.model)
                        ).capitalize()
                        try:
                            app_cfg = django_apps.get_app_config(ct.app_label)
                            type_label = f"{app_cfg.verbose_name} \u203a {type_label}"
                        except LookupError:
                            pass
                    else:
                        type_label = ct.model if ct else "object"
                except Exception:
                    type_label = ct.model if ct else "object"
                _ip_all_objs[key] = {
                    "ct_id": item.content_type_id,
                    "pk": obj.pk,
                    "name": getattr(obj, "name", str(obj)),
                    "type_label": type_label,
                    "obj": obj,
                }
    _by_type: dict = {}
    for entry in sorted(
        _ip_all_objs.values(), key=lambda x: (x["type_label"], x["name"])
    ):
        _by_type.setdefault(entry["type_label"], []).append(entry)
    groups = [
        {"type_label": tl, "objects": objs} for tl, objs in sorted(_by_type.items())
    ]
    return groups, _ip_all_objs


@register_model_view(Rulebook)
class RulebookView(generic.ObjectView):
    queryset = Rulebook.objects.prefetch_related(
        "assignments__assigned_object_type",
    ).select_related("platform")

    def get_extra_context(self, request, instance):
        # Assigned objects
        assignments = list(
            instance.assignments.select_related("assigned_object_type").all()
        )

        # Fields + Matching Strategy (always available)
        rulebook_fields = load_rulebook_fields_for_detail(instance)
        rulebook_fields_system = [f for f in rulebook_fields if f.is_system_field]
        rulebook_fields_object = [f for f in rulebook_fields if not f.is_system_field]
        matching_classes = sorted(instance.matching_classes)
        has_object_rulebook_fields = bool(rulebook_fields_object)

        if instance.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
            return {
                "assignments": assignments,
                "rulebook_fields": rulebook_fields,
                "rulebook_fields_system": rulebook_fields_system,
                "rulebook_fields_object": rulebook_fields_object,
                "has_object_rulebook_fields": has_object_rulebook_fields,
                "matching_classes": matching_classes,
            }

        availability = _available_rules_columns(instance)
        config = _get_rules_table_config(request, instance)
        selected_columns = config["selected_columns"]
        selected_set = set(selected_columns)
        order_map = {name: idx + 1 for idx, name in enumerate(selected_columns)}

        return {
            "assignments": assignments,
            "security_rules_columns": SECURITY_RULES_COLUMNS,
            "selected_security_rules_columns": selected_columns,
            "selected_security_rules_columns_set": selected_set,
            "security_rules_column_order": order_map,
            "security_rules_column_order_list": selected_columns,
            "custom_columns": config["custom_columns"],
            "nsm_available_rules_areas": availability,
            "rulebook_fields": rulebook_fields,
            "rulebook_fields_system": rulebook_fields_system,
            "rulebook_fields_object": rulebook_fields_object,
            "has_object_rulebook_fields": has_object_rulebook_fields,
            "matching_classes": matching_classes,
        }


@register_model_view(Rulebook, name="rules_columns", path="rules-columns")
class RulebookRulesColumnsView(generic.ObjectView):
    queryset = Rulebook.objects.all()

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        if instance.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
            return redirect(reverse("plugins:netbox_nsm:rulebook", args=[instance.pk]))

        custom_columns = []
        titles = request.POST.getlist("custom_column_title")
        bodies = request.POST.getlist("custom_column_body")
        for title, body in zip(titles, bodies):
            custom_columns.append({"title": title, "body": body})

        request.session[_rules_columns_session_key(instance.pk)] = {
            "custom_columns": _sanitize_custom_columns(custom_columns),
        }
        request.session.modified = True

        return redirect(
            reverse("plugins:netbox_nsm:rulebook_rules", args=[instance.pk])
        )


class _RulebookRulesTabMixin:
    """Bulk-delete and HTML rules table."""

    queryset = Rulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/rulebook_rules.html"
    rules_tab_route = "rulebook_rules"
    rules_tab_key = "rules"

    def post(self, request, *args, **kwargs):
        """Handle bulk-delete of rules from the rules table."""
        instance = self.get_object(**kwargs)
        if not request.user.has_perm("netbox_nsm.delete_rule"):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden()
        pk_list = [int(pk) for pk in request.POST.getlist("pk") if pk.isdigit()]
        if pk_list:
            from netbox_nsm.branch_db import ensure_branch_context
            from netbox_nsm.changelog_utils import record_rulebook_rules_changelog
            from netbox_nsm.rulebook_rules_utils import snapshot_rules_layout_entries

            with ensure_branch_context(request):
                rules_qs = Rule.objects.filter(pk__in=pk_list, rulebook=instance)
                rb_prechange = snapshot_rules_layout_entries(rules_qs)
                rules_qs.delete()
                record_rulebook_rules_changelog(
                    instance,
                    request,
                    rb_prechange,
                    postchange={"rules_layout": {}},
                )
        return redirect(
            reverse(
                f"plugins:netbox_nsm:{self.rules_tab_route}",
                args=[instance.pk],
            )
        )

    def get_extra_context(self, request, instance):
        from netbox_nsm.rulebook_rules_tab import build_rulebook_rules_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        ctx = build_rulebook_rules_tab_context(
            request,
            instance,
            view_helpers=rulebook_views,
        )
        ctx["rules_tab_label"] = self.tab.label
        ctx["rules_tab_key"] = self.rules_tab_key
        return ctx


@register_model_view(Rulebook, name="rules")
class RulebookRulesView(_RulebookRulesTabMixin, generic.ObjectView):
    tab = ViewTab(
        label=_("Rules"),
        permission="netbox_nsm.view_rulebook",
        weight=100,
        hide_if_empty=True,
    )


@register_model_view(Rulebook, name="test", path="test")
class RulebookRulesTestRedirectView(generic.ObjectView):
    """Legacy /test/ prototype URL → /rules/."""

    queryset = Rulebook.objects.all()

    def get(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        from netbox_nsm.branch_urls import with_branch_query

        rules_url = reverse(
            "plugins:netbox_nsm:rulebook_rules",
            args=[instance.pk],
        )
        query = request.GET.urlencode()
        if query:
            rules_url = f"{rules_url}?{query}"
        return redirect(with_branch_query(rules_url, request), permanent=True)


@register_model_view(Rulebook, "list", path="", detail=False)
class RulebookListView(generic.ObjectListView):
    queryset = (
        Rulebook.objects.prefetch_related("assignments__assigned_object_type")
        .select_related("platform", "parent")
        .annotate(rule_count=Count("rules"))
    )
    filterset = RulebookFilterSet
    filterset_form = RulebookFilterForm
    table = RulebookTable
    template_name = "netbox_nsm/rulebook_list.html"
    actions = (AddObject, BulkDelete)

    def get_table(self, data, request, bulk_actions=True):
        from netbox_nsm.rulebook_hierarchy import hierarchy_depth, rulebook_tree_order

        data_list = list(data)
        depth_cache: dict[int, int] = {}
        for rb in data_list:
            rb.nsm_list_depth = hierarchy_depth(rb, _cache=depth_cache)
        order_map = {
            pk: idx for idx, pk in enumerate(rulebook_tree_order(data_list))
        }
        data_list.sort(key=lambda rb: order_map.get(rb.pk, 999999))
        return super().get_table(
            data_list,
            request,
            bulk_actions,
        )


@register_model_view(Rulebook, "add", detail=False)
@register_model_view(Rulebook, "edit")
class RulebookEditView(generic.ObjectEditView):
    queryset = Rulebook.objects.all()
    form = RulebookForm


@register_model_view(Rulebook, "delete")
class RulebookDeleteView(generic.ObjectDeleteView):
    queryset = Rulebook.objects.all()


@register_model_view(Rulebook, "bulk_edit", path="edit", detail=False)
class RulebookBulkEditView(generic.BulkEditView):
    queryset = Rulebook.objects.annotate(rule_count=Count("rules"))
    filterset = RulebookFilterSet
    table = RulebookTable
    form = RulebookBulkEditForm


@register_model_view(Rulebook, "bulk_delete", path="delete", detail=False)
class RulebookBulkDeleteView(generic.BulkDeleteView):
    queryset = Rulebook.objects.all()
    table = RulebookTable


def _extract_ip_refs(obj):
    """Return list of {display, url, type} for IP-relevant objects reachable from obj."""
    return _extract_ip_refs_visited(obj, set())


_FIELD_TYPE_LABELS = {
    "prefix": "Prefix",
    "ip_address": "IP Address",
    "range": "Range",
}


def _addr_ip_ref(obj):
    """Return {str, url, type} when obj references an IPAM object, else None."""
    for field_name in ("prefix", "ip_address", "range"):
        try:
            related = getattr(obj, field_name, None)
            if related is not None:
                return {
                    "str": str(related),
                    "url": related.get_absolute_url(),
                    "type": _FIELD_TYPE_LABELS.get(field_name, field_name),
                }
        except Exception:
            pass
    return None


def _addr_group_members(obj):
    """Members contained in this nsm_addresses group (forward M2M on ``group``)."""
    group_rel = getattr(obj, "group", None)
    if group_rel is None or not hasattr(group_rel, "all"):
        return []
    try:
        return list(group_rel.all().order_by("name"))
    except Exception:
        try:
            return list(group_rel.all())
        except Exception:
            return []


def _addr_is_group_container(obj):
    """True when obj has no direct IP but contains other address objects."""
    if _addr_ip_ref(obj) is not None:
        return False
    if getattr(obj, "address_type", None) == "address-group":
        return True
    return bool(_addr_group_members(obj))


def _extract_ip_refs_visited(obj, visited=None):
    """Like _extract_ip_refs but accepts a visited set to avoid cycles in address groups."""
    if visited is None:
        visited = set()
    refs = []

    fd = getattr(obj, "field_data", None)
    if fd:
        for v in fd.values():
            if (
                isinstance(v, dict)
                and (v.get("str") or v.get("display"))
                and v.get("url")
            ):
                refs.append(
                    {
                        "display": v.get("display") or v.get("str"),
                        "url": v["url"],
                        "type": "",
                    }
                )
        return refs

    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            refs.append(
                {
                    "display": str(obj),
                    "url": obj.get_absolute_url(),
                    "type": obj._meta.verbose_name.capitalize(),
                }
            )
            return refs
    except Exception:
        pass

    ip_ref = _addr_ip_ref(obj)
    if ip_ref is None and _addr_is_group_container(obj):
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        for member in members:
            if member.pk not in visited:
                visited.add(member.pk)
                refs.extend(_extract_ip_refs_visited(member, visited))
        return refs

    if ip_ref is not None:
        refs.append(
            {
                "display": ip_ref["str"],
                "url": ip_ref["url"],
                "type": ip_ref["type"],
            }
        )

    return refs


def _collect_ips_from_group(group, visited=None):
    """Recursively resolve IPs from ObjectGroup sub_groups."""
    if visited is None:
        visited = set()
    if group.pk in visited:
        return []
    visited.add(group.pk)
    refs = []
    for sub in group.sub_groups.all():
        refs.extend(_collect_ips_from_group(sub, visited))
    return refs


def _addr_node_prefix_cidr(*, obj=None, ip_ref=None):
    """Return CIDR string for IPv4 IPAM prefixes and host addresses (e.g. /32)."""
    if ip_ref:
        ip_ref_type = ip_ref.get("type")
        cidr = ip_ref.get("str")
        if ip_ref_type == _FIELD_TYPE_LABELS["prefix"]:
            return cidr
        if ip_ref_type == _FIELD_TYPE_LABELS["ip_address"]:
            if cidr and "/" in cidr:
                return cidr
        if not ip_ref_type and cidr and "/" in cidr:
            return cidr
    if obj is not None:
        try:
            if obj._meta.app_label == "ipam":
                if obj._meta.model_name == "prefix":
                    prefix_val = getattr(obj, "prefix", None)
                    return str(prefix_val) if prefix_val is not None else str(obj)
                if obj._meta.model_name == "ipaddress":
                    addr = getattr(obj, "address", None)
                    cidr = str(addr) if addr is not None else str(obj)
                    if cidr and "/" in cidr:
                        return cidr
        except Exception:
            pass
    return None


def _attach_addr_node_prefix_display(node, *, obj=None, ip_ref=None):
    """Attach CIDR/netmask display labels to address-tree nodes for IPv4 prefixes/hosts."""
    from netbox_nsm.addr_netmask import prefix_display_labels_for_cidr

    cidr = _addr_node_prefix_cidr(obj=obj, ip_ref=ip_ref)
    if not cidr:
        return node
    labels = prefix_display_labels_for_cidr(cidr)
    if labels:
        node["prefix_display_cidr"], node["prefix_display_netmask"] = labels
    return node


_IPAM_ADDR_MODEL_NAMES = frozenset({"prefix", "ipaddress", "iprange"})
_IPAM_PREFIX_CHILDREN_MAX = 250


def _is_ipam_addr_object(obj) -> bool:
    try:
        return (
            obj._meta.app_label == "ipam"
            and obj._meta.model_name in _IPAM_ADDR_MODEL_NAMES
        )
    except Exception:
        return False


def _collect_ipam_prefix_children(prefix):
    """Return analyzable children contained in or linked to an IPAM prefix."""
    from ipam.models import IPAddress, IPRange, Prefix

    cidr = str(prefix.prefix)
    limit = _IPAM_PREFIX_CHILDREN_MAX
    children = []

    for child in (
        Prefix.objects.filter(prefix__net_contained_or_equal=cidr)
        .exclude(pk=prefix.pk)
        .order_by("prefix")[:limit]
    ):
        children.append(child)

    for ip in IPAddress.objects.filter(address__net_contained_or_equal=cidr).order_by(
        "address"
    )[:limit]:
        children.append(ip)

    for rng in IPRange.objects.filter(
        start_address__net_contained_or_equal=cidr,
        end_address__net_contained_or_equal=cidr,
    ).order_by("start_address")[:limit]:
        children.append(rng)

    from netbox_nsm.address_ipam_fk import get_nsm_address_model

    addr_model = get_nsm_address_model()
    if addr_model is not None:
        for addr in addr_model.objects.filter(prefix_id=prefix.pk).order_by("name")[
            :limit
        ]:
            children.append(addr)

    return children


def _build_addr_tree_node(obj, visited=None):
    """
    Recursively build an address hierarchy tree node for nsm_addresses objects.
    Returns: {name, url, kind: 'group'|'leaf', ip_ref: {str,url}|None, children: [...]}
    """
    if visited is None:
        visited = set()
    if obj.pk in visited:
        return None
    visited.add(obj.pk)

    ip_ref = _addr_ip_ref(obj)

    if ip_ref is None and _addr_is_group_container(obj):
        children = []
        members = _addr_group_members(obj)
        if getattr(obj, "address_type", None) == "address-group":
            try:
                legacy = list(obj.address_group.all())
                seen = {m.pk for m in members}
                members.extend(m for m in legacy if m.pk not in seen)
            except Exception:
                pass
        for sub in members:
            child = _build_addr_tree_node(sub, visited)
            if child:
                children.append(child)
        return {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "group",
            "ip_ref": None,
            "children": children,
        }

    if ip_ref is not None:
        node = {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "leaf",
            "ip_ref": {"str": ip_ref["str"], "url": ip_ref["url"]},
            "children": [],
        }
        return _attach_addr_node_prefix_display(node, obj=obj, ip_ref=ip_ref)

    # IPAM prefix — expand contained IPs, ranges, child prefixes, linked addresses
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name == "prefix":
            child_nodes = []
            for child_obj in _collect_ipam_prefix_children(obj):
                child = _build_addr_tree_node(child_obj, visited)
                if child:
                    child_nodes.append(child)
            if not child_nodes:
                return None
            node = {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "group",
                "ip_ref": None,
                "children": child_nodes,
            }
            return _attach_addr_node_prefix_display(node, obj=obj)
    except Exception:
        pass

    # Other IPAM objects — treat as leaf
    try:
        if obj._meta.app_label == "ipam":
            node = {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "leaf",
                "ip_ref": {"str": str(obj), "url": obj.get_absolute_url()},
                "children": [],
            }
            return _attach_addr_node_prefix_display(
                node, obj=obj, ip_ref=node["ip_ref"]
            )
    except Exception:
        pass
    return {
        "name": str(getattr(obj, "name", obj)),
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
        "kind": "leaf",
        "ip_ref": None,
        "children": [],
    }


def _addr_path_line(path_parts):
    """CSV path: group,group,...,ip (comma-separated, no spaces)."""
    return ",".join(str(p) for p in path_parts if p is not None and str(p) != "")


def _addr_path_parts_for_leaf(node, path_prefix):
    """Build CSV path segments for a leaf (object name + IP when both differ)."""
    row = list(path_prefix)
    ip_ref = node.get("ip_ref")
    if ip_ref and ip_ref.get("str"):
        ip_str = str(ip_ref["str"])
        name = str(node.get("name") or "").strip()
        if name and name != ip_str:
            row.append(name)
        row.append(ip_str)
    else:
        row.append(node["name"])
    return row


def _prefix_addr_copy_lines(lines, *prefix_parts):
    """Prepend fixed CSV segments (e.g. ``all``) to each copy line."""
    head = _addr_path_line(list(prefix_parts))
    if not head:
        return list(lines or [])
    prefixed = []
    for line in lines or []:
        text = str(line).strip()
        prefixed.append(f"{head},{text}" if text else head)
    return prefixed


def _flatten_addr_tree_paths(nodes, path_prefix=None):
    """Flatten address tree nodes to comma-separated path lines (one per leaf)."""
    if path_prefix is None:
        path_prefix = []
    lines = []
    for node in nodes:
        if node.get("kind") == "group":
            branch = path_prefix + [node["name"]]
            children = node.get("children") or []
            if children:
                lines.extend(_flatten_addr_tree_paths(children, branch))
            else:
                lines.append(_addr_path_line(branch))
        else:
            lines.append(_addr_path_line(_addr_path_parts_for_leaf(node, path_prefix)))
    return lines


def _enrich_addr_tree_leaf_counts(node):
    """Attach leaf_count (resolved IP paths in subtree) to each node."""
    if node.get("kind") == "group":
        total = 0
        for child in node.get("children") or []:
            _enrich_addr_tree_leaf_counts(child)
            total += child.get("leaf_count") or 0
        node["leaf_count"] = total
    else:
        node["leaf_count"] = 1
    return node


def _enrich_addr_tree_copy_lines(node, path_prefix=None):
    """Attach copy_lines (subtree) to each group/leaf node for template copy buttons."""
    if path_prefix is None:
        path_prefix = []
    if node.get("kind") == "group":
        branch = path_prefix + [node["name"]]
        child_lines = []
        for child in node.get("children") or []:
            _enrich_addr_tree_copy_lines(child, branch)
            child_lines.extend(child.get("copy_lines") or [])
        node["copy_lines"] = child_lines
    else:
        node["copy_lines"] = [
            _addr_path_line(_addr_path_parts_for_leaf(node, path_prefix))
        ]
    return node


def _get_rulebook_address_fields(rulebook):
    return (
        RulebookField.objects.filter(
            rulebook=rulebook,
            field_kind=RulebookFieldKind.OBJECT,
            type_configs__type_config__matching_class=MatchingClassChoices.ADDRESS,
        )
        .distinct()
        .prefetch_related("type_configs__type_config__content_type")
        .order_by("sort_order", "slug")
    )


def _build_addr_tree_nodes(objs, *, all_copy_prefix="all"):
    """Build enriched tree nodes and flat CSV path lines for a list of address objects."""
    nodes = []
    for obj in objs:
        node = _build_addr_tree_node(obj)
        if node:
            _enrich_addr_tree_copy_lines(node)
            _enrich_addr_tree_leaf_counts(node)
            nodes.append(node)
    flat_lines = _flatten_addr_tree_paths(nodes)
    if all_copy_prefix:
        flat_lines = _prefix_addr_copy_lines(flat_lines, all_copy_prefix)
    return nodes, flat_lines


def _object_supports_addr_analysis(obj):
    """True when obj can be expanded as an address tree (group container or IP leaf)."""
    if _addr_ip_ref(obj) is not None or _addr_is_group_container(obj):
        return True
    try:
        if obj._meta.app_label == "ipam" and obj._meta.model_name in (
            "prefix",
            "ipaddress",
            "iprange",
        ):
            return True
    except Exception:
        pass
    return False


def _object_is_addr_analyzable(obj, content_type_id, matching_class_map=None):
    """True when content type is address-class and the object can be IP-analyzed."""
    if not obj or not content_type_id:
        return False
    if not _object_supports_addr_analysis(obj):
        return False
    if _is_ipam_addr_object(obj):
        return True
    from netbox_nsm.models.type_config import MatchingClassChoices

    if matching_class_map is None:
        matching_class_map = {
            tc.content_type_id: tc.matching_class
            for tc in TypeConfig.objects.only("content_type_id", "matching_class")
        }
    try:
        ct_id = int(content_type_id)
    except (TypeError, ValueError):
        return False
    return matching_class_map.get(ct_id) == MatchingClassChoices.ADDRESS


def _build_multi_object_addr_analysis(objs):
    """IP Analysis: merged tree for one or more selected objects."""
    supported = [o for o in objs if o and _object_supports_addr_analysis(o)]
    if not supported:
        return []
    nodes, all_copy_lines = _build_addr_tree_nodes(supported)
    if not nodes:
        return []
    return [
        {
            "field_name": "",
            "field_slug": "selected",
            "types": [
                {
                    "type_name": "",
                    "type_config": None,
                    "nodes": nodes,
                    "all_copy_lines": all_copy_lines,
                    "leaf_count": len(all_copy_lines),
                    "has_objects": True,
                }
            ],
        }
    ]


def _leaf_count_for_addr_analysis(sections) -> int:
    total = 0
    for section in sections or []:
        for type_block in section.get("types") or []:
            total += int(type_block.get("leaf_count") or 0)
    return total


def _build_ipa_object_columns(selections, objs):
    """IP Analysis: one table column per selected object (name + counter in header)."""
    columns = []
    for sel, obj in zip(selections, objs):
        analysis = _build_multi_object_addr_analysis([obj]) if obj else []
        columns.append(
            {
                "name": sel["name"],
                "ct": sel["ct"],
                "pk": sel["pk"],
                "leaf_count": _leaf_count_for_addr_analysis(analysis),
                "addr_analysis": analysis,
            }
        )
    return columns


def _parse_ipa_column_selections(request, col_suffix=""):
    """
    Parse repeated ip_ct/ip_pk/ip_name (or ip2_*) query params.
    Returns (selections, addr_analysis) where selections is
    [{"ct", "pk", "name"}, ...].
    """
    from django.contrib.contenttypes.models import ContentType as _CT

    prefix = f"ip{col_suffix}_"
    ct_list = request.GET.getlist(prefix + "ct")
    pk_list = request.GET.getlist(prefix + "pk")
    name_list = request.GET.getlist(prefix + "name")

    selections = []
    objs = []
    seen: set = set()

    for i, ct_str in enumerate(ct_list):
        pk_str = pk_list[i] if i < len(pk_list) else ""
        name_hint = name_list[i] if i < len(name_list) else ""
        if not (str(ct_str).isdigit() and str(pk_str).isdigit()):
            continue
        key = (int(ct_str), int(pk_str))
        if key in seen:
            continue
        try:
            ct = _CT.objects.get(pk=key[0])
            mc = ct.model_class()
            if not mc:
                continue
            obj = mc.objects.filter(pk=key[1]).first()
            if not obj:
                continue
            seen.add(key)
            name = getattr(obj, "name", None) or name_hint or str(obj)
            selections.append({"ct": str(key[0]), "pk": str(key[1]), "name": str(name)})
            objs.append(obj)
        except Exception:
            continue

    return selections, _build_ipa_object_columns(selections, objs)


def _build_object_address_analysis(_rulebook, obj, content_type_id):
    """Address analysis for a single object (IP Analysis — object only, no src/dst)."""
    if not obj or not content_type_id:
        return []
    return _build_multi_object_addr_analysis([obj])


def _build_rulebook_address_analysis(rulebook, objects_by_field_ct):
    """
    For each rulebook column that allows address types, list all configured types
    with object trees (root label "All", copy = comma-separated paths).
    objects_by_field_ct: {field_id: {content_type_id: [objects]}}
    """
    if not rulebook:
        return []

    sections = []
    for field in _get_rulebook_address_fields(rulebook):
        type_blocks = []
        for ft in field.type_configs.select_related("type_config").order_by(
            "sort_order", "type_config__order_id"
        ):
            tc = ft.type_config
            objs = (objects_by_field_ct.get(field.pk) or {}).get(tc.content_type_id, [])
            nodes, all_copy_lines = _build_addr_tree_nodes(objs)
            type_blocks.append(
                {
                    "type_name": tc.name,
                    "type_config": tc,
                    "nodes": nodes,
                    "all_copy_lines": all_copy_lines,
                    "leaf_count": len(all_copy_lines),
                    "has_objects": bool(objs),
                }
            )
        if type_blocks:
            sections.append(
                {
                    "field_name": field.name,
                    "field_slug": field.slug,
                    "types": type_blocks,
                }
            )
    return sections


@register_model_view(Rule)
class RuleView(generic.ObjectView):
    queryset = Rule.objects.prefetch_related(
        "source_users",
        "destination_users",
        "object_items__field",
        "object_items__content_type",
        "group_items__field",
        "group_items__security_group",
    ).select_related("rulebook")

    def get_extra_context(self, request, instance):
        src_items = instance.object_items.filter(
            field__placement="source"
        ).select_related("field")
        dst_items = instance.object_items.filter(
            field__placement="destination"
        ).select_related("field")

        src_group_items = instance.group_items.filter(
            field__placement="source"
        ).select_related("security_group")
        dst_group_items = instance.group_items.filter(
            field__placement="destination"
        ).select_related("security_group")

        fixed_object_items = instance.object_items.filter(
            field__placement="fixed"
        ).select_related("field")
        fixed_group_items = instance.group_items.filter(
            field__placement="fixed"
        ).select_related("field", "security_group")

        fixed_objects_by_area = {}
        for item in fixed_object_items:
            assigned = item.assigned_object
            if assigned and item.field:
                fixed_objects_by_area.setdefault(item.field.slug, []).append(assigned)

        fixed_groups_by_area = {}
        for item in fixed_group_items:
            if item.field:
                fixed_groups_by_area.setdefault(item.field.slug, []).append(
                    item.security_group
                )

        vgc = instance.virtual_group_config or {}

        def _group_label(objects):
            names = sorted(str(getattr(o, "name", str(o))) for o in objects)
            return " | ".join(names)

        source_objs = [
            item.assigned_object for item in src_items if item.assigned_object
        ]
        dest_objs = [item.assigned_object for item in dst_items if item.assigned_object]
        svc_objs = fixed_objects_by_area.get("service", [])
        act_objs = fixed_objects_by_area.get("action", [])

        return {
            "source_objects": source_objs,
            "destination_objects": dest_objs,
            "source_groups": [item.security_group for item in src_group_items],
            "destination_groups": [item.security_group for item in dst_group_items],
            "service_objects": svc_objs,
            "service_groups": fixed_groups_by_area.get("service", []),
            "action_objects": act_objs,
            "action_groups": fixed_groups_by_area.get("action", []),
            "info_objects": fixed_objects_by_area.get("info", []),
            "info_groups": fixed_groups_by_area.get("info", []),
            "vgroup_source": bool(vgc.get("source", False)),
            "vgroup_source_label": _group_label(source_objs),
            "vgroup_destination": bool(vgc.get("destination", False)),
            "vgroup_destination_label": _group_label(dest_objs),
            "vgroup_services": bool(vgc.get("services", False)),
            "vgroup_services_label": _group_label(svc_objs),
            "vgroup_action": bool(vgc.get("action", False)),
            "vgroup_action_label": _group_label(act_objs),
        }


@register_model_view(Rule, "list", path="", detail=False)
class RuleListView(generic.ObjectListView):
    queryset = Rule.objects.select_related("rulebook")
    filterset = RuleFilterSet
    filterset_form = RuleFilterForm
    table = RuleTable


@register_model_view(Rule, "add", detail=False)
@register_model_view(Rule, "edit")
class RuleEditView(generic.ObjectEditView):
    queryset = Rule.objects.all()
    form = RuleForm
    template_name = "netbox_nsm/rule_edit.html"

    def dispatch(self, request, *args, **kwargs):
        from netbox_nsm.branch_db import resolve_db_alias, use_db_alias

        alias = resolve_db_alias(request=request)
        if alias:
            with use_db_alias(alias):
                return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """
        NetBox ``ObjectEditView.post()`` builds the form without ``request=`` and
        calls ``form.save()`` directly (not ``form_valid()``). Inject *request*
        and keep ``active_branch`` set for junction-table writes (``TaggedItem``
        / ``INCLUDE_MODELS`` pattern).
        """
        from netbox_nsm.branch_db import ensure_branch_context

        base_form = self.form
        req = request

        class _RequestRuleForm(base_form):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("request", req)
                super().__init__(*args, **kwargs)

        self.form = _RequestRuleForm
        try:
            with ensure_branch_context(request):
                return super().post(request, *args, **kwargs)
        finally:
            self.form = base_form

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form._request = self.request
        return form

    def form_valid(self, form):
        from netbox_nsm.branch_db import (
            ensure_branch_context,
            required_junction_db_alias,
            use_db_alias,
        )

        form._request = self.request
        db_alias = required_junction_db_alias(form.instance, self.request)
        with ensure_branch_context(self.request):
            with use_db_alias(db_alias):
                return super().form_valid(form)

    def alter_object(self, instance, request, args, kwargs):
        """Pre-fill index and comments from rulebook template when creating a new rule."""
        if not instance.pk:
            rulebook_pk = request.GET.get("rulebook")
            if rulebook_pk and str(rulebook_pk).isdigit():
                try:
                    rulebook = Rulebook.objects.get(pk=int(rulebook_pk))
                    result = Rule.objects.filter(rulebook_id=rulebook.pk).aggregate(
                        max_index=Max("index")
                    )
                    instance.index = (result.get("max_index") or 0) + 1
                    if rulebook.rule_comment_template and not instance.comments:
                        try:
                            instance.comments = (
                                rulebook.rule_comment_template.format_map(
                                    {
                                        "rulebook": rulebook.name,
                                        "index": instance.index,
                                        "rule_name": "",
                                    }
                                )
                            )
                        except (KeyError, ValueError):
                            instance.comments = rulebook.rule_comment_template
                except Rulebook.DoesNotExist:
                    pass
            elif not instance.rulebook_id:
                rulebook_pk = request.POST.get("rulebook") or request.GET.get(
                    "rulebook"
                )
                if rulebook_pk and str(rulebook_pk).isdigit():
                    instance.rulebook_id = int(rulebook_pk)
        return instance

    def get_extra_context(self, request, instance):
        from netbox_nsm.branch_urls import branch_schema_id_from_request
        from netbox_nsm.display_utils import type_name_for_field_content_type

        # Build current selections JSON for pre-populating the picker on edit
        selections = []
        if instance.pk:
            from netbox_nsm.models import TypeConfig as _TC

            _mc_map = {
                tc.content_type_id: tc.matching_class
                for tc in _TC.objects.only("content_type_id", "matching_class")
            }

            for item in instance.object_items.select_related(
                "field", "content_type"
            ).prefetch_related("field__type_configs__type_config__content_type"):
                assigned = item.assigned_object
                try:
                    name = getattr(assigned, "name", None) or str(assigned)
                except Exception:
                    name = None
                if not name:
                    name = f"#{item.object_id}"
                selections.append(
                    {
                        "area": str(item.field.slug) if item.field else "",
                        "placement": str(item.field.placement) if item.field else "",
                        "kind": "object",
                        "id": f"{item.content_type_id}.{item.object_id}",
                        "name": str(name),
                        "typeName": type_name_for_field_content_type(
                            item.field, item.content_type_id
                        ),
                        "matchingClass": _mc_map.get(item.content_type_id, ""),
                        "color": getattr(assigned, "color", "") or "",
                        "exclude": bool(item.exclude),
                    }
                )
            for item in instance.group_items.select_related(
                "field", "security_group"
            ).all():
                selections.append(
                    {
                        "area": str(item.field.slug) if item.field else "",
                        "placement": str(item.field.placement) if item.field else "",
                        "kind": "group",
                        "id": str(item.security_group.pk),
                        "name": str(item.security_group.name),
                        "typeName": "Groups",
                        "exclude": bool(item.exclude),
                    }
                )
        rulebook = getattr(instance, "rulebook", None)
        if rulebook is None and getattr(instance, "rulebook_id", None):
            try:
                rulebook = Rulebook.objects.get(pk=instance.rulebook_id)
            except Rulebook.DoesNotExist:
                pass
        if rulebook is None and not instance.pk:
            rulebook_pk = request.GET.get("rulebook") or request.POST.get("rulebook")
            if rulebook_pk and str(rulebook_pk).isdigit():
                try:
                    rulebook = Rulebook.objects.get(pk=int(rulebook_pk))
                except Rulebook.DoesNotExist:
                    pass

        picker_catalog = {
            str(rb.pk): _build_security_rule_picker_data(rulebook=rb)
            for rb in Rulebook.objects.all().order_by("name")
        }

        # Pre-fill source/destination zones from matrix add_href params
        if not instance.pk and rulebook:
            from netbox_nsm.display_utils import ct_display_label
            from netbox_nsm.models import TypeConfig as _TC

            _mc_map = {
                tc.content_type_id: tc.matching_class
                for tc in _TC.objects.only("content_type_id", "matching_class")
            }
            src_field = RulebookField.objects.filter(
                rulebook=rulebook, placement="source"
            ).first()
            dst_field = RulebookField.objects.filter(
                rulebook=rulebook, placement="destination"
            ).first()
            for param_ct, param_obj, field in [
                ("prefill_src_ct", "prefill_src_obj", src_field),
                ("prefill_dst_ct", "prefill_dst_obj", dst_field),
            ]:
                ct_val = request.GET.get(param_ct, "")
                obj_val = request.GET.get(param_obj, "")
                if not (ct_val.isdigit() and obj_val.isdigit() and field):
                    continue
                ct_id = int(ct_val)
                obj_pk = int(obj_val)
                try:
                    ct = ContentType.objects.get(pk=ct_id)
                    mc = ct.model_class()
                    obj = mc.objects.get(pk=obj_pk) if mc else None
                    name = (
                        getattr(obj, "name", None) or str(obj) if obj else f"#{obj_pk}"
                    )
                except Exception:
                    name = f"#{obj_pk}"
                    ct = None
                selections.append(
                    {
                        "area": str(field.slug),
                        "placement": str(field.placement),
                        "kind": "object",
                        "id": f"{ct_id}.{obj_pk}",
                        "name": name,
                        "typeName": type_name_for_field_content_type(field, ct_id),
                        "matchingClass": _mc_map.get(ct_id, ""),
                        "color": getattr(obj, "color", "") or "" if obj else "",
                        "exclude": False,
                    }
                )
        return {
            "nsm_rule_picker_catalog": picker_catalog,
            "nsm_rule_picker_rulebook_id": rulebook.pk if rulebook else None,
            "nsm_active_branch": branch_schema_id_from_request(request),
            "nsm_rule_selections": selections,
            "nsm_rule_virtual_groups": (
                instance.virtual_group_config if instance.pk else {}
            ),
            "nsm_rule_slots": _build_rule_edit_rule_slots(rulebook),
        }


@register_model_view(Rule, "delete")
class RuleDeleteView(generic.ObjectDeleteView):
    queryset = Rule.objects.all()

    def dispatch(self, request, *args, **kwargs):
        from netbox_nsm.branch_db import resolve_db_alias, use_db_alias

        alias = resolve_db_alias(request=request)
        if alias:
            with use_db_alias(alias):
                return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_return_url(self, request, obj=None):
        return_url = request.GET.get("return_url") or request.POST.get("return_url")
        if return_url:
            return return_url
        instance = obj
        if instance is None:
            try:
                instance = self.get_object()
            except Exception:
                instance = None
        if instance is not None and instance.rulebook_id:
            return reverse(
                "plugins:netbox_nsm:rulebook_rules",
                args=[instance.rulebook_id],
            )
        return super().get_return_url(request, obj=obj)

    def post(self, request, *args, **kwargs):
        from utilities.forms import DeleteForm

        from netbox_nsm.branch_db import ensure_branch_context
        from netbox_nsm.changelog_utils import record_rulebook_rules_changelog
        from netbox_nsm.rulebook_rules_utils import snapshot_rule_layout_entry

        obj = self.get_object(**kwargs)
        rulebook = obj.rulebook
        rb_prechange = None
        form = DeleteForm(request.POST, instance=obj)
        if form.is_valid():
            with ensure_branch_context(request):
                rb_prechange = snapshot_rule_layout_entry(obj)

        response = super().post(request, *args, **kwargs)
        if rb_prechange is not None:
            with ensure_branch_context(request):
                record_rulebook_rules_changelog(
                    rulebook,
                    request,
                    rb_prechange,
                    postchange={"rules_layout": {}},
                )
        return response


@register_model_view(Rule, "bulk_edit", path="edit", detail=False)
class RuleBulkEditView(generic.BulkEditView):
    queryset = Rule.objects.all()
    form = RuleBulkEditForm


@register_model_view(Rule, "bulk_delete", path="delete", detail=False)
class RuleBulkDeleteView(generic.BulkDeleteView):
    queryset = Rule.objects.all()

    def post(self, request, *args, **kwargs):
        rulebook_snapshots = None
        if "_confirm" in request.POST:
            pk_list = [pk for pk in request.POST.getlist("pk") if str(pk).isdigit()]
            if pk_list:
                from netbox_nsm.branch_db import ensure_branch_context
                from netbox_nsm.models import Rulebook
                from netbox_nsm.rulebook_rules_utils import snapshot_rules_layout_entries

                queryset = self.queryset.filter(pk__in=pk_list)
                with ensure_branch_context(request):
                    rulebook_snapshots = {}
                    for rulebook_id in queryset.values_list(
                        "rulebook_id", flat=True
                    ).distinct():
                        rules = queryset.filter(rulebook_id=rulebook_id)
                        rulebook = Rulebook.objects.get(pk=rulebook_id)
                        rulebook_snapshots[rulebook_id] = (
                            rulebook,
                            snapshot_rules_layout_entries(rules),
                        )
        response = super().post(request, *args, **kwargs)
        if rulebook_snapshots:
            from netbox_nsm.branch_db import ensure_branch_context
            from netbox_nsm.changelog_utils import record_rulebook_rules_changelog

            with ensure_branch_context(request):
                for rulebook, prechange in rulebook_snapshots.values():
                    record_rulebook_rules_changelog(
                        rulebook,
                        request,
                        prechange,
                        postchange={"rules_layout": {}},
                    )
        return response


@register_model_view(RulebookAssignment, "list", path="", detail=False)
class RulebookAssignmentListView(generic.ObjectListView):
    queryset = RulebookAssignment.objects.all()
    filterset = RulebookAssignmentFilterSet
    filterset_form = RulebookAssignmentFilterForm
    table = RulebookAssignmentTable
    actions = {"export": {"view"}}


@register_model_view(RulebookAssignment, "add", detail=False)
@register_model_view(RulebookAssignment, "edit")
class RulebookAssignmentEditView(generic.ObjectEditView):
    queryset = RulebookAssignment.objects.all()
    form = RulebookAssignmentForm

    def alter_object(self, instance, request, args, kwargs):
        if not instance.pk:
            content_type = get_object_or_404(
                ContentType, pk=request.GET.get("assigned_object_type")
            )
            instance.assigned_object = get_object_or_404(
                content_type.model_class(), pk=request.GET.get("assigned_object_id")
            )
        return instance

    def get_extra_addanother_params(self, request):
        return {
            "assigned_object_type": request.GET.get("assigned_object_type"),
            "assigned_object_id": request.GET.get("assigned_object_id"),
        }


@register_model_view(RulebookAssignment, "delete")
class RulebookAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = RulebookAssignment.objects.all()


@register_model_view(RulebookAssignment, "bulk_delete", path="delete", detail=False)
class RulebookAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = RulebookAssignment.objects.all()
    table = RulebookAssignmentTable


class RulebookBulkAssignView(generic.ObjectView):
    """Assign a rulebook to multiple devices / VMs / VDCs in one step."""

    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/rulebook_bulk_assign.html"

    def get(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        form = RulebookBulkAssignForm()
        return self.render_to_response({"object": instance, "form": form})

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        form = RulebookBulkAssignForm(request.POST)
        if form.is_valid():
            created = 0
            skipped = 0
            for device in form.cleaned_data.get("devices") or []:
                ct = ContentType.objects.get_for_model(device)
                _, c = RulebookAssignment.objects.get_or_create(
                    rulebook=instance,
                    assigned_object_type=ct,
                    assigned_object_id=device.pk,
                )
                if c:
                    created += 1
                else:
                    skipped += 1
            for vm in form.cleaned_data.get("virtual_machines") or []:
                ct = ContentType.objects.get_for_model(vm)
                _, c = RulebookAssignment.objects.get_or_create(
                    rulebook=instance,
                    assigned_object_type=ct,
                    assigned_object_id=vm.pk,
                )
                if c:
                    created += 1
                else:
                    skipped += 1
            for vdc in form.cleaned_data.get("virtual_device_contexts") or []:
                ct = ContentType.objects.get_for_model(vdc)
                _, c = RulebookAssignment.objects.get_or_create(
                    rulebook=instance,
                    assigned_object_type=ct,
                    assigned_object_id=vdc.pk,
                )
                if c:
                    created += 1
                else:
                    skipped += 1
            from django.contrib import messages as dj_messages

            dj_messages.success(
                request,
                _("%(created)d assignment(s) created, %(skipped)d already existed.")
                % {"created": created, "skipped": skipped},
            )
            return redirect(instance.get_absolute_url())
        return self.render_to_response({"object": instance, "form": form})


class GlobalRulesSearchView(View):
    """
    Global search across ALL rulebooks using the NSM Query Engine.
    GET param: nsm_q — query string (e.g. 'Source.Labels = Web AND Action = Permit')
    Results are grouped by rulebook with match counts.
    URL: /plugins/netbox-nsm/rules/search/
    """

    template_name = "netbox_nsm/global_rules_search.html"

    def get(self, request):
        from django.shortcuts import render as _render
        from netbox_nsm.query import parse
        from netbox_nsm.query.engine import global_search

        nsm_q_raw = request.GET.get("nsm_q", "").strip()
        query = parse(nsm_q_raw)

        rulebook_groups = []
        total_count = 0

        if nsm_q_raw and query.is_valid and not query.is_empty:
            result = global_search(
                Rule.objects.select_related("rulebook"),
                query,
            )
            rulebook_groups = result["rulebook_groups"]
            total_count = result["total_count"]

        return _render(
            request,
            self.template_name,
            {
                "nsm_q": nsm_q_raw,
                "nsm_query": query,
                "nsm_query_error": query.parse_error,
                "rulebook_groups": rulebook_groups,
                "total_count": total_count,
            },
        )
