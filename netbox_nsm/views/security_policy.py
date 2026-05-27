from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.html import escape
from django.db.models import Count, Max, Q
import json

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
    SecurityObject,
    SecurityObjectGroup,
    RulebookTypeChoices,
    SecurityPolicyRule,
    SecurityPolicyRulebook,
    SecurityPolicyAssignment,
)
from netbox_nsm.tables import (
    SecurityPolicyAssignmentTable,
    SecurityPolicyRulebookTable,
    SecurityPolicyRuleTable,
)

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


def _options_from_queryset(queryset):
    return [{"value": str(obj.pk), "text": str(obj)} for obj in queryset]


def _build_security_rule_add_options():
    def _opt(value_field, value, group_label, text):
        return {
            "value": json.dumps({"field": value_field, "value": str(value), "label": str(group_label)}),
            "text": f"{group_label}: {text}",
        }

    def _opts(value_field, group_label, items):
        return [_opt(value_field, i["value"], group_label, i["text"]) for i in items]

    service_objects_qs = (
        SecurityObject.objects
        .filter(custom_type__area="services")
        .select_related("custom_type")
        .order_by("custom_type__name", "name")
    )
    service_groups = _options_from_queryset(
        SecurityObjectGroup.objects.filter(area="services").order_by("name")
    )
    action_objects_qs = (
        SecurityObject.objects
        .filter(custom_type__area="action")
        .select_related("custom_type")
        .order_by("custom_type__name", "name")
    )
    action_groups = _options_from_queryset(
        SecurityObjectGroup.objects.filter(area="action").order_by("name")
    )
    srcdst_objects_qs = (
        SecurityObject.objects
        .filter(custom_type__area="srcdst")
        .select_related("custom_type")
        .order_by("custom_type__name", "name")
    )
    srcdst_groups = _options_from_queryset(
        SecurityObjectGroup.objects.filter(area="srcdst").order_by("name")
    )

    def _typed_opts(value_field, qs):
        return [
            _opt(value_field, obj.pk, obj.custom_type.name, obj.name)
            for obj in qs
        ]

    source_options = [
        *_typed_opts("custom_srcdst_objects", srcdst_objects_qs),
        *_opts("source_groups", _("Group"), srcdst_groups),
    ]
    destination_options = [
        *_typed_opts("destination_custom_objects", srcdst_objects_qs),
        *_opts("destination_groups", _("Group"), srcdst_groups),
    ]
    service_options = [
        *_typed_opts("custom_service_objects", service_objects_qs),
        *_opts("service_groups", _("Group"), service_groups),
    ]
    action_options = [
        *_typed_opts("custom_action_objects", action_objects_qs),
        *_opts("action_groups", _("Group"), action_groups),
    ]

    return {
        "source": source_options,
        "destination": destination_options,
        "service": service_options,
        "action": action_options,
    }


def _policy_columns_session_key(rulebook_pk):
    return f"netbox_nsm_policy_columns_{rulebook_pk}"


def _default_security_rules_columns():
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


def _get_policy_table_config(request, rulebook_pk):
    allowed_columns = [name for name, _ in SECURITY_RULES_COLUMNS]
    allowed_set = set(allowed_columns)
    default_columns = _default_security_rules_columns()

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
    """
    For each area (srcdst, services, action), count:
    - individual object usage across all rules
    - label combinations: per-rule sorted-and-joined object names
    """
    from collections import Counter, defaultdict

    AREA_DEFS = [
        ("srcdst",   "Objects (Source / Destination)"),
        ("services", "Services"),
        ("action",   "Action"),
    ]

    rules = list(
        SecurityPolicyRule.objects
        .filter(rulebook=rulebook)
        .prefetch_related(
            "custom_srcdst_objects__custom_type",
            "destination_custom_objects__custom_type",
            "custom_service_objects__custom_type",
            "custom_action_objects__custom_type",
            "source_groups", "destination_groups",
            "service_groups", "action_groups",
        )
    )

    def _names_for_area(rule, area):
        """Return list of (name, type_label) tuples for the given area."""
        if area == "srcdst":
            src = [(o.name, o.custom_type.name) for o in rule.custom_srcdst_objects.all()]
            dst = [(o.name, o.custom_type.name) for o in rule.destination_custom_objects.all()]
            return src + dst
        if area == "services":
            return [(o.name, o.custom_type.name) for o in rule.custom_service_objects.all()]
        if area == "action":
            return [(o.name, o.custom_type.name) for o in rule.custom_action_objects.all()]
        return []

    total_rules = len(rules)
    areas = []

    for area_key, area_label in AREA_DEFS:
        individual = Counter()   # (name, type_label) → count
        combos = Counter()       # sorted-joined name string → count

        for rule in rules:
            items = _names_for_area(rule, area_key)
            names = sorted(set(name for name, _ in items))
            for name, type_label in items:
                individual[(name, type_label)] += 1
            if names:
                combos[" | ".join(names)] += 1

        areas.append({
            "key": area_key,
            "label": area_label,
            "total_objects": len(individual),
            "objects": [
                {"name": name, "type_name": type_name, "count": count}
                for (name, type_name), count in individual.most_common(10)
            ],
            "combos": [
                {"label": label, "count": count}
                for label, count in combos.most_common()
            ],
        })

    return {
        "total_rules": total_rules,
        "areas": areas,
    }


