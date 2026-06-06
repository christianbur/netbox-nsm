import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from netbox_nsm.models import Rule, Rulebook, RulebookTypeChoices
from netbox_nsm.picker_browse import (
    MIN_PICKER_QUERY_LEN,
    browse_picker_objects,
)
from netbox_nsm.branch_db import ensure_branch_context
from netbox_nsm.changelog_utils import (
    record_rule_assignment_changelog,
    record_rulebook_rules_changelog,
    snapshot_instance,
)
from netbox_nsm.rule_field_selections import (
    build_all_column_cells_payload,
    build_column_cell_payload,
    get_all_column_selections,
    get_column_selections,
    rules_column_keys_for_rulebook,
    save_all_column_selections,
    save_column_selections,
)
from netbox_nsm.views.rulebook import _build_security_rule_picker_data

__all__ = (
    "RulePickerBrowseApiView",
    "RulebookPickerDataApiView",
    "RuleFieldSelectionsApiView",
)


class RulePickerBrowseApiView(LoginRequiredMixin, View):
    """
    Server-side object browse for the rule editor (branch-aware via Django ORM).

    GET /plugins/netbox-nsm/api/picker-browse/?ct=<content_type_id>&q=...&limit=30&offset=0
    Optional: regex=<name_filter_regex from RulebookFieldType>
    """

    def get(self, request):
        if not request.user.has_perm("netbox_nsm.view_rule"):
            return JsonResponse({"detail": "Forbidden"}, status=403)

        try:
            ct_id = int(request.GET["ct"])
        except (KeyError, TypeError, ValueError):
            return HttpResponseBadRequest("ct required")

        q_raw = (request.GET.get("q") or "").strip()
        wildcard = q_raw == "*"
        q = "" if wildcard else q_raw
        if not wildcard and q and len(q) < MIN_PICKER_QUERY_LEN:
            return JsonResponse({"count": 0, "results": []})

        try:
            limit = int(request.GET.get("limit", 30))
        except (TypeError, ValueError):
            limit = 30
        try:
            offset = int(request.GET.get("offset", 0))
        except (TypeError, ValueError):
            offset = 0

        name_filter_regex = (request.GET.get("regex") or "").strip() or None

        try:
            with ensure_branch_context(request):
                payload = browse_picker_objects(
                    ct_id,
                    q=q,
                    limit=limit,
                    offset=offset,
                    name_filter_regex=name_filter_regex,
                )
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))

        return JsonResponse(payload)


class RulebookPickerDataApiView(LoginRequiredMixin, View):
    """
    Lazy-load picker metadata for one rulebook (object types, groups).

    GET /plugins/netbox-nsm/api/rulebooks/<pk>/picker-data/
    """

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rule"):
            return JsonResponse({"detail": "Forbidden"}, status=403)

        rulebook = get_object_or_404(Rulebook, pk=pk)
        if rulebook.rulebook_type != RulebookTypeChoices.SECURITY_RULES:
            return JsonResponse({"detail": "Not found"}, status=404)

        return JsonResponse(_build_security_rule_picker_data(rulebook=rulebook))


class RuleFieldSelectionsApiView(LoginRequiredMixin, View):
    """
    Read/write object selections for AG Grid columns.

    GET  .../field-selections/?column=source::ct_1  — one column
    GET  .../field-selections/                      — all columns
    POST .../field-selections/?column=source::ct_1  — body: {"selections": [...]}
    POST .../field-selections/                      — body: {"columns": {...}}
    """

    def _load_rule(self, pk, *, prefetch: bool = False):
        qs = Rule.objects.select_related("rulebook")
        if prefetch:
            qs = qs.prefetch_related(
                "object_items__field",
                "object_items__content_type",
                "group_items__field",
                "group_items__security_group",
            )
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        if not request.user.has_perm("netbox_nsm.view_rule"):
            return JsonResponse({"detail": "Forbidden"}, status=403)

        column_key = (request.GET.get("column") or "").strip()
        rule = self._load_rule(pk, prefetch=True)

        if not column_key:
            columns = get_all_column_selections(rule, rule.rulebook)
            return JsonResponse(
                {
                    "column_keys": rules_column_keys_for_rulebook(rule.rulebook),
                    "columns": columns,
                }
            )

        if "::" not in column_key:
            return JsonResponse({"detail": "column required"}, status=400)

        return JsonResponse(
            {
                "column": column_key,
                "selections": get_column_selections(rule, column_key),
            }
        )

    def post(self, request, pk):
        if not request.user.has_perm("netbox_nsm.change_rule"):
            return JsonResponse({"detail": "Forbidden"}, status=403)

        column_key = (request.GET.get("column") or "").strip()

        try:
            body = json.loads(request.body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return JsonResponse({"detail": "Invalid JSON"}, status=400)

        rule = self._load_rule(pk)
        prechange = snapshot_instance(rule)
        rb_prechange = snapshot_instance(rule.rulebook)
        try:
            with ensure_branch_context(request):
                if isinstance(body.get("columns"), dict):
                    save_all_column_selections(
                        rule, body["columns"], rule.rulebook, request=request
                    )
                    record_rule_assignment_changelog(rule, request, prechange)
                    record_rulebook_rules_changelog(rule.rulebook, request, rb_prechange)
                    rule = self._load_rule(pk, prefetch=True)
                    return JsonResponse(
                        {
                            "columns": get_all_column_selections(rule, rule.rulebook),
                            "cells": build_all_column_cells_payload(
                                rule, rule.rulebook
                            ),
                        }
                    )

                if not column_key or "::" not in column_key:
                    return JsonResponse({"detail": "column required"}, status=400)

                selections = body.get("selections")
                if not isinstance(selections, list):
                    return JsonResponse(
                        {"detail": "selections must be a list"}, status=400
                    )

                save_column_selections(rule, column_key, selections, request=request)
                record_rule_assignment_changelog(rule, request, prechange)
                record_rulebook_rules_changelog(rule.rulebook, request, rb_prechange)
            rule = self._load_rule(pk, prefetch=True)
            payload = build_column_cell_payload(rule, rule.rulebook, column_key)
            payload["selections"] = get_column_selections(rule, column_key)
            return JsonResponse(payload)
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)
        except Exception as exc:
            return JsonResponse(
                {"detail": str(exc) or "Save failed"},
                status=500,
            )
