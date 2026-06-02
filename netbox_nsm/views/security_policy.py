from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch
from django.utils.translation import gettext_lazy as _
from django.utils.html import escape, conditional_escape
from django.db.models import Count, Max, Q
from django.views import View
from netbox.object_actions import AddObject, BulkDelete
import json
import re

import markdown
import django_tables2 as tables

from utilities.views import ViewTab, register_model_view
from netbox.views import generic

from netbox_nsm.filtersets import (
    SecurityPolicyRuleFilterSet,
    SecurityPolicyAssignmentFilterSet,
    SecurityPolicyRulebookFilterSet,
)
from netbox_nsm.forms import (
    SecurityPolicyAssignmentFilterForm,
    SecurityPolicyAssignmentForm,
    SecurityPolicyRulebookBulkAssignForm,
    SecurityPolicyRulebookBulkEditForm,
    SecurityPolicyRulebookFilterForm,
    SecurityPolicyRulebookForm,
    SecurityPolicyRuleFilterForm,
    SecurityPolicyRuleForm,
)
from netbox_nsm.models import (
    SecurityArea,
    SecurityObjectGroup,
    NSMTypeConfig,
    SecurityPolicyRuleObjectItem,
    SecurityPolicyRuleGroupItem,
    RulebookTypeChoices,
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyAssignment,
    RulebookField,
    RulebookFieldType,
    TypeConfig,
)
from netbox_nsm.tables import (
    SecurityPolicyAssignmentTable,
    SecurityPolicyRulebookTable,
    SecurityPolicyRuleTable,
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


def _render_policy_cell(items):
    import uuid as _uuid
    if not items:
        return '<span class="text-muted small">-</span>'
    regular = [i for i in items if not i.get("is_group")]
    groups = [i for i in items if i.get("is_group")]
    out = []
    for item in regular:
        color = (item.get("color") or "").strip()
        style_attr = ""
        extra_class = ""
        if color:
            # contrast text color (luminance based)
            try:
                hex_val = color.lstrip("#")
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                text_color = "#111111" if luminance > 0.6 else "#ffffff"
            except (ValueError, IndexError):
                text_color = "#ffffff"
            style_attr = (
                f' style="background-color: {conditional_escape(color)};'
                f" border-color: {conditional_escape(color)};"
                f' color: {text_color};"'
            )
            extra_class = " nsm-rule-pill-colored"
        out.append(
            f'<a href="{conditional_escape(item["url"])}" '
            f'class="nsm-rule-pill{extra_class} text-decoration-none"'
            f"{style_attr} "
            f'title="{conditional_escape(item["name"])}">'
            f'{conditional_escape(item["name"])}'
            "</a>"
        )
    if groups:
        uid = _uuid.uuid4().hex[:8]
        pills_html = "".join(
            f'<a href="{conditional_escape(g["url"])}" '
            f'class="nsm-rule-pill text-decoration-none" '
            f'title="{conditional_escape(g["name"])}">'
            f'{conditional_escape(g["name"])}</a>'
            for g in groups
        )
        out.append(
            f'<button type="button" '
            f'class="nsm-rule-pill nsm-group-badge" '
            f'style="border:none;cursor:pointer;" '
            f"onclick=\"var d=document.getElementById('nsm-grp-{uid}');d.style.display=d.style.display==='none'?'':'none';this.classList.toggle('active');\" "
            f'title="{len(groups)} Group(s) \u2013 click to expand">'
            f'<i class="mdi mdi-account-group" style="font-size:10px;"></i> G</button>'
            f'<div id="nsm-grp-{uid}" class="nsm-group-expand" style="display:none;">'
            f'{pills_html}</div>'
        )
    return f'<div class="nsm-rule-pills">{"".join(out)}</div>'


def _build_grouped_policy_table_data(rules, selected_columns, rulebook=None):
    from netbox_nsm.display_utils import get_display_template_map, render_object_display

    rules = list(rules)
    ct_display_template_map = get_display_template_map()

    # Build ct_id → label map from TypeConfig
    ct_label_map = {}
    for tc in TypeConfig.objects.select_related("content_type"):
        mc = tc.content_type.model_class()
        if mc:
            vc = getattr(mc._meta, "verbose_name", tc.content_type.model)
            ct_label_map[tc.content_type.pk] = str(vc).capitalize()

    # Build field metadata from rulebook
    fields_by_slug = {}
    field_ct_ids_map = {}  # slug → [ct_id, ...]
    if rulebook:
        for field in rulebook.fields.prefetch_related(
            "type_configs__type_config__content_type"
        ).all():
            fields_by_slug[field.slug] = field
            field_ct_ids_map[field.slug] = [
                ft.type_config.content_type_id
                for ft in field.type_configs.all()
                if ft.type_config and ft.type_config.content_type_id
            ]

    def _slugs_for_col(col):
        if col == "source":
            return [s for s, f in fields_by_slug.items() if f.placement == "source"]
        if col == "destination":
            return [
                s for s, f in fields_by_slug.items() if f.placement == "destination"
            ]
        # Any other column: direct slug match (fixed-placement fields etc.)
        if col in fields_by_slug:
            return [col]
        return []

    # Collect used keys from items
    used_keys = set()
    for rule in rules:
        for item in rule.object_items.all():
            if item.field is None:
                continue
            used_keys.add(f"{item.field.slug}::ct_{item.content_type_id}")
        for item in rule.group_items.all():
            if item.field is None:
                continue
            used_keys.add(f"{item.field.slug}::Groups")

    header_groups = []
    grouped_columns = []
    for col in selected_columns:
        for field_slug in _slugs_for_col(col):
            field = fields_by_slug.get(field_slug)
            ct_ids = field_ct_ids_map.get(field_slug, [])
            is_fixed = field is not None and field.placement == "fixed"
            if is_fixed:
                # Fixed-placement fields (e.g. scope, action, service): always show
                # all configured TypeConfig sub-columns, even if no rules have data
                # yet. Source/destination columns are data-driven.
                types = [
                    (f"ct_{ct_id}", ct_label_map.get(ct_id, f"Type {ct_id}"))
                    for ct_id in ct_ids
                ]
            else:
                types = [
                    (f"ct_{ct_id}", ct_label_map.get(ct_id, f"Type {ct_id}"))
                    for ct_id in ct_ids
                    if f"{field_slug}::ct_{ct_id}" in used_keys
                ]
            if f"{field_slug}::Groups" in used_keys:
                types.append(("Groups", "Groups"))
            # For fixed fields with no TypeConfigs at all, show a placeholder column
            if not types and is_fixed:
                types = [("_empty", "—")]
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

            header_groups.append(
                {
                    "label": re.sub(r'\s*\(.*?\)\s*$', '', field.name).strip() if field else field_slug.capitalize(),
                    "columns": cols,
                }
            )

    for group_idx, group in enumerate(header_groups):
        for idx, col in enumerate(group["columns"]):
            col["is_group_start"] = idx == 0
            col["is_group_end"] = idx == len(group["columns"]) - 1
            col["group_band"] = "odd" if (group_idx % 2) else "even"

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
                    "is_group": True,
                }
            )

        cells = {}
        for k, v in per_key.items():
            cells[k] = _render_policy_cell(v)

        rows.append(
            {
                "pk": rule.pk,
                "index": rule.index,
                "enabled": rule.enabled,
                "name": rule.name,
                "url": rule.get_absolute_url(),
                "description": rule.description or "-",
                "edit_url": f"/plugins/netbox-nsm/security-rule/{rule.pk}/edit/",
                "delete_url": f"/plugins/netbox-nsm/security-rule/{rule.pk}/delete/",
                "cells": cells,
            }
        )

    return {
        "header_groups": header_groups,
        "column_count": len(grouped_columns),
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

MAX_CUSTOM_COLUMNS = 10


def _get_api_url_for_content_type(ct):
    """Resolve the REST API list URL for a ContentType, or return None."""
    import re as _re

    app = ct.app_label
    model = ct.model

    # netbox_custom_objects uses dynamic table models named "table{pk}model"
    # The API URL is /api/plugins/custom-objects/{slug}/
    if app == "netbox_custom_objects":
        m = _re.match(r"^table(\d+)model$", model)
        if m:
            try:
                from netbox_custom_objects.models import CustomObjectType

                cot = CustomObjectType.objects.get(pk=int(m.group(1)))
                return f"/api/plugins/custom-objects/{cot.slug}/"
            except Exception:
                pass
        return None

    # Built-in NetBox apps (dcim, ipam, virtualization, …)
    try:
        return reverse(f"{app}-api:{model}-list")
    except NoReverseMatch:
        pass
    # Plugin apps nested under plugins-api
    try:
        return reverse(f"plugins-api:{app}-api:{model}-list")
    except NoReverseMatch:
        pass
    return None


def _build_security_rule_picker_data(rulebook=None):
    """
    Build minimal picker metadata for the rule editor.
    Uses RulebookField/RulebookFieldType/TypeConfig instead of the legacy SecurityArea model.
    """
    fields = {}

    fields_qs = (
        RulebookField.objects.filter(rulebook=rulebook)
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
            "types": [],
        }

    if rulebook:
        for ftype in (
            RulebookFieldType.objects.filter(field__rulebook=rulebook)
            .select_related("field", "type_config__content_type")
            .order_by("sort_order", "type_config__content_type__model")
        ):
            field_data = fields.get(ftype.field.slug)
            if not field_data:
                continue
            tc = ftype.type_config
            model_class = tc.content_type.model_class()
            if not model_class:
                continue
            api_url = _get_api_url_for_content_type(tc.content_type)
            if not api_url:
                continue
            label = str(model_class._meta.verbose_name_plural).title()
            field_data["types"].append(
                {
                    "name": label,
                    "ct_id": tc.content_type.pk,
                    "api_url": api_url,
                    "kind": "object",
                    "allow_virtual_groups": False,
                    "matching_class": tc.matching_class or "",
                }
            )

    # Groups: static list per field slug (keyed by SecurityArea slug for legacy compat)
    groups_by_slug = {}
    for group in SecurityObjectGroup.objects.prefetch_related("areas").order_by("name"):
        for area in group.areas.all():
            groups_by_slug.setdefault(str(area.slug), []).append(
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
            "types": d["types"],
        }
        for _, d in sorted(
            fields.items(),
            key=lambda pair: (pair[1]["sort_order"], pair[1]["name"].lower(), pair[0]),
        )
        if d["types"]
    ]
    return {"areas": ordered_areas}


