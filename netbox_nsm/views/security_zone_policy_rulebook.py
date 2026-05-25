from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.html import escape
from django.db.models import Max, Q
import json

import markdown
import django_tables2 as tables

from utilities.views import ViewTab, register_model_view
from netbox.views import generic

from netbox_nsm.filtersets import (
    SecurityZonePolicyRuleFilterSet,
    SecurityZonePolicyRulebookAssignmentFilterSet,
    SecurityZonePolicyRulebookFilterSet,
)
from netbox_nsm.forms import (
    SecurityZonePolicyRulebookAssignmentFilterForm,
    SecurityZonePolicyRulebookAssignmentForm,
    SecurityZonePolicyRulebookBulkEditForm,
    SecurityZonePolicyRulebookFilterForm,
    SecurityZonePolicyRulebookForm,
    SecurityZonePolicyRuleFilterForm,
    SecurityZonePolicyRuleForm,
)
from netbox_nsm.models import (
    ApplicationItem,
    Application,
    ApplicationSet,
    ObjectCustomObject,
    ObjectGroup,
    RulebookTypeChoices,
    SecurityZone,
    SecurityZonePolicyRule,
    SecurityZonePolicyRulebook,
    SecurityZonePolicyRulebookAssignment,
)
from netbox_nsm.tables import (
    SecurityZonePolicyRulebookAssignmentTable,
    SecurityZonePolicyRulebookTable,
    SecurityZonePolicyRuleTable,
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


def _build_security_rule_object_catalog():
    zones = _options_from_queryset(SecurityZone.objects.order_by("name"))

    return {
        "source_zones": zones,
        "destination_zones": zones,
        "services": _options_from_queryset(ApplicationItem.objects.order_by("name")),
        "applications": _options_from_queryset(Application.objects.order_by("name")),
        "application_sets": _options_from_queryset(ApplicationSet.objects.order_by("name")),
    }


def _build_security_rule_add_options():
    catalog = _build_security_rule_object_catalog()

    def _option(value_field, value, label, text):
        return {
            "value": json.dumps({"field": value_field, "value": str(value), "label": str(label)}),
            "text": f"{label}: {text}",
        }

    srcdst_objects = _options_from_queryset(
        ObjectCustomObject.objects.filter(custom_type__area="srcdst").select_related("custom_type").order_by("name")
    )
    srcdst_groups = _options_from_queryset(
        ObjectGroup.objects.filter(area="srcdst").order_by("name")
    )
    service_objects = _options_from_queryset(
        ObjectCustomObject.objects.filter(custom_type__area="services").select_related("custom_type").order_by("name")
    )
    service_groups = _options_from_queryset(
        ObjectGroup.objects.filter(area="services").order_by("name")
    )
    action_objects = _options_from_queryset(
        ObjectCustomObject.objects.filter(custom_type__area="action").select_related("custom_type").order_by("name")
    )
    action_groups = _options_from_queryset(
        ObjectGroup.objects.filter(area="action").order_by("name")
    )

    source_options = [
        *[_option("source_zones", i["value"], _("Zone"), i["text"]) for i in catalog.get("source_zones", [])],
        *[_option("custom_srcdst_objects", i["value"], _("Object"), i["text"]) for i in srcdst_objects],
        *[_option("source_groups", i["value"], _("Group"), i["text"]) for i in srcdst_groups],
    ]
    destination_options = [
        *[_option("destination_zones", i["value"], _("Zone"), i["text"]) for i in catalog.get("destination_zones", [])],
        *[_option("destination_custom_objects", i["value"], _("Object"), i["text"]) for i in srcdst_objects],
        *[_option("destination_groups", i["value"], _("Group"), i["text"]) for i in srcdst_groups],
    ]

    action_options = []
    for choice_value, choice_label in SecurityZonePolicyRule._meta.get_field("policy_action").choices:
        action_options.append(
            {
                "value": json.dumps({"field": "policy_action", "value": str(choice_value), "label": str(_("Default Action"))}),
                "text": str(choice_label),
            }
        )
    action_options += [
        *[_option("custom_action_objects", i["value"], _("Object"), i["text"]) for i in action_objects],
        *[_option("action_groups", i["value"], _("Group"), i["text"]) for i in action_groups],
    ]

    service_options = [
        *[_option("services", i["value"], _("Service"), i["text"]) for i in catalog.get("services", [])],
        *[_option("applications", i["value"], _("Application"), i["text"]) for i in catalog.get("applications", [])],
        *[_option("application_sets", i["value"], _("Application Set"), i["text"]) for i in catalog.get("application_sets", [])],
        *[_option("custom_service_objects", i["value"], _("Object"), i["text"]) for i in service_objects],
        *[_option("service_groups", i["value"], _("Group"), i["text"]) for i in service_groups],
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
        for column in SecurityZonePolicyRuleTable.Meta.default_columns
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
        for column in SecurityZonePolicyRuleTable.Meta.default_columns
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
        (SecurityZonePolicyRuleTable.Meta,),
        {
            "model": SecurityZonePolicyRule,
            "fields": tuple(SecurityZonePolicyRuleTable.Meta.fields) + tuple(custom_keys),
            "default_columns": tuple(selected_columns) + tuple(custom_keys),
        },
    )
    return type("ConfiguredSecurityZonePolicyRuleTable", (SecurityZonePolicyRuleTable,), attrs)

__all__ = (
    "SecurityZonePolicyRulebookView",
    "SecurityZonePolicyRulebookListView",
    "SecurityZonePolicyRulebookEditView",
    "SecurityZonePolicyRulebookDeleteView",
    "SecurityZonePolicyRulebookBulkEditView",
    "SecurityZonePolicyRulebookBulkDeleteView",
    "SecurityZonePolicyRulebookPolicyColumnsView",
    "SecurityZonePolicyRulebookRulesView",
    "SecurityZonePolicyRuleView",
    "SecurityZonePolicyRuleListView",
    "SecurityZonePolicyRuleEditView",
    "SecurityZonePolicyRuleDeleteView",
    "SecurityZonePolicyRulebookAssignmentListView",
    "SecurityZonePolicyRulebookAssignmentEditView",
    "SecurityZonePolicyRulebookAssignmentDeleteView",
    "SecurityZonePolicyRulebookAssignmentBulkDeleteView",
)


@register_model_view(SecurityZonePolicyRulebook)
class SecurityZonePolicyRulebookView(generic.ObjectView):
    queryset = SecurityZonePolicyRulebook.objects.all()

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


@register_model_view(SecurityZonePolicyRulebook, name="policy_columns")
class SecurityZonePolicyRulebookPolicyColumnsView(generic.ObjectView):
    queryset = SecurityZonePolicyRulebook.objects.all()

    def post(self, request, *args, **kwargs):
        instance = self.get_object(**kwargs)
        if instance.rulebook_type != RulebookTypeChoices.POLICY:
            return redirect(reverse("plugins:netbox_nsm:securityzonepolicyrulebook", args=[instance.pk]))

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

        return redirect(reverse("plugins:netbox_nsm:securityzonepolicyrulebook_policy", args=[instance.pk]))


@register_model_view(SecurityZonePolicyRulebook, name="policy")
class SecurityZonePolicyRulebookRulesView(generic.ObjectView):
    queryset = SecurityZonePolicyRulebook.objects.all().prefetch_related("rules")
    template_name = "netbox_nsm/securityzonepolicyrulebook_security_policy.html"
    tab = ViewTab(
        label=_("Policy"),
        permission="netbox_nsm.view_securityzonepolicyrulebook",
    )

    def get_extra_context(self, request, instance):
        rules_qs = SecurityZonePolicyRule.objects.filter(rulebook=instance).prefetch_related(
            "source_zones",
            "destination_zones",
            "source_users",
            "destination_users",
            "services",
            "applications",
            "application_sets",
            "custom_srcdst_objects__custom_type",
            "custom_service_objects__custom_type",
            "custom_action_objects__custom_type",
        )

        # ── optional zone filter (set by clicking a visualization matrix cell) ──
        src_filter  = [v for v in request.GET.getlist("source_zones_id")  if v.isdigit()]
        dst_filter  = [v for v in request.GET.getlist("destination_zones_id") if v.isdigit()]
        if src_filter:
            rules_qs = rules_qs.filter(source_zones__id__in=src_filter)
        if dst_filter:
            rules_qs = rules_qs.filter(destination_zones__id__in=dst_filter)
        if src_filter or dst_filter:
            rules_qs = rules_qs.distinct()

        # resolve zone names for active-filter badge
        active_src_zones = (
            list(SecurityZone.objects.filter(pk__in=src_filter).order_by("name"))
            if src_filter else []
        )
        active_dst_zones = (
            list(SecurityZone.objects.filter(pk__in=dst_filter).order_by("name"))
            if dst_filter else []
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
            sequence=tuple(selected_columns + custom_keys + ["..."]),
        )
        policy_table.configure(request)
        return {
            "table": policy_table,
            "is_security_rules": True,
            "security_rules_columns": SECURITY_RULES_COLUMNS,
            "selected_security_rules_columns": selected_columns,
            "active_src_zones": active_src_zones,
            "active_dst_zones": active_dst_zones,
        }


@register_model_view(SecurityZonePolicyRulebook, name="visualization", path="visualization/zonematrix")
class SecurityZonePolicyRulebookVisualizationView(generic.ObjectView):
    queryset = SecurityZonePolicyRulebook.objects.all()
    template_name = "netbox_nsm/securityzonepolicyrulebook_visualization.html"
    tab = ViewTab(
        label=_("Visualisation"),
        permission="netbox_nsm.view_securityzonepolicyrulebook",
    )

    def get_extra_context(self, request, instance):
        from collections import defaultdict

        ACTION_COLOR = {
            "permit": "success",
            "deny": "danger",
            "log": "warning",
            "count": "info",
            "reject": "danger",
        }

        rules_qs = (
            SecurityZonePolicyRule.objects
            .filter(rulebook=instance)
            .prefetch_related("source_zones", "destination_zones")
            .order_by("index")
        )

        # collect all unique zones (src ∪ dst), sorted alphabetically
        # rules with no source/destination zones get a sentinel "(none)" zone
        NONE_ZONE_PK = 0
        zones_by_pk = {}
        has_none_src = False
        has_none_dst = False
        for rule in rules_qs:
            src_list = list(rule.source_zones.all())
            dst_list = list(rule.destination_zones.all())
            if not src_list:
                has_none_src = True
            if not dst_list:
                has_none_dst = True
            for z in src_list:
                zones_by_pk[z.pk] = z
            for z in dst_list:
                zones_by_pk[z.pk] = z
        all_zones = sorted(zones_by_pk.values(), key=lambda z: z.name)
        if has_none_src or has_none_dst:
            from types import SimpleNamespace
            all_zones = [SimpleNamespace(pk=NONE_ZONE_PK, name="(none)")] + all_zones

        # optional zone filter from GET params – separate src/dst selectors
        # empty selection = show all zones
        src_filter = [v for v in request.GET.getlist("src_zone_id") if v.isdigit()]
        dst_filter = [v for v in request.GET.getlist("dst_zone_id") if v.isdigit()]
        selected_src_pks = set(int(v) for v in src_filter)
        selected_dst_pks = set(int(v) for v in dst_filter)
        src_zones = [z for z in all_zones if z.pk in selected_src_pks] if src_filter else all_zones
        dst_zones = [z for z in all_zones if z.pk in selected_dst_pks] if dst_filter else all_zones

        # build cell_map: (src_pk, dst_pk) → list[rule]
        # rules without zones are mapped to NONE_ZONE_PK (0)
        cell_map = defaultdict(list)
        for rule in rules_qs:
            rule._color = ACTION_COLOR.get(rule.policy_action, "secondary")
            src_list = list(rule.source_zones.all())
            dst_list = list(rule.destination_zones.all())
            for sp in ([z.pk for z in src_list] if src_list else [NONE_ZONE_PK]):
                for dp in ([z.pk for z in dst_list] if dst_list else [NONE_ZONE_PK]):
                    cell_map[(sp, dp)].append(rule)

        policy_url_base = reverse(
            "plugins:netbox_nsm:securityzonepolicyrulebook_policy",
            args=[instance.pk],
        )
        add_url_base = reverse("plugins:netbox_nsm:securityzonepolicyrule_add")
        viz_url_base = reverse(
            "plugins:netbox_nsm:securityzonepolicyrulebook_visualization",
            args=[instance.pk],
        )

        # build matrix_rows for template
        matrix_rows = []
        for src in src_zones:
            cells = []
            for dst in dst_zones:
                rules = cell_map.get((src.pk, dst.pk), [])
                count = len(rules)
                # build zone-aware href query strings (skip pk=0 sentinel)
                sp_q = f"source_zones_id={src.pk}" if src.pk != NONE_ZONE_PK else ""
                dp_q = f"destination_zones_id={dst.pk}" if dst.pk != NONE_ZONE_PK else ""
                filter_qs = "?" + "&".join(p for p in [sp_q, dp_q] if p)
                if count == 0:
                    src_add = f"&source_zones={src.pk}" if src.pk != NONE_ZONE_PK else ""
                    dst_add = f"&destination_zones={dst.pk}" if dst.pk != NONE_ZONE_PK else ""
                    cell = {
                        "type": "empty",
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
                        "rule": r,
                        "color": r._color,
                        "label": r.get_policy_action_display(),
                        "href": f"{policy_url_base}{filter_qs}",
                    }
                else:
                    cell = {
                        "type": "multi",
                        "count": count,
                        "href": f"{policy_url_base}{filter_qs}",
                    }
                cell["is_self"] = src.pk == dst.pk
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
        }