def _build_object_usage_stats(rulebook):
    """Count how often each custom object, zone, and group appears in the rulebook's rules."""
    from collections import Counter
    rules = list(
        SecurityPolicyRule.objects
        .filter(rulebook=rulebook)
        .prefetch_related(
            "custom_srcdst_objects__custom_type",
            "destination_custom_objects__custom_type",
            "custom_service_objects__custom_type",
            "custom_action_objects__custom_type",
            "source_groups", "destination_groups",
            "service_groups", "action_groups",
        )
    )

    object_counter = Counter()
    group_counter = Counter()

    for rule in rules:
        for obj in list(rule.custom_srcdst_objects.all()) + list(rule.destination_custom_objects.all()) + \
                   list(rule.custom_service_objects.all()) + list(rule.custom_action_objects.all()):
            object_counter[(obj.pk, obj.name, obj.custom_type.name)] += 1
        for grp in list(rule.source_groups.all()) + list(rule.destination_groups.all()) + \
                   list(rule.service_groups.all()) + list(rule.action_groups.all()):
            group_counter[(grp.pk, grp.name)] += 1

    top_objects = [
        {"pk": pk, "name": name, "type": type_name, "count": count}
        for (pk, name, type_name), count in object_counter.most_common(10)
    ]
    top_groups = [
        {"pk": pk, "name": name, "count": count}
        for (pk, name), count in group_counter.most_common(10)
    ]
    return {
        "top_objects": top_objects,
        "top_groups": top_groups,
        "total_rules": len(rules),
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
)


ZONE_TYPE_NAME = "Zones"
_NONE_ZONE_PK = 0


def _make_none_zone():
    from types import SimpleNamespace
    return SimpleNamespace(pk=_NONE_ZONE_PK, name="(none)")