def _available_policy_columns(rulebook=None):
    if rulebook is None:
        # Legacy fallback (no rulebook context)
        result = {
            "source": RulebookField.objects.filter(placement="source").exists(),
            "destination": RulebookField.objects.filter(placement="destination").exists(),
        }
        for slug in ("service", "action", "info"):
            result[slug] = RulebookField.objects.filter(slug=slug).exists()
        return result
    result = {
        "source": rulebook.fields.filter(placement="source").exists(),
        "destination": rulebook.fields.filter(placement="destination").exists(),
    }
    for field in rulebook.fields.filter(placement="fixed"):
        result[field.slug] = True
    return result


def _dynamic_policy_columns(rulebook):
    """Build the (name, label) column list dynamically from a rulebook's fields."""
    cols = [
        ("index", _("Index")),
        ("status", _("Status")),
        ("name", _("Name")),
    ]
    has_source = has_dest = False
    for field in rulebook.fields.order_by("sort_order", "slug"):
        if field.placement == "source" and not has_source:
            cols.append(("source", _("Source")))
            has_source = True
        elif field.placement == "destination" and not has_dest:
            cols.append(("destination", _("Destination")))
            has_dest = True
        elif field.placement == "fixed":
            cols.append((field.slug, field.name))
    cols.append(("description", _("Description")))
    return cols


def _filter_policy_columns(columns, availability):
    """Remove columns that are known to be unavailable."""
    return [col for col in columns if availability.get(col, True)]


def _policy_columns_session_key(rulebook_pk):
    return f"netbox_nsm_policy_columns_{rulebook_pk}"


def _default_security_rules_columns(rulebook=None):
    if rulebook is not None:
        return [name for name, _ in _dynamic_policy_columns(rulebook)]
    return [
        column
        for column in SecurityPolicyRuleTable.Meta.default_columns
        if column in {name for name, _ in SECURITY_RULES_COLUMNS}
    ]


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