@register_model_view(SecurityZonePolicyRulebook, "list", path="", detail=False)
class SecurityZonePolicyRulebookListView(generic.ObjectListView):
    queryset = SecurityZonePolicyRulebook.objects.all()
    filterset = SecurityZonePolicyRulebookFilterSet
    filterset_form = SecurityZonePolicyRulebookFilterForm
    table = SecurityZonePolicyRulebookTable


@register_model_view(SecurityZonePolicyRulebook, "add", detail=False)
@register_model_view(SecurityZonePolicyRulebook, "edit")
class SecurityZonePolicyRulebookEditView(generic.ObjectEditView):
    queryset = SecurityZonePolicyRulebook.objects.all()
    form = SecurityZonePolicyRulebookForm


@register_model_view(SecurityZonePolicyRulebook, "delete")
class SecurityZonePolicyRulebookDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZonePolicyRulebook.objects.all()


@register_model_view(SecurityZonePolicyRulebook, "bulk_edit", path="edit", detail=False)
class SecurityZonePolicyRulebookBulkEditView(generic.BulkEditView):
    queryset = SecurityZonePolicyRulebook.objects.all()
    filterset = SecurityZonePolicyRulebookFilterSet
    table = SecurityZonePolicyRulebookTable
    form = SecurityZonePolicyRulebookBulkEditForm


