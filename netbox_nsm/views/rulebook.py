from django.contrib.contenttypes.models import ContentType
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
    get_policy_column_labels,
    get_policy_column_slugs,
    get_visible_rulebook_fields,
    load_rulebook_fields_for_detail,
)
from netbox_nsm.tables import (
    RulebookAssignmentTable,
    RulebookTable,
    RuleTable,
)


def _policy_placement_for_area(area_slug):
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


def _policy_pill_html(item, *, hidden=False, colored=True):
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


def _render_policy_cell(items, max_pills=None, *, colored=True):
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
    parts = [_policy_pill_html(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(_policy_pill_html(item, hidden=True, colored=colored))
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


def _policy_pill_html_ag(item, *, hidden=False, colored=True):
    """AG Grid: colored dot + plain text link (no pill chrome)."""
    color = (item.get("color") or "").strip() if colored else ""
    dot_html = ""
    if color:
        dot_html = (
            f'<span class="nsm-ag-cell-dot" style="background-color:'
            f'{conditional_escape(color)};" aria-hidden="true"></span>'
        )
    hidden_class = " nsm-pill-hidden" if hidden else ""
    excluded_class = " nsm-ag-cell-excluded" if item.get("excluded") else ""
    return (
        f'<span class="nsm-ag-cell-item{hidden_class}{excluded_class}">'
        f"{dot_html}"
        f'<a href="{conditional_escape(item["url"])}" '
        f' class="nsm-ag-cell-link text-decoration-none"'
        f' title="{conditional_escape(item["name"])}">'
        f"{conditional_escape(item['name'])}"
        f"</a></span>"
    )


def _render_policy_cell_ag(items, max_pills=None, *, colored=True):
    if not items:
        return '<span class="nsm-cell-empty">-</span>'
    try:
        limit = max(
            1, int(max_pills if max_pills is not None else DEFAULT_MAX_VISIBLE_PILLS)
        )
    except (TypeError, ValueError):
        limit = DEFAULT_MAX_VISIBLE_PILLS
    shown = items[:limit]
    hidden = items[limit:]
    parts = [_policy_pill_html_ag(item, colored=colored) for item in shown]
    for item in hidden:
        parts.append(_policy_pill_html_ag(item, hidden=True, colored=colored))
    if hidden:
        parts.append(
            '<button type="button"'
            ' class="nsm-ag-cell-more"'
            " onclick=\"var c=this.closest('.nsm-ag-cell-list');"
            "c.querySelectorAll('.nsm-pill-hidden').forEach(function(e){e.style.display='';});"
            'this.remove();"'
            f">+{len(hidden)}</button>"
        )
    return f'<div class="nsm-ag-cell-list">{"".join(parts)}</div>'


def _build_grouped_policy_table_data(rules, rulebook):
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

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

    policy_layout = []
    header_groups = []
    grouped_columns = []
    group_idx = 0

    for field in visible_fields:
        if field.field_kind == RulebookFieldKind.SYSTEM:
            policy_layout.append(
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
        policy_layout.append(
            {
                "kind": "object",
                "slug": field_slug,
                "label": field.name,
                "group": group,
            }
        )
        group_idx += 1

    col_index = 1
    for entry in policy_layout:
        if entry["kind"] == "system":
            entry["col_index"] = col_index
            col_index += 1
        else:
            for col in entry["group"]["columns"]:
                col["col_index"] = col_index
                col_index += 1

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
        cells_ag = {}
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
            cells[k] = _render_policy_cell(v, max_pills=max_pills, colored=use_colored)
            cells_ag[k] = _render_policy_cell_ag(
                v, max_pills=max_pills, colored=use_colored
            )
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
                "cells_ag": cells_ag,
                "cells_filter": cells_filter,
            }
        )

    return {
        "policy_layout": policy_layout,
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

POLICY_TABLE_COLUMN_NAMES = frozenset(name for name, _ in SECURITY_RULES_COLUMNS)

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
                    "allow_virtual_groups": bool(tc.allow_virtual_groups),
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


def _available_policy_columns(rulebook=None):
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


def _build_rule_edit_policy_slots(rulebook=None):
    """Visible src/dst/service/action/info columns for the rule editor grid."""
    if rulebook is None:
        return []
    availability = _available_policy_columns(rulebook)
    labels = get_policy_column_labels(rulebook)
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


def _filter_policy_columns(columns, availability):
    filtered = []
    for column in columns:
        if column in availability and not availability.get(column, False):
            continue
        filtered.append(column)
    return filtered


def _policy_columns_session_key(rulebook_pk):
    return f"netbox_nsm_policy_columns_{rulebook_pk}"


def _default_security_rules_columns():
    return [
        column
        for column in RuleTable.Meta.default_columns
        if column in POLICY_TABLE_COLUMN_NAMES
    ]


def _normalize_policy_table_columns(columns, availability=None):
    """Keep only columns that exist on RuleTable (ignore rulebook-only slugs)."""
    normalized = []
    for column in columns:
        if column not in POLICY_TABLE_COLUMN_NAMES:
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


def _get_policy_table_config(request, rulebook):
    ensure_system_rulebook_fields(rulebook)
    availability = _available_policy_columns(rulebook)
    selected_columns = _normalize_policy_table_columns(
        get_policy_column_slugs(rulebook),
        availability,
    )
    config = request.session.get(_policy_columns_session_key(rulebook.pk), {})
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


def _build_policy_table_class(custom_columns, selected_columns):
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


def _build_object_analysis(rulebook):
    """Count per-area object usage across all rules in a rulebook."""
    from collections import Counter
    from netbox_nsm.models import (
        RuleObjectItem,
        RuleGroupItem,
    )

    rule_pks = list(Rule.objects.filter(rulebook=rulebook).values_list("pk", flat=True))
    total_rules = len(rule_pks)

    # Build a cache: content_type_id → human-readable verbose_name_plural
    _ct_label_cache: dict[int, str] = {}

    def _ct_label(ct):
        if ct is None:
            return "object"
        if ct.pk not in _ct_label_cache:
            try:
                from django.apps import apps as django_apps

                mc = ct.model_class()
                if mc is not None:
                    model_name = str(
                        getattr(mc._meta, "verbose_name", ct.model)
                    ).capitalize()
                    try:
                        app_cfg = django_apps.get_app_config(ct.app_label)
                        app_name = str(app_cfg.verbose_name)
                    except LookupError:
                        app_name = ct.app_label.replace("_", " ").capitalize()
                    label = f"{app_name} \u203a {model_name}"
                else:
                    label = ct.model.capitalize()
            except Exception:
                label = ct.model.capitalize()
            _ct_label_cache[ct.pk] = label
        return _ct_label_cache[ct.pk]

    areas_qs = RulebookField.objects.filter(rulebook=rulebook).order_by(
        "sort_order", "slug"
    )
    areas = []

    for area in areas_qs:
        individual = Counter()
        combos = Counter()

        obj_items = (
            RuleObjectItem.objects.filter(rule__in=rule_pks, field=area)
            .select_related("content_type", "rule")
            .order_by("rule_id")
        )
        grp_items = (
            RuleGroupItem.objects.filter(rule__in=rule_pks, field=area)
            .select_related("security_group", "rule")
            .order_by("rule_id")
        )

        by_rule: dict = {}
        for item in obj_items:
            assigned = item.assigned_object
            name = str(
                getattr(assigned, "name", None) or item.object_id
                if assigned
                else item.object_id
            )
            type_label = _ct_label(item.content_type if item.content_type_id else None)
            by_rule.setdefault(item.rule_id, []).append(name)
            individual[(name, type_label)] += 1
        for item in grp_items:
            by_rule.setdefault(item.rule_id, []).append(item.security_group.name)
            individual[(item.security_group.name, "Group")] += 1

        for names in by_rule.values():
            combos[" | ".join(sorted(set(names)))] += 1

        if not individual:
            continue

        areas.append(
            {
                "key": area.slug,
                "label": area.name,
                "total_objects": len(individual),
                "objects": [
                    {"name": name, "type_name": type_name, "count": count}
                    for (name, type_name), count in individual.most_common(10)
                ],
                "combos": [
                    {"label": label, "count": count}
                    for label, count in combos.most_common()
                ],
            }
        )

    return {"total_rules": total_rules, "areas": areas}


def _build_object_usage_stats(rulebook):
    """Count how often each object/group appears across all rules in a rulebook."""
    from collections import Counter
    from netbox_nsm.models import (
        RuleObjectItem,
        RuleGroupItem,
    )

    rule_pks = list(Rule.objects.filter(rulebook=rulebook).values_list("pk", flat=True))

    object_counter = Counter()
    for item in RuleObjectItem.objects.filter(rule__in=rule_pks).select_related(
        "content_type"
    ):
        assigned = item.assigned_object
        name = str(
            getattr(assigned, "name", None) or item.object_id
            if assigned
            else item.object_id
        )
        type_label = str(item.content_type.model) if item.content_type_id else "object"
        object_counter[(item.object_id, name, type_label)] += 1

    group_counter = Counter()
    for item in RuleGroupItem.objects.filter(rule__in=rule_pks).select_related(
        "security_group"
    ):
        group_counter[(item.security_group.pk, item.security_group.name)] += 1

    return {
        "top_objects": [
            {"pk": pk, "name": name, "type": type_name, "count": count}
            for (pk, name, type_name), count in object_counter.most_common(10)
        ],
        "top_groups": [
            {"pk": pk, "name": name, "count": count}
            for (pk, name), count in group_counter.most_common(10)
        ],
        "total_rules": len(rule_pks),
    }


__all__ = (
    "RulebookView",
    "RulebookListView",
    "RulebookEditView",
    "RulebookDeleteView",
    "RulebookBulkEditView",
    "RulebookBulkDeleteView",
    "RulebookPolicyColumnsView",
    "RulebookRulesGridView",
    "RulebookBulkAssignView",
    "RuleView",
    "RuleListView",
    "RuleEditView",
    "RuleDeleteView",
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


@register_model_view(Rulebook, name="analysis", path="analysis")
class RulebookAnalysisView(generic.ObjectView):
    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/rulebook_analysis.html"
    tab = ViewTab(
        label=_("Policy Analysis"),
        permission="netbox_nsm.view_rulebook",
        weight=200,
    )

    def get_extra_context(self, request, instance):
        return {
            "object_analysis": _build_object_analysis(instance),
        }


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


def _matrix_policy_href(
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
):
    from urllib.parse import quote

    from netbox_nsm.display_utils import get_display_template_map, render_object_display
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
    return f"{base_url}?nsm_q={quote(q, safe='')}"


@register_model_view(Rulebook, name="matrix", path="matrix")
class RulebookMatrixGridView(generic.ObjectView):
    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/rulebook_matrix_ag.html"
    tab = ViewTab(
        label=_("Matrix"),
        permission="netbox_nsm.view_rulebook",
        weight=110,
    )

    def get_extra_context(self, request, instance):
        from netbox_nsm.matrix_grid_payload import build_matrix_ag_grid_payload
        from netbox_nsm.matrix_tab_context import build_matrix_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        ctx = build_matrix_tab_context(
            request, instance, view_helpers=rulebook_views, client_axis_filters=True
        )
        ctx["matrix_ag_grid_payload"] = build_matrix_ag_grid_payload(
            ctx["matrix_rows"],
            ctx["dst_zones"],
            ctx["matrix_mode"],
            zone_content_type_id=ctx.get("selected_ct_id"),
            request=request,
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


@register_model_view(Rulebook, name="ipanalysis", path="ipanalysis")
class RulebookIPAnalysisView(generic.ObjectView):
    queryset = Rulebook.objects.all()
    template_name = "netbox_nsm/rulebook_ipanalysis.html"
    tab = ViewTab(
        label=_("IP Analysis"),
        permission="netbox_nsm.view_rulebook",
        weight=400,
    )

    def get_extra_context(self, request, instance):
        # Build searchable types from TypeConfig entries (deduplicated by ct_id)
        seen_ct_ids = set()
        ip_api_types = []
        for tc in TypeConfig.objects.select_related("content_type").order_by(
            "order_id", "content_type__app_label", "content_type__model"
        ):
            if tc.content_type_id in seen_ct_ids:
                continue
            mc = tc.content_type.model_class()
            if not mc:
                continue
            api_url = _get_api_url_for_content_type(tc.content_type)
            if not api_url:
                continue
            seen_ct_ids.add(tc.content_type_id)
            ip_api_types.append(
                {
                    "ct_id": tc.content_type.pk,
                    "api_url": api_url,
                    "name": str(mc._meta.verbose_name_plural).title(),
                }
            )

        ip_selections, ip_addr_analysis = _parse_ipa_column_selections(request, "")
        ip2_selections, ip2_addr_analysis = _parse_ipa_column_selections(request, "2")

        return {
            "ip_api_types": ip_api_types,
            "ip_selections": ip_selections,
            "ip_addr_analysis": ip_addr_analysis,
            "ip2_selections": ip2_selections,
            "ip2_addr_analysis": ip2_addr_analysis,
        }

    # ─── end of RulebookIPAnalysisView ───────────────────────


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

        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return {
                "assignments": assignments,
                "rulebook_fields": rulebook_fields,
                "rulebook_fields_system": rulebook_fields_system,
                "rulebook_fields_object": rulebook_fields_object,
                "has_object_rulebook_fields": has_object_rulebook_fields,
                "matching_classes": matching_classes,
            }

        availability = _available_policy_columns(instance)
        config = _get_policy_table_config(request, instance)
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
            "nsm_available_policy_areas": availability,
            "rulebook_fields": rulebook_fields,
            "rulebook_fields_system": rulebook_fields_system,
            "rulebook_fields_object": rulebook_fields_object,
            "has_object_rulebook_fields": has_object_rulebook_fields,
            "matching_classes": matching_classes,
        }


@register_model_view(Rulebook, name="policy_columns")
class RulebookPolicyColumnsView(generic.ObjectView):
    queryset = Rulebook.objects.all()

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return redirect(reverse("plugins:netbox_nsm:rulebook", args=[instance.pk]))

        custom_columns = []
        titles = request.POST.getlist("custom_column_title")
        bodies = request.POST.getlist("custom_column_body")
        for title, body in zip(titles, bodies):
            custom_columns.append({"title": title, "body": body})

        request.session[_policy_columns_session_key(instance.pk)] = {
            "custom_columns": _sanitize_custom_columns(custom_columns),
        }
        request.session.modified = True

        return redirect(
            reverse("plugins:netbox_nsm:rulebook_rules", args=[instance.pk])
        )


class _RulebookRulesTabMixin:
    """Bulk-delete and context for the Rules (AG Grid) tab."""

    queryset = Rulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/rulebook_policy.html"
    policy_tab_route = "rulebook_rules"
    policy_tab_key = "rules"

    def post(self, request, *args, **kwargs):
        """Handle bulk-delete of rules from the rules table."""
        instance = self.get_object(**kwargs)
        if not request.user.has_perm("netbox_nsm.delete_rule"):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden()
        pk_list = [int(pk) for pk in request.POST.getlist("pk") if pk.isdigit()]
        if pk_list:
            Rule.objects.filter(pk__in=pk_list, rulebook=instance).delete()
        return redirect(
            reverse(
                f"plugins:netbox_nsm:{self.policy_tab_route}",
                args=[instance.pk],
            )
        )

    def get_extra_context(self, request, instance):
        from netbox_nsm import policy_tab_context
        import netbox_nsm.views.rulebook as rulebook_views

        ctx = policy_tab_context.build_policy_tab_context(
            request,
            instance,
            view_helpers=rulebook_views,
            grid_all_rules=True,
        )
        ctx["policy_tab_label"] = self.tab.label
        ctx["policy_tab_key"] = self.policy_tab_key
        ctx["nsm_show_facet_panel"] = False
        return ctx


@register_model_view(Rulebook, name="rules")
class RulebookRulesGridView(_RulebookRulesTabMixin, generic.ObjectView):
    tab = ViewTab(
        label=_("Rules"),
        permission="netbox_nsm.view_rulebook",
        weight=100,
        hide_if_empty=True,
    )


@register_model_view(Rulebook, "list", path="", detail=False)
class RulebookListView(generic.ObjectListView):
    queryset = (
        Rulebook.objects.prefetch_related("assignments__assigned_object_type")
        .select_related("platform")
        .annotate(rule_count=Count("rules"))
    )
    filterset = RulebookFilterSet
    filterset_form = RulebookFilterForm
    table = RulebookTable
    template_name = "netbox_nsm/rulebook_list.html"
    actions = (AddObject, BulkDelete)


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
        return {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "leaf",
            "ip_ref": {"str": ip_ref["str"], "url": ip_ref["url"]},
            "children": [],
        }

    # IPAM object or unknown — treat as leaf
    try:
        if obj._meta.app_label == "ipam":
            return {
                "name": str(obj),
                "url": obj.get_absolute_url(),
                "kind": "leaf",
                "ip_ref": {"str": str(obj), "url": obj.get_absolute_url()},
                "children": [],
            }
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
    """Build CSV path segments for a leaf (IP as final segment when present)."""
    row = list(path_prefix)
    ip_ref = node.get("ip_ref")
    if ip_ref and ip_ref.get("str"):
        row.append(ip_ref["str"])
    else:
        row.append(node["name"])
    return row


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


def _build_addr_tree_nodes(objs):
    """Build enriched tree nodes and flat CSV path lines for a list of address objects."""
    nodes = []
    for obj in objs:
        node = _build_addr_tree_node(obj)
        if node:
            _enrich_addr_tree_copy_lines(node)
            _enrich_addr_tree_leaf_counts(node)
            nodes.append(node)
    return nodes, _flatten_addr_tree_paths(nodes)


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

    return selections, _build_multi_object_addr_analysis(objs)


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
            "nsm_policy_slots": _build_rule_edit_policy_slots(rulebook),
        }


@register_model_view(Rule, "delete")
class RuleDeleteView(generic.ObjectDeleteView):
    queryset = Rule.objects.all()


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