def _get_policy_table_config(request, rulebook_pk, rulebook=None):
    if rulebook is not None:
        dynamic_cols = _dynamic_policy_columns(rulebook)
        allowed_columns = [name for name, _ in dynamic_cols]
    else:
        allowed_columns = [name for name, _ in SECURITY_RULES_COLUMNS]
    allowed_set = set(allowed_columns)
    default_columns = _default_security_rules_columns(rulebook)

    config = request.session.get(_policy_columns_session_key(rulebook_pk), {})
    stored_columns = config.get("selected_columns")

    if stored_columns:
        # Keep stored selection but add any new default columns not yet in the session,
        # inserting them at the correct position based on default_columns order.
        selected_columns = [c for c in stored_columns if c in allowed_set]
        stored_set = set(selected_columns)
        for i, col in enumerate(default_columns):
            if col not in stored_set:
                # Find insertion point: insert after the last preceding default column
                # that is already in selected_columns
                insert_after = None
                for prev_col in reversed(default_columns[:i]):
                    if prev_col in stored_set:
                        insert_after = prev_col
                        break
                if insert_after is not None:
                    pos = selected_columns.index(insert_after) + 1
                    selected_columns.insert(pos, col)
                else:
                    selected_columns.insert(0, col)
                stored_set.add(col)
    else:
        selected_columns = default_columns

    if not selected_columns:
        selected_columns = default_columns

    column_order = config.get("column_order") or selected_columns
    ordered_selected = []
    for column in column_order:
        if column in selected_columns and column not in ordered_selected:
            ordered_selected.append(column)
    for column in selected_columns:
        if column not in ordered_selected:
            ordered_selected.append(column)

    custom_columns = _sanitize_custom_columns(config.get("custom_columns") or [])

    return {
        "selected_columns": ordered_selected,
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
        column
        for column in SecurityPolicyRuleTable.Meta.default_columns
        if column in allowed_columns
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
        (SecurityPolicyRuleTable.Meta,),
        {
            "model": SecurityPolicyRule,
            "fields": tuple(SecurityPolicyRuleTable.Meta.fields) + tuple(custom_keys),
            "default_columns": tuple(selected_columns) + tuple(custom_keys),
        },
    )
    return type("ConfiguredSecurityPolicyRuleTable", (SecurityPolicyRuleTable,), attrs)


def _build_object_analysis(rulebook):
    """Count per-area object usage across all rules in a rulebook."""
    from collections import Counter
    from netbox_nsm.models import (
        SecurityPolicyRuleObjectItem,
        SecurityPolicyRuleGroupItem,
    )

    rule_pks = list(
        SecurityPolicyRule.objects.filter(rulebook=rulebook).values_list(
            "pk", flat=True
        )
    )
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
            SecurityPolicyRuleObjectItem.objects.filter(rule__in=rule_pks, field=area)
            .select_related("content_type", "rule")
            .order_by("rule_id")
        )
        grp_items = (
            SecurityPolicyRuleGroupItem.objects.filter(rule__in=rule_pks, field=area)
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
        SecurityPolicyRuleObjectItem,
        SecurityPolicyRuleGroupItem,
    )

    rule_pks = list(
        SecurityPolicyRule.objects.filter(rulebook=rulebook).values_list(
            "pk", flat=True
        )
    )

    object_counter = Counter()
    for item in SecurityPolicyRuleObjectItem.objects.filter(
        rule__in=rule_pks
    ).select_related("content_type"):
        assigned = item.assigned_object
        name = str(
            getattr(assigned, "name", None) or item.object_id
            if assigned
            else item.object_id
        )
        type_label = str(item.content_type.model) if item.content_type_id else "object"
        object_counter[(item.object_id, name, type_label)] += 1

    group_counter = Counter()
    for item in SecurityPolicyRuleGroupItem.objects.filter(
        rule__in=rule_pks
    ).select_related("security_group"):
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
    "SecurityPolicyRulebookView",
    "SecurityPolicyRulebookListView",
    "SecurityPolicyRulebookEditView",
    "SecurityPolicyRulebookDeleteView",
    "SecurityPolicyRulebookBulkEditView",
    "SecurityPolicyRulebookBulkDeleteView",
    "SecurityPolicyRulebookPolicyColumnsView",
    "SecurityPolicyRulebookRulesView",
    "SecurityPolicyRulebookVisualizationView",
    "SecurityPolicyRulebookBulkAssignView",
    "SecurityPolicyRuleView",
    "SecurityPolicyRuleListView",
    "SecurityPolicyRuleEditView",
    "SecurityPolicyRuleDeleteView",
    "SecurityPolicyAssignmentListView",
    "SecurityPolicyAssignmentEditView",
    "SecurityPolicyAssignmentDeleteView",
    "SecurityPolicyAssignmentBulkDeleteView",
    "GlobalRulesSearchView",
)


ZONE_TYPE_NAME = "Zones"
_NONE_ZONE_PK = 0


def _make_none_zone():
    from types import SimpleNamespace

    return SimpleNamespace(pk=_NONE_ZONE_PK, name="(none)")


@register_model_view(SecurityPolicyRulebook, name="analysis", path="analysis")
class SecurityPolicyRulebookAnalysisView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()
    template_name = "netbox_nsm/securitypolicyrulebook_analysis.html"
    tab = ViewTab(
        label=_("Policy Analysis"),
        permission="netbox_nsm.view_securitypolicyrulebook",
        weight=200,
    )

    def get_extra_context(self, request, instance):
        return {
            "object_analysis": _build_object_analysis(instance),
        }


def _load_rules_qs(instance):
    """Shared helper: load all rules with needed prefetches."""
    return list(
        SecurityPolicyRule.objects.filter(rulebook=instance)
        .prefetch_related(
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
        )
        .order_by("index")
    )