@register_model_view(SecurityPolicyRulebook, name="visualization", path="visualization/zonematrix")
class SecurityPolicyRulebookVisualizationView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()
    template_name = "netbox_nsm/securitypolicyrulebook_visualization.html"
    tab = ViewTab(
        label=_("Visualisation"),
        permission="netbox_nsm.view_securitypolicyrulebook",
    )

    def get_extra_context(self, request, instance):
        from collections import defaultdict

        ACTION_COLOR = {
            "permit": "success",
            "deny": "danger",
            "reject": "danger",
            "log": "warning",
            "count": "info",
        }

        rules_qs = list(
            SecurityPolicyRule.objects
            .filter(rulebook=instance)
            .prefetch_related(
                "custom_srcdst_objects__custom_type",
                "destination_custom_objects__custom_type",
                "custom_action_objects",
            )
            .order_by("index")
        )

        # Collect all unique zone objects from source and destination
        zones_by_pk = {}
        has_none_src = False
        has_none_dst = False
        for rule in rules_qs:
            src_zones = [o for o in rule.custom_srcdst_objects.all() if o.custom_type.name == ZONE_TYPE_NAME]
            dst_zones = [o for o in rule.destination_custom_objects.all() if o.custom_type.name == ZONE_TYPE_NAME]
            if not src_zones:
                has_none_src = True
            if not dst_zones:
                has_none_dst = True
            for z in src_zones + dst_zones:
                zones_by_pk[z.pk] = z

        all_zones = sorted(zones_by_pk.values(), key=lambda z: z.name)
        if has_none_src or has_none_dst:
            all_zones = [_make_none_zone()] + all_zones

        # Zone filter from query string
        src_filter = [v for v in request.GET.getlist("src_zone_id") if v.isdigit()]
        dst_filter = [v for v in request.GET.getlist("dst_zone_id") if v.isdigit()]
        selected_src_pks = {int(v) for v in src_filter}
        selected_dst_pks = {int(v) for v in dst_filter}
        src_zones = [z for z in all_zones if z.pk in selected_src_pks] if src_filter else all_zones
        dst_zones = [z for z in all_zones if z.pk in selected_dst_pks] if dst_filter else all_zones

        def _action_color_label(rule):
            for obj in rule.custom_action_objects.all():
                name_lower = obj.name.lower()
                for key, color in ACTION_COLOR.items():
                    if key in name_lower:
                        return color, obj.name
            return "secondary", "?"

        # Build cell_map: (src_pk, dst_pk) → list of rules
        cell_map = defaultdict(list)
        for rule in rules_qs:
            rule._color, rule._action_label = _action_color_label(rule)
            src_pks = [o.pk for o in rule.custom_srcdst_objects.all() if o.custom_type.name == ZONE_TYPE_NAME]
            dst_pks = [o.pk for o in rule.destination_custom_objects.all() if o.custom_type.name == ZONE_TYPE_NAME]
            if not src_pks:
                src_pks = [_NONE_ZONE_PK]
            if not dst_pks:
                dst_pks = [_NONE_ZONE_PK]
            for sp in src_pks:
                for dp in dst_pks:
                    cell_map[(sp, dp)].append(rule)

        policy_url_base = reverse(
            "plugins:netbox_nsm:securitypolicyrulebook_policy",
            args=[instance.pk],
        )
        add_url_base = reverse("plugins:netbox_nsm:securitypolicyrule_add")
        viz_url_base = reverse(
            "plugins:netbox_nsm:securitypolicyrulebook_visualization",
            args=[instance.pk],
        )

        matrix_rows = []
        for src in src_zones:
            cells = []
            for dst in dst_zones:
                rules = cell_map.get((src.pk, dst.pk), [])
                count = len(rules)
                sp_q = f"src_obj_id={src.pk}" if src.pk != _NONE_ZONE_PK else ""
                dp_q = f"dst_obj_id={dst.pk}" if dst.pk != _NONE_ZONE_PK else ""
                filter_qs = "?" + "&".join(p for p in [sp_q, dp_q] if p) if (sp_q or dp_q) else ""
                if count == 0:
                    src_add = f"&custom_srcdst_objects={src.pk}" if src.pk != _NONE_ZONE_PK else ""
                    dst_add = f"&destination_custom_objects={dst.pk}" if dst.pk != _NONE_ZONE_PK else ""
                    cell = {
                        "type": "empty",
                        "is_self": src.pk == dst.pk,
                        "href": (
                            f"{add_url_base}?rulebook={instance.pk}"
                            f"{src_add}{dst_add}"
                            f"&return_url={policy_url_base}"
                        ),
                    }
                elif count == 1:
                    r = rules[0]
                    cell = {
                        "type": "single",
                        "color": r._color,
                        "label": r._action_label,
                        "is_self": src.pk == dst.pk,
                        "href": f"{policy_url_base}{filter_qs}",
                    }
                else:
                    cell = {
                        "type": "multi",
                        "count": count,
                        "is_self": src.pk == dst.pk,
                        "href": f"{policy_url_base}{filter_qs}",
                    }
                cells.append(cell)
            matrix_rows.append({"source_zone": src, "cells": cells})

        return {
            "all_zones": all_zones,
            "src_zones": src_zones,
            "dst_zones": dst_zones,
            "selected_src_pks": selected_src_pks,
            "selected_dst_pks": selected_dst_pks,
            "viz_url_base": viz_url_base,
            "matrix_rows": matrix_rows,
            "object_analysis": _build_object_analysis(instance),
        }


@register_model_view(SecurityPolicyRulebook)
class SecurityPolicyRulebookView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()

    def get_extra_context(self, request, instance):
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return {}

        config = _get_policy_table_config(request, instance.pk)
        selected_set = set(config["selected_columns"])
        order_map = {name: idx + 1 for idx, name in enumerate(config["selected_columns"])}

        return {
            "security_rules_columns": SECURITY_RULES_COLUMNS,
            "selected_security_rules_columns": config["selected_columns"],
            "selected_security_rules_columns_set": selected_set,
            "security_rules_column_order": order_map,
            "security_rules_column_order_list": config["selected_columns"],
            "custom_columns": config["custom_columns"],
        }