@register_model_view(SecurityZonePolicyRulebook, "bulk_delete", path="delete", detail=False)
class SecurityZonePolicyRulebookBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZonePolicyRulebook.objects.all()
    table = SecurityZonePolicyRulebookTable


@register_model_view(SecurityZonePolicyRule)
class SecurityZonePolicyRuleView(generic.ObjectView):
    queryset = SecurityZonePolicyRule.objects.prefetch_related(
        "source_zones",
        "destination_zones",
        "source_users",
        "destination_users",
        "services",
        "applications",
        "application_sets",
        "custom_srcdst_objects__custom_type",
        "custom_service_objects__custom_type",
        "custom_action_objects__custom_type",
    ).select_related("rulebook")


@register_model_view(SecurityZonePolicyRule, "list", path="", detail=False)
class SecurityZonePolicyRuleListView(generic.ObjectListView):
    queryset = SecurityZonePolicyRule.objects.select_related("rulebook")
    filterset = SecurityZonePolicyRuleFilterSet
    filterset_form = SecurityZonePolicyRuleFilterForm
    table = SecurityZonePolicyRuleTable


@register_model_view(SecurityZonePolicyRule, "add", detail=False)
@register_model_view(SecurityZonePolicyRule, "edit")
class SecurityZonePolicyRuleEditView(generic.ObjectEditView):
    queryset = SecurityZonePolicyRule.objects.all()
    form = SecurityZonePolicyRuleForm
    template_name = "netbox_nsm/securityzonepolicyrule_edit.html"

    def alter_object(self, instance, request, args, kwargs):
        """Pre-fill index with last_index + 1 when creating a new rule."""
        if not instance.pk:
            rulebook_pk = request.GET.get("rulebook")
            if rulebook_pk and str(rulebook_pk).isdigit():
                result = SecurityZonePolicyRule.objects.filter(
                    rulebook_id=int(rulebook_pk)
                ).aggregate(max_index=Max("index"))
                instance.index = (result.get("max_index") or 0) + 1
        return instance

    def get_extra_context(self, request, instance):
        return {
            "nsm_object_catalog": _build_security_rule_object_catalog(),
            "nsm_add_options": _build_security_rule_add_options(),
        }