@register_model_view(SecurityPolicyRulebook, name="visualization", path="zonematrix")
class SecurityPolicyRulebookVisualizationView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()
    template_name = "netbox_nsm/securitypolicyrulebook_matrix.html"
    tab = ViewTab(
        label=_("Zone Matrix"),
        permission="netbox_nsm.view_securitypolicyrulebook",
        weight=300,
    )

    def get_extra_context(self, request, instance):
        from collections import defaultdict
        from django.contrib.contenttypes.models import ContentType

        # Load all action objects once for color lookup & legend
        try:
            _action_area = SecurityArea.objects.get(slug="action")
            _action_ct_ids = list(
                NSMTypeConfig.objects.filter(areas=_action_area).values_list(
                    "content_type_id", flat=True
                )
            )
            _action_objs = {}
            for _ct_id in _action_ct_ids:
                try:
                    _ct = ContentType.objects.get(pk=_ct_id)
                    _mc = _ct.model_class()
                    if _mc:
                        for _obj in _mc.objects.all():
                            _action_objs[_obj.pk] = _obj
                except Exception:
                    pass
        except Exception:
            _action_objs = {}

        action_legend = sorted(
            [
                {"name": o.name, "color": getattr(o, "color", "#888888")}
                for o in _action_objs.values()
            ],
            key=lambda x: x["name"],
        )

        rules_qs = _load_rules_qs(instance)

        policy_url_base = reverse(
            "plugins:netbox_nsm:securitypolicyrulebook_policy",
            args=[instance.pk],
        )
        add_url_base = reverse("plugins:netbox_nsm:securitypolicyrule_add")

        # ── Collect available object types ──
        # Only types from source/destination fields of THIS rulebook
        available_ct_ids = list(
            RulebookFieldType.objects.filter(
                field__rulebook=instance,
                field__placement__in=["source", "destination"],
            )
            .values_list("type_config__content_type_id", flat=True)
            .distinct()
        )
        available_types = []
        for ct_id in available_ct_ids:
            try:
                ct = ContentType.objects.get(pk=ct_id)
                mc = ct.model_class()
                if mc is None:
                    continue
                label = str(
                    getattr(mc._meta, "verbose_name_plural", ct.model)
                ).capitalize()
                available_types.append({"ct_id": ct_id, "label": label})
            except ContentType.DoesNotExist:
                continue
        available_types.sort(key=lambda x: x["label"])

        sel_ct_id_str = request.GET.get("obj_type", "")
        selected_ct_id = int(sel_ct_id_str) if sel_ct_id_str.isdigit() else None
        if selected_ct_id is None and available_types:
            selected_ct_id = available_types[0]["ct_id"]

        used_zones_by_pk = {}
        if selected_ct_id is not None:
            try:
                selected_ct = ContentType.objects.get(pk=selected_ct_id)
            except ContentType.DoesNotExist:
                selected_ct = None
            if selected_ct:
                for rule in rules_qs:
                    for item in rule.object_items.all():
                        if item.content_type_id != selected_ct_id:
                            continue
                        obj = item.assigned_object
                        if obj is None:
                            continue
                        used_zones_by_pk[obj.pk] = obj

        all_zones = sorted(
            used_zones_by_pk.values(), key=lambda z: getattr(z, "name", str(z)).lower()
        )
        all_src_zones = all_zones
        all_dst_zones = all_zones

        src_filter_pks = {int(v) for v in request.GET.getlist("src_id") if v.isdigit()}
        dst_filter_pks = {int(v) for v in request.GET.getlist("dst_id") if v.isdigit()}
        src_zones = (
            [z for z in all_src_zones if z.pk in src_filter_pks]
            if src_filter_pks
            else all_src_zones
        )
        dst_zones = (
            [z for z in all_dst_zones if z.pk in dst_filter_pks]
            if dst_filter_pks
            else all_dst_zones
        )

        # Field names for NSM query links
        _src_fields = list(instance.fields.filter(placement="source").order_by("sort_order"))
        _dst_fields = list(instance.fields.filter(placement="destination").order_by("sort_order"))
        _src_fname = _src_fields[0].slug if _src_fields else "source"
        _dst_fname = _dst_fields[0].slug if _dst_fields else "destination"

        def _action_color_label(rule):
            for item in rule.object_items.all():
                if not item.field or item.field.slug != "action":
                    continue
                assigned = item.assigned_object
                if assigned is None:
                    continue
                return getattr(assigned, "color", None) or "#888888", getattr(
                    assigned, "name", str(assigned)
                )
            return "#888888", "?"

        cell_map = defaultdict(list)
        if selected_ct_id is not None:
            for rule in rules_qs:
                rule._color, rule._action_label = _action_color_label(rule)
                rule_src_pks = set()
                rule_dst_pks = set()
                for item in rule.object_items.all():
                    if item.content_type_id != selected_ct_id:
                        continue
                    obj = item.assigned_object
                    if obj is None:
                        continue
                    if item.field and item.field.placement == "source":
                        rule_src_pks.add(obj.pk)
                    elif item.field and item.field.placement == "destination":
                        rule_dst_pks.add(obj.pk)
                for sp in rule_src_pks or {None}:
                    for dp in rule_dst_pks or {None}:
                        if sp is not None and dp is not None:
                            cell_map[(sp, dp)].append(rule)

        def _badge(rules_list):
            if not rules_list:
                return {"count": 0, "color": None, "label": None}
            if len(rules_list) == 1:
                r = rules_list[0]
                return {"count": 1, "color": r._color, "label": r._action_label}
            return {"count": len(rules_list), "color": None, "label": None}

        def _combined_badge(fwd_rules, rev_rules):
            """Merge fwd + rev (dedup by pk) into a single badge for undirected mode."""
            seen = set()
            merged = []
            for r in fwd_rules + rev_rules:
                if r.pk not in seen:
                    seen.add(r.pk)
                    merged.append(r)
            return _badge(merged)

        matrix_mode = request.GET.get("mode", "directed")
        if matrix_mode not in ("undirected", "directed"):
            matrix_mode = "directed"

        from urllib.parse import quote as _urlquote

        def _nsm_href(src_name, dst_name):
            q = f'{_src_fname} == "{src_name}" AND {_dst_fname} == "{dst_name}"'
            return f"{policy_url_base}?nsm_q={_urlquote(q)}"

        def _nsm_href_bidir(sn, dn):
            q = f'{_src_fname} == "{sn}" AND {_dst_fname} == "{dn}" OR {_src_fname} == "{dn}" AND {_dst_fname} == "{sn}"'
            return f"{policy_url_base}?nsm_q={_urlquote(q)}"

        matrix_rows = []
        for src in src_zones:
            cells = []
            for dst in dst_zones:
                fwd_rules = cell_map.get((src.pk, dst.pk), [])
                rev_rules = cell_map.get((dst.pk, src.pk), [])
                sn = getattr(src, "name", str(src))
                dn = getattr(dst, "name", str(dst))
                cells.append(
                    {
                        "fwd": _badge(fwd_rules),
                        "rev": _badge(rev_rules),
                        "combined": _combined_badge(fwd_rules, rev_rules),
                        "fwd_href": _nsm_href(sn, dn),
                        "rev_href": _nsm_href(dn, sn),
                        "both_href": _nsm_href_bidir(sn, dn),
                        "add_href": (
                            f"{add_url_base}?rulebook={instance.pk}"
                            f"&prefill_src_ct={selected_ct_id}&prefill_src_obj={src.pk}"
                            f"&prefill_dst_ct={selected_ct_id}&prefill_dst_obj={dst.pk}"
                            f"&return_url={policy_url_base}"
                        ),
                        "is_self": src.pk == dst.pk,
                    }
                )
            matrix_rows.append({"source_zone": src, "cells": cells})

        return {
            "available_types": available_types,
            "selected_ct_id": selected_ct_id,
            "all_src_zones": all_src_zones,
            "all_dst_zones": all_dst_zones,
            "src_zones": src_zones,
            "dst_zones": dst_zones,
            "src_filter_pks": src_filter_pks,
            "dst_filter_pks": dst_filter_pks,
            "matrix_rows": matrix_rows,
            "action_legend": action_legend,
            "matrix_mode": matrix_mode,
        }


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