@register_model_view(SecurityPolicyRulebook, name="policy_columns")
class SecurityPolicyRulebookPolicyColumnsView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all()

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook", args=[instance.pk]))

        allowed_columns = {name for name, _ in SECURITY_RULES_COLUMNS}
        selected_columns = [
            column for column in request.POST.getlist("columns") if column in allowed_columns
        ]

        if not selected_columns:
            selected_columns = _default_security_rules_columns()

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

        return redirect(reverse("plugins:netbox_nsm:securitypolicyrulebook_policy", args=[instance.pk]))


@register_model_view(SecurityPolicyRulebook, name="policy")
class SecurityPolicyRulebookRulesView(generic.ObjectView):
    queryset = SecurityPolicyRulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/securitypolicyrulebook_security_policy.html"
    tab = ViewTab(
        label=_("Policy"),
        permission="netbox_nsm.view_securitypolicyrulebook",
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
            reverse("plugins:netbox_nsm:securitypolicyrulebook_policy", args=[instance.pk])
        )

    def get_extra_context(self, request, instance):
        rules_qs = SecurityPolicyRule.objects.filter(rulebook=instance).prefetch_related(
            "source_users",
            "destination_users",
            "custom_srcdst_objects__custom_type",
            "destination_custom_objects__custom_type",
            "custom_service_objects__custom_type",
            "custom_action_objects__custom_type",
            "source_groups",
            "destination_groups",
            "service_groups",
            "action_groups",
        )

        # ── optional custom-object filter (src_obj_id / dst_obj_id) ─────────────────
        # Works for ALL SecurityObject types: labels, addresses, services, etc.
        # Subset matching: ALL supplied PKs must be present in the respective field.
        src_obj_filter = [v for v in request.GET.getlist("src_obj_id") if v.isdigit()]
        dst_obj_filter = [v for v in request.GET.getlist("dst_obj_id") if v.isdigit()]
        if src_obj_filter:
            n = len(src_obj_filter)
            rules_qs = rules_qs.annotate(
                _src_obj_matched=Count(
                    "custom_srcdst_objects",
                    filter=Q(custom_srcdst_objects__id__in=src_obj_filter),
                    distinct=True,
                )
            ).filter(_src_obj_matched=n)
        if dst_obj_filter:
            n = len(dst_obj_filter)
            rules_qs = rules_qs.annotate(
                _dst_obj_matched=Count(
                    "destination_custom_objects",
                    filter=Q(destination_custom_objects__id__in=dst_obj_filter),
                    distinct=True,
                )
            ).filter(_dst_obj_matched=n)

        # ── optional text / column search ──────────────────────────────────────
        search_q   = request.GET.get("q",   "").strip()
        search_col = request.GET.get("col", "").strip()
        search_val = request.GET.get("val", "").strip()

        if search_q:
            _q = (
                Q(name__icontains=search_q)
                | Q(description__icontains=search_q)
                | Q(custom_srcdst_objects__name__icontains=search_q)
                | Q(custom_service_objects__name__icontains=search_q)
                | Q(custom_action_objects__name__icontains=search_q)
                | Q(source_groups__name__icontains=search_q)
                | Q(destination_groups__name__icontains=search_q)
                | Q(service_groups__name__icontains=search_q)
                | Q(action_groups__name__icontains=search_q)
            )
            if search_q.isdigit():
                _q |= Q(index=int(search_q))
            rules_qs = rules_qs.filter(_q).distinct()

        _COLUMN_LOOKUPS = {
            "name":        "name__icontains",
            "description": "description__icontains",
        }
        if search_col and search_val:
            if search_col == "index" and search_val.isdigit():
                rules_qs = rules_qs.filter(index=int(search_val)).distinct()
            elif search_col in _COLUMN_LOOKUPS:
                rules_qs = rules_qs.filter(**{_COLUMN_LOOKUPS[search_col]: search_val}).distinct()

        # resolve custom-object names for active-filter badge
        active_src_objs = (
            list(SecurityObject.objects.filter(pk__in=src_obj_filter).select_related("custom_type").order_by("name"))
            if src_obj_filter else []
        )
        active_dst_objs = (
            list(SecurityObject.objects.filter(pk__in=dst_obj_filter).select_related("custom_type").order_by("name"))
            if dst_obj_filter else []
        )

        config = _get_policy_table_config(request, instance.pk)
        selected_columns = config["selected_columns"]
        custom_columns = config["custom_columns"]

        all_columns = [name for name, _ in SECURITY_RULES_COLUMNS]
        excluded_columns = [name for name in all_columns if name not in selected_columns]
        custom_keys = [f"custom_column_{idx}" for idx in range(1, len(custom_columns) + 1)]

        policy_table_class = _build_policy_table_class(custom_columns, selected_columns)

        policy_table = policy_table_class(
            rules_qs,
            orderable=False,
            exclude=excluded_columns,
            sequence=("pk",) + tuple(selected_columns + custom_keys + ["..."]),
        )
        policy_table.configure(request)
        return {
            "table": policy_table,
            "is_security_rules": True,
            "security_rules_columns": SECURITY_RULES_COLUMNS,
            "selected_security_rules_columns": selected_columns,
            "active_src_objs": active_src_objs,
            "active_dst_objs": active_dst_objs,
            "search_q": search_q,
            "search_col": search_col,
            "search_val": search_val,
        }