@register_model_view(SecurityZonePolicyRule, "delete")
class SecurityZonePolicyRuleDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZonePolicyRule.objects.all()


@register_model_view(SecurityZonePolicyRulebookAssignment, "list", path="", detail=False)
class SecurityZonePolicyRulebookAssignmentListView(generic.ObjectListView):
    queryset = SecurityZonePolicyRulebookAssignment.objects.all()
    filterset = SecurityZonePolicyRulebookAssignmentFilterSet
    filterset_form = SecurityZonePolicyRulebookAssignmentFilterForm
    table = SecurityZonePolicyRulebookAssignmentTable
    actions = {"export": {"view"}}


@register_model_view(SecurityZonePolicyRulebookAssignment, "add", detail=False)
@register_model_view(SecurityZonePolicyRulebookAssignment, "edit")
class SecurityZonePolicyRulebookAssignmentEditView(generic.ObjectEditView):
    queryset = SecurityZonePolicyRulebookAssignment.objects.all()
    form = SecurityZonePolicyRulebookAssignmentForm

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


@register_model_view(SecurityZonePolicyRulebookAssignment, "delete")
class SecurityZonePolicyRulebookAssignmentDeleteView(generic.ObjectDeleteView):
    queryset = SecurityZonePolicyRulebookAssignment.objects.all()


@register_model_view(SecurityZonePolicyRulebookAssignment, "bulk_delete", path="delete", detail=False)
class SecurityZonePolicyRulebookAssignmentBulkDeleteView(generic.BulkDeleteView):
    queryset = SecurityZonePolicyRulebookAssignment.objects.all()
    table = SecurityZonePolicyRulebookAssignmentTable