@register_model_view(SecurityPolicyRulebook, name="ipanalysis", path="ipanalysis")
class SecurityPolicyRulebookIPAnalysisView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()
    template_name = "netbox_nsm/securitypolicyrulebook_ipanalysis.html"
    tab = ViewTab(
        label=_("IP Analysis"),
        permission="netbox_nsm.view_securitypolicyrulebook",
        weight=400,
    )

    def get_extra_context(self, request, instance):
        from django.contrib.contenttypes.models import ContentType as _CT

        # Build searchable types from ALL NSMTypeConfig entries (deduplicated by ct_id)
        seen_ct_ids = set()
        ip_api_types = []
        for tc in NSMTypeConfig.objects.select_related("content_type").order_by(
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

        def _resolve(ct_str, pk_str, name_hint):
            if not (ct_str.isdigit() and pk_str.isdigit()):
                return name_hint, [], None
            try:
                ct = _CT.objects.get(pk=int(ct_str))
                mc = ct.model_class()
                if mc:
                    obj = mc.objects.filter(pk=int(pk_str)).first()
                    if obj:
                        name = getattr(obj, "name", None) or name_hint or str(obj)
                        seen_keys = set()
                        refs = []
                        for r in _extract_ip_refs(obj):
                            key = r.get("display", "") or r.get("str", "")
                            if key and key not in seen_keys:
                                seen_keys.add(key)
                                refs.append(r)
                        tree = _build_addr_tree_node(obj)
                        return name, refs, tree
            except Exception:
                pass
            return name_hint, [], None

        # Left column
        ip_sel_ct = request.GET.get("ip_ct", "")
        ip_sel_pk = request.GET.get("ip_pk", "")
        ip_sel_name = request.GET.get("ip_name", "")
        ip_selected_name, ip_refs, ip_tree_node = _resolve(
            ip_sel_ct, ip_sel_pk, ip_sel_name
        )

        # Right column
        ip2_sel_ct = request.GET.get("ip2_ct", "")
        ip2_sel_pk = request.GET.get("ip2_pk", "")
        ip2_sel_name = request.GET.get("ip2_name", "")
        ip2_selected_name, ip2_refs, ip2_tree_node = _resolve(
            ip2_sel_ct, ip2_sel_pk, ip2_sel_name
        )

        return {
            "ip_api_types": ip_api_types,
            # left
            "ip_sel_ct": ip_sel_ct,
            "ip_sel_pk": ip_sel_pk,
            "ip_sel_name": ip_sel_name,
            "ip_selected_name": ip_selected_name,
            "ip_refs": ip_refs,
            "ip_tree_node": ip_tree_node,
            # right
            "ip2_sel_ct": ip2_sel_ct,
            "ip2_sel_pk": ip2_sel_pk,
            "ip2_sel_name": ip2_sel_name,
            "ip2_selected_name": ip2_selected_name,
            "ip2_refs": ip2_refs,
            "ip2_tree_node": ip2_tree_node,
        }

    # ─── end of SecurityPolicyRulebookIPAnalysisView ───────────────────────


@register_model_view(SecurityPolicyRulebook)
class SecurityPolicyRulebookView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.prefetch_related(
        "assignments__assigned_object_type",
    ).all()

    def get_extra_context(self, request, instance):
        # Assigned objects
        assignments = list(
            instance.assignments.select_related("assigned_object_type").all()
        )

        # Fields + Matching Strategy (always available)
        from netbox_nsm.models import RulebookField

        rulebook_fields = list(
            RulebookField.objects.filter(rulebook=instance)
            .prefetch_related("type_configs__type_config")
            .order_by("sort_order", "slug")
        )
        matching_classes = sorted(instance.matching_classes)

        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return {
                "assignments": assignments,
                "rulebook_fields": rulebook_fields,
                "matching_classes": matching_classes,
            }

        availability = _available_policy_columns(instance)
        config = _get_policy_table_config(request, instance.pk, rulebook=instance)
        selected_columns = _filter_policy_columns(
            config["selected_columns"], availability
        )
        selected_set = set(selected_columns)
        order_map = {name: idx + 1 for idx, name in enumerate(selected_columns)}

        return {
            "assignments": assignments,
            "security_rules_columns": _dynamic_policy_columns(instance),
            "selected_security_rules_columns": selected_columns,
            "selected_security_rules_columns_set": selected_set,
            "security_rules_column_order": order_map,
            "security_rules_column_order_list": selected_columns,
            "custom_columns": config["custom_columns"],
            "nsm_available_policy_areas": availability,
            "rulebook_fields": rulebook_fields,
            "matching_classes": matching_classes,
        }


@register_model_view(SecurityPolicyRulebook, name="policy_columns")
class SecurityPolicyRulebookPolicyColumnsView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return redirect(
                reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[instance.pk])
            )

        availability = _available_policy_columns(instance)
        allowed_columns = {name for name, _ in _dynamic_policy_columns(instance)}
        selected_columns = [
            column
            for column in request.POST.getlist("columns")
            if column in allowed_columns
        ]
        selected_columns = _filter_policy_columns(selected_columns, availability)

        if not selected_columns:
            selected_columns = _filter_policy_columns(
                _default_security_rules_columns(instance), availability
            )

        ordered_columns = []
        raw_order = request.POST.get("column_order", "")
        for column in [item.strip() for item in raw_order.split(",") if item.strip()]:
            if column in selected_columns and column not in ordered_columns:
                ordered_columns.append(column)
        for column in selected_columns:
            if column not in ordered_columns:
                ordered_columns.append(column)

        custom_columns = []
        titles = request.POST.getlist("custom_column_title")
        bodies = request.POST.getlist("custom_column_body")
        for title, body in zip(titles, bodies):
            custom_columns.append({"title": title, "body": body})

        request.session[_policy_columns_session_key(instance.pk)] = {
            "selected_columns": ordered_columns,
            "column_order": ordered_columns,
            "custom_columns": _sanitize_custom_columns(custom_columns),
        }
        request.session.modified = True

        return redirect(
            reverse(
                "plugins:netbox_nsm:securitypolicyrulebook_policy", args=[instance.pk]
            )
        )