@register_model_view(SecurityPolicyRulebook, "list", path="", detail=False)
class SecurityPolicyRulebookListView(generic.ObjectListView):
    queryset = SecurityPolicyRulebook.objects.all()
    filterset = SecurityPolicyRulebookFilterSet
    filterset_form = SecurityPolicyRulebookFilterForm
    table = SecurityPolicyRulebookTable


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
    """Return list of {str, url} from field_data object_ref values."""
    refs = []
    for v in (obj.field_data or {}).values():
        if isinstance(v, dict) and v.get("str") and v.get("url"):
            refs.append({"str": v["str"], "url": v["url"]})
    return refs


def _collect_ips_from_group(group, visited=None):
    """Recursively resolve IPs from SecurityObjectGroup members and sub_groups."""
    if visited is None:
        visited = set()
    if group.pk in visited:
        return []
    visited.add(group.pk)
    refs = []
    for member in group.members.all().select_related("custom_type"):
        refs.extend(_extract_ip_refs(member))
    for sub in group.sub_groups.all():
        refs.extend(_collect_ips_from_group(sub, visited))
    return refs


@register_model_view(SecurityPolicyRule)
class SecurityPolicyRuleView(generic.ObjectView):
    queryset = SecurityPolicyRule.objects.prefetch_related(
        "source_users",
        "destination_users",
        "custom_srcdst_objects__custom_type",
        "destination_custom_objects__custom_type",
        "source_groups__members__custom_type",
        "source_groups__sub_groups",
        "destination_groups__members__custom_type",
        "destination_groups__sub_groups",
        "custom_service_objects__custom_type",
        "custom_action_objects__custom_type",
    ).select_related("rulebook")

    def get_extra_context(self, request, instance):
        src_ips = []
        for o in instance.custom_srcdst_objects.all():
            src_ips.extend(_extract_ip_refs(o))
        for g in instance.source_groups.all():
            src_ips.extend(_collect_ips_from_group(g))

        dst_ips = []
        for o in instance.destination_custom_objects.all():
            dst_ips.extend(_extract_ip_refs(o))
        for g in instance.destination_groups.all():
            dst_ips.extend(_collect_ips_from_group(g))

        return {"src_ips": src_ips, "dst_ips": dst_ips}


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
                            instance.comments = rulebook.rule_comment_template.format_map({
                                "rulebook": rulebook.name,
                                "index": instance.index,
                                "rule_name": "",
                            })
                        except (KeyError, ValueError):
                            instance.comments = rulebook.rule_comment_template
                except SecurityPolicyRulebook.DoesNotExist:
                    pass
        return instance

    def get_extra_context(self, request, instance):
        initial_labels: dict = {"source": {}, "destination": {}, "service": {}, "action": {}}
        if instance.pk:
            for obj in instance.custom_srcdst_objects.select_related("custom_type").all():
                initial_labels["source"][str(obj.pk)] = obj.custom_type.name
            for obj in instance.destination_custom_objects.select_related("custom_type").all():
                initial_labels["destination"][str(obj.pk)] = obj.custom_type.name
            for obj in instance.custom_service_objects.select_related("custom_type").all():
                initial_labels["service"][str(obj.pk)] = obj.custom_type.name
            for obj in instance.custom_action_objects.select_related("custom_type").all():
                initial_labels["action"][str(obj.pk)] = obj.custom_type.name
        return {
            "nsm_add_options": _build_security_rule_add_options(),
            "nsm_initial_labels": json.dumps(initial_labels),
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


@register_model_view(SecurityPolicyAssignment, "bulk_delete", path="delete", detail=False)
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