@register_model_view(SecurityPolicyRulebook, name="policy")
class SecurityPolicyRulebookRulesView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/securitypolicyrulebook_security_policy.html"
    tab = ViewTab(
        label=_("Policy"),
        permission="netbox_nsm.view_securitypolicyrulebook",
        weight=100,
    )

    def post(self, request, *args, **kwargs):
        """Handle bulk-delete of rules from the inline policy table."""
        instance = self.get_object(**kwargs)
        if not request.user.has_perm("netbox_nsm.delete_securitypolicyrule"):
            from django.http import HttpResponseForbidden

            return HttpResponseForbidden()
        pk_list = [int(pk) for pk in request.POST.getlist("pk") if pk.isdigit()]
        if pk_list:
            SecurityPolicyRule.objects.filter(
                pk__in=pk_list, rulebook=instance
            ).delete()
        return redirect(
            reverse(
                "plugins:netbox_nsm:securitypolicyrulebook_policy", args=[instance.pk]
            )
        )

    def get_extra_context(self, request, instance):
        from django.core.paginator import Paginator
        from netbox_nsm.query import (
            parse,
            RulebookContext,
            filter_rules,
            compute_facets,
        )
        from netbox_nsm.query.engine import prepare_rules

        availability = _available_policy_columns(instance)
        base_rules_qs = (
            SecurityPolicyRule.objects.filter(rulebook=instance)
            .prefetch_related(
                "source_users",
                "destination_users",
                "object_items__field",
                "object_items__content_type",
                "group_items__field",
                "group_items__security_group",
            )
            .order_by("index")
        )

        # ── NSM Query Engine ──────────────────────────────────────────────────
        nsm_q_raw = request.GET.get("nsm_q", "").strip()
        query = parse(nsm_q_raw)
        context = RulebookContext(instance)

        # Load all rules into Python (enables in-memory filtering + facets)
        all_rules = prepare_rules(base_rules_qs)

        # Filter via query engine
        filtered_rules = filter_rules(all_rules, query, context)

        # Compute facets: entries from all_rules, counts from filtered_rules
        facets = compute_facets(all_rules, context, filtered_rules=filtered_rules)

        # Mark entries that are already active in the current query (avoid duplicates)
        _nsm_q_lower = nsm_q_raw.lower()
        for facet in facets:
            for grp_list in (facet.get("entries_value", []), facet.get("entries_set", [])):
                for grp_block in grp_list:
                    for entry in grp_block.get("entries", []):
                        entry["already_active"] = entry["qval"].lower() in _nsm_q_lower


        # ── Column config ─────────────────────────────────────────────────────
        config = _get_policy_table_config(request, instance.pk, rulebook=instance)
        selected_columns = _filter_policy_columns(
            config["selected_columns"], availability
        )
        custom_columns = config["custom_columns"]

        all_columns = [name for name, _ in SECURITY_RULES_COLUMNS]
        # Dynamic fixed-placement fields (e.g. "scope") are displayed via the grouped
        # table data, not as django-tables2 columns. Filter them out for the table instance.
        known_table_fields = set(SecurityPolicyRuleTable.Meta.fields)
        table_selected_columns = [c for c in selected_columns if c in known_table_fields]
        excluded_columns = [
            name for name in all_columns if name not in set(table_selected_columns)
        ]
        custom_keys = [
            f"custom_column_{idx}" for idx in range(1, len(custom_columns) + 1)
        ]

        # ── Pagination (over Python list) ─────────────────────────────────────
        VALID_PER_PAGE = [25, 50, 100, 250, 500, 1000]
        try:
            per_page = int(request.GET.get("per_page", 100))
            if per_page not in VALID_PER_PAGE:
                per_page = 100
        except (ValueError, TypeError):
            per_page = 100

        total_count = len(filtered_rules)
        paginator = Paginator(filtered_rules, per_page)
        try:
            page_num = int(request.GET.get("page", 1))
        except (ValueError, TypeError):
            page_num = 1
        page_num = max(1, min(page_num, paginator.num_pages or 1))
        page_obj = paginator.get_page(page_num)
        paged_rules = list(page_obj.object_list)

        # Build query string without 'page' for pagination links
        get_params = request.GET.copy()
        get_params.pop("page", None)
        base_qs_str = get_params.urlencode()

        # ── Build table ───────────────────────────────────────────────────────
        # The policy table expects a queryset; convert paged rules to a QS via pk list
        paged_pks = [r.pk for r in paged_rules]
        paged_qs = SecurityPolicyRule.objects.filter(pk__in=paged_pks).prefetch_related(
            "source_users",
            "destination_users",
            "object_items__field",
            "object_items__content_type",
            "group_items__field",
            "group_items__security_group",
        )
        # Re-attach cached items for grouped table builder
        paged_qs_list = list(paged_qs)
        cached_map = {r.pk: r for r in paged_rules}
        for rule in paged_qs_list:
            src = cached_map.get(rule.pk)
            if src:
                rule._cached_object_items = src._cached_object_items
                rule._cached_group_items = src._cached_group_items
        # Preserve sort order
        paged_qs_ordered = sorted(paged_qs_list, key=lambda r: paged_pks.index(r.pk))

        policy_table_class = _build_policy_table_class(custom_columns, table_selected_columns)
        policy_table = policy_table_class(
            paged_qs_ordered,
            orderable=False,
            exclude=excluded_columns,
            sequence=("pk",) + tuple(table_selected_columns + custom_keys + ["..."]),
        )
        policy_table.configure(request)

        grouped = _build_grouped_policy_table_data(
            paged_qs_ordered, selected_columns, rulebook=instance
        )

        return {
            "table": policy_table,
            "is_security_rules": True,
            "security_rules_columns": SECURITY_RULES_COLUMNS,
            "selected_security_rules_columns": selected_columns,
            "nsm_available_policy_areas": availability,
            # NSM Query Engine
            "nsm_q": nsm_q_raw,
            "nsm_query": query,
            "nsm_query_error": query.parse_error,
            "nsm_facets": facets,
            "policy_header_groups": grouped["header_groups"],
            "policy_grouped_column_count": grouped["column_count"],
            "policy_grouped_rows": grouped["rows"],
            # pagination
            "page_obj": page_obj,
            "paginator": paginator,
            "per_page": per_page,
            "valid_per_page": VALID_PER_PAGE,
            "total_count": total_count,
            "base_qs_str": base_qs_str,
        }


@register_model_view(SecurityPolicyRulebook, "list", path="", detail=False)
class SecurityPolicyRulebookListView(generic.ObjectListView):
    queryset = SecurityPolicyRulebook.objects.prefetch_related(
        "assignments__assigned_object_type"
    ).annotate(rule_count=Count("rules")).all()
    filterset = SecurityPolicyRulebookFilterSet
    filterset_form = SecurityPolicyRulebookFilterForm
    table = SecurityPolicyRulebookTable
    template_name = "netbox_nsm/securitypolicyrulebook_list.html"
    actions = (AddObject, BulkDelete)


@register_model_view(SecurityPolicyRulebook, "add", detail=False)
@register_model_view(SecurityPolicyRulebook, "edit")
class SecurityPolicyRulebookEditView(generic.ObjectEditView):
    queryset = SecurityPolicyRulebook.objects.all()
    form = SecurityPolicyRulebookForm


@register_model_view(SecurityPolicyRulebook, "delete")
class SecurityPolicyRulebookDeleteView(generic.ObjectDeleteView):
    queryset = SecurityPolicyRulebook.objects.all()


@register_model_view(SecurityPolicyRulebook, "bulk_edit", path="edit", detail=False)
class SecurityPolicyRulebookBulkEditView(generic.BulkEditView):
    queryset = SecurityPolicyRulebook.objects.all()
    filterset = SecurityPolicyRulebookFilterSet
    table = SecurityPolicyRulebookTable
    form = SecurityPolicyRulebookBulkEditForm


@register_model_view(SecurityPolicyRulebook, "bulk_delete", path="delete", detail=False)
class SecurityPolicyRulebookBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityPolicyRulebook.objects.all()
    table = SecurityPolicyRulebookTable


def _extract_ip_refs(obj):
    """Return list of {display, url, type} for IP-relevant objects reachable from obj."""
    return _extract_ip_refs_visited(obj, set())


_FIELD_TYPE_LABELS = {
    "prefix": "Prefix",
    "ip_address": "IP Address",
    "range": "Range",
}


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

    address_type = getattr(obj, "address_type", None)
    if address_type == "address-group":
        try:
            for member in obj.address_group.all():
                if member.pk not in visited:
                    visited.add(member.pk)
                    refs.extend(_extract_ip_refs_visited(member, visited))
        except Exception:
            pass
        return refs

    for field_name in ("prefix", "ip_address", "range"):
        try:
            related = getattr(obj, field_name, None)
            if related is not None:
                refs.append(
                    {
                        "display": str(related),
                        "url": related.get_absolute_url(),
                        "type": _FIELD_TYPE_LABELS.get(field_name, field_name),
                    }
                )
        except Exception:
            pass

    return refs


def _collect_ips_from_group(group, visited=None):
    """Recursively resolve IPs from SecurityObjectGroup sub_groups."""
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

    address_type = getattr(obj, "address_type", None)

    if address_type == "address-group":
        children = []
        try:
            for sub in obj.address_group.all():
                child = _build_addr_tree_node(sub, visited)
                if child:
                    children.append(child)
        except Exception:
            pass
        return {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "group",
            "ip_ref": None,
            "children": children,
        }

    if address_type in ("ip-prefix", "ip-address", "ip-range"):
        ip_ref = None
        try:
            if address_type == "ip-prefix":
                p = obj.prefix
                if p:
                    ip_ref = {"str": str(p), "url": p.get_absolute_url()}
            elif address_type == "ip-address":
                ip = obj.ip_address
                if ip:
                    ip_ref = {"str": str(ip), "url": ip.get_absolute_url()}
            elif address_type == "ip-range":
                r = obj.range
                if r:
                    ip_ref = {"str": str(r), "url": r.get_absolute_url()}
        except Exception:
            pass
        return {
            "name": str(obj.name),
            "url": obj.get_absolute_url(),
            "kind": "leaf",
            "ip_ref": ip_ref,
            "children": [],
        }

    # IPAM object or unknown — treat as leaf
    ip_ref = None
    try:
        if obj._meta.app_label == "ipam":
            ip_ref = {"str": str(obj), "url": obj.get_absolute_url()}
    except Exception:
        pass
    return {
        "name": str(obj),
        "url": getattr(obj, "get_absolute_url", lambda: "#")(),
        "kind": "leaf",
        "ip_ref": ip_ref,
        "children": [],
    }


@register_model_view(SecurityPolicyRule)
class SecurityPolicyRuleView(generic.ObjectView):
    queryset = SecurityPolicyRule.objects.prefetch_related(
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

        src_ips = []
        src_addr_nodes = []
        for item in src_items:
            assigned = item.assigned_object
            if assigned:
                src_ips.extend(_extract_ip_refs(assigned))
                node = _build_addr_tree_node(assigned)
                if node:
                    src_addr_nodes.append(node)

        dst_ips = []
        dst_addr_nodes = []
        for item in dst_items:
            assigned = item.assigned_object
            if assigned:
                dst_ips.extend(_extract_ip_refs(assigned))
                node = _build_addr_tree_node(assigned)
                if node:
                    dst_addr_nodes.append(node)

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
            "src_ips": src_ips,
            "dst_ips": dst_ips,
            "src_addr_nodes": src_addr_nodes,
            "dst_addr_nodes": dst_addr_nodes,
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


@register_model_view(SecurityPolicyRule, "list", path="", detail=False)
class SecurityPolicyRuleListView(generic.ObjectListView):
    queryset = SecurityPolicyRule.objects.select_related("rulebook")
    filterset = SecurityPolicyRuleFilterSet
    filterset_form = SecurityPolicyRuleFilterForm
    table = SecurityPolicyRuleTable


@register_model_view(SecurityPolicyRule, "add", detail=False)
@register_model_view(SecurityPolicyRule, "edit")
class SecurityPolicyRuleEditView(generic.ObjectEditView):
    queryset = SecurityPolicyRule.objects.all()
    form = SecurityPolicyRuleForm
    template_name = "netbox_nsm/securitypolicyrule_edit.html"

    def alter_object(self, instance, request, args, kwargs):
        """Pre-fill index and comments from rulebook template when creating a new rule."""
        if not instance.pk:
            rulebook_pk = request.GET.get("rulebook")
            if rulebook_pk and str(rulebook_pk).isdigit():
                try:
                    rulebook = SecurityPolicyRulebook.objects.get(pk=int(rulebook_pk))
                    result = SecurityPolicyRule.objects.filter(
                        rulebook_id=rulebook.pk
                    ).aggregate(max_index=Max("index"))
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
                except SecurityPolicyRulebook.DoesNotExist:
                    pass
        return instance

    def get_extra_context(self, request, instance):
        from netbox_nsm.display_utils import ct_display_label

        # Build current selections JSON for pre-populating the picker on edit
        selections = []
        if instance.pk:
            # Build a ct_id → matching_class lookup from TypeConfig
            from netbox_nsm.models import TypeConfig as _TC

            _mc_map = {
                tc.content_type_id: tc.matching_class
                for tc in _TC.objects.only("content_type_id", "matching_class")
            }

            for item in instance.object_items.select_related(
                "field", "content_type"
            ).all():
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
                        "typeName": (
                            ct_display_label(item.content_type)
                            if item.content_type_id
                            else ""
                        ),
                        "matchingClass": _mc_map.get(item.content_type_id, ""),
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
        if rulebook is None and not instance.pk:
            rulebook_pk = request.GET.get("rulebook")
            if rulebook_pk and str(rulebook_pk).isdigit():
                try:
                    rulebook = SecurityPolicyRulebook.objects.get(pk=int(rulebook_pk))
                except SecurityPolicyRulebook.DoesNotExist:
                    pass

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
                        "typeName": ct_display_label(ct) if ct else "",
                        "matchingClass": _mc_map.get(ct_id, ""),
                        "exclude": False,
                    }
                )
        return {
            "nsm_rule_picker_data": _build_security_rule_picker_data(rulebook=rulebook),
            "nsm_rule_selections": selections,
            "nsm_rule_virtual_groups": (
                instance.virtual_group_config if instance.pk else {}
            ),
        }


@register_model_view(SecurityPolicyRule, "delete")
class SecurityPolicyRuleDeleteView(generic.ObjectDeleteView):
    queryset = SecurityPolicyRule.objects.all()


@register_model_view(SecurityPolicyAssignment, "list", path="", detail=False)
class SecurityPolicyAssignmentListView(generic.ObjectListView):
    queryset = SecurityPolicyAssignment.objects.all()
    filterset = SecurityPolicyAssignmentFilterSet
    filterset_form = SecurityPolicyAssignmentFilterForm
    table = SecurityPolicyAssignmentTable
    actions = {"export": {"view"}}


@register_model_view(SecurityPolicyAssignment, "add", detail=False)
@register_model_view(SecurityPolicyAssignment, "edit")
class SecurityPolicyAssignmentEditView(generic.ObjectEditView):
    queryset = SecurityPolicyAssignment.objects.all()
    form = SecurityPolicyAssignmentForm

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


@register_model_view(SecurityPolicyAssignment, "delete")
class SecurityPolicyAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = SecurityPolicyAssignment.objects.all()


@register_model_view(
    SecurityPolicyAssignment, "bulk_delete", path="delete", detail=False
)
class SecurityPolicyAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityPolicyAssignment.objects.all()
    table = SecurityPolicyAssignmentTable


class SecurityPolicyRulebookBulkAssignView(generic.ObjectView):
    """Assign a rulebook to multiple devices / VMs / VDCs in one step."""

    queryset = SecurityPolicyRulebook.objects.all()
    template_name = "netbox_nsm/securitypolicyrulebook_bulk_assign.html"

    def get(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        form = SecurityPolicyRulebookBulkAssignForm()
        return self.render_to_response({"object": instance, "form": form})

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        form = SecurityPolicyRulebookBulkAssignForm(request.POST)
        if form.is_valid():
            created = 0
            skipped = 0
            for device in form.cleaned_data.get("devices") or []:
                ct = ContentType.objects.get_for_model(device)
                _, c = SecurityPolicyAssignment.objects.get_or_create(
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
                _, c = SecurityPolicyAssignment.objects.get_or_create(
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
                _, c = SecurityPolicyAssignment.objects.get_or_create(
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
                f"{created} assignment(s) created, {skipped} already existed.",
            )
            return redirect(instance.get_absolute_url())
        return self.render_to_response({"object": instance, "form": form})


class GlobalRulesSearchView(View):
    """
    Global search across ALL rulebooks using the NSM Query Engine.
    GET param: nsm_q — query string (e.g. 'Source.Labels = Web AND Action = Permit')
    Results are grouped by rulebook with match counts.
    URL: /plugins/netbox-nsm/security-rule/search/
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
                SecurityPolicyRule.objects.select_related("rulebook"),
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
