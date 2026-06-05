"""Shared context for Zone Matrix views (classic HTML and AG Grid tab)."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.models import RulebookFieldType, TypeConfig
from netbox_nsm.matrix_grid_payload import matrix_zone_display_label
from netbox_nsm.display_utils import get_display_template_map
from netbox_nsm.branch_urls import with_branch_query, wrap_matrix_cell_hrefs


def build_matrix_tab_context(
    request, instance, *, view_helpers, client_axis_filters: bool = False
) -> dict:
    """Build matrix_rows, filters, and legend for matrix templates."""
    rules_qs = view_helpers._load_rules_qs(instance)

    try:
        action_ct_ids = list(
            TypeConfig.objects.filter(panel_slugs__contains=["action"]).values_list(
                "content_type_id", flat=True
            )
        )
        action_objs = {}
        for ct_id in action_ct_ids:
            try:
                ct = ContentType.objects.get(pk=ct_id)
                model_class = ct.model_class()
                if model_class:
                    for obj in model_class.objects.all():
                        action_objs[obj.pk] = obj
            except Exception:
                pass
    except Exception:
        action_objs = {}

    action_legend = sorted(
        [
            {"name": o.name, "color": getattr(o, "color", "#888888")}
            for o in action_objs.values()
        ],
        key=lambda x: x["name"],
    )

    policy_url_base = with_branch_query(
        reverse(
            "plugins:netbox_nsm:rulebook_rules",
            args=[instance.pk],
        ),
        request,
    )
    add_url_base = reverse("plugins:netbox_nsm:rule_add")

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
            model_class = ct.model_class()
            if model_class is None:
                continue
            label = str(
                getattr(model_class._meta, "verbose_name_plural", ct.model)
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

    display_template_map = get_display_template_map()

    def zone_label(zone) -> str:
        return matrix_zone_display_label(zone, selected_ct_id, display_template_map)

    all_zones = sorted(
        used_zones_by_pk.values(), key=lambda z: zone_label(z).lower()
    )
    zone_labels = {z.pk: zone_label(z) for z in all_zones}

    src_filter_pks = set()
    dst_filter_pks = set()
    if not client_axis_filters:
        src_filter_pks = {int(v) for v in request.GET.getlist("src_id") if v.isdigit()}
        dst_filter_pks = {int(v) for v in request.GET.getlist("dst_id") if v.isdigit()}
    src_zones = (
        [z for z in all_zones if z.pk in src_filter_pks] if src_filter_pks else all_zones
    )
    dst_zones = (
        [z for z in all_zones if z.pk in dst_filter_pks] if dst_filter_pks else all_zones
    )

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
            rule = rules_list[0]
            return {"count": 1, "color": rule._color, "label": rule._action_label}
        return {"count": len(rules_list), "color": None, "label": None}

    def _combined_badge(fwd_rules, rev_rules):
        seen = set()
        merged = []
        for rule in fwd_rules + rev_rules:
            if rule.pk not in seen:
                seen.add(rule.pk)
                merged.append(rule)
        return _badge(merged)

    matrix_mode = request.GET.get("mode", "directed")
    if matrix_mode not in ("undirected", "directed"):
        matrix_mode = "directed"

    src_rb_field = (
        view_helpers._rulebook_field_for_ct(instance, "source", selected_ct_id)
        if selected_ct_id
        else None
    )
    dst_rb_field = (
        view_helpers._rulebook_field_for_ct(instance, "destination", selected_ct_id)
        if selected_ct_id
        else None
    )
    src_field_name = src_rb_field.name if src_rb_field else "Source"
    dst_field_name = dst_rb_field.name if dst_rb_field else "Destination"

    matrix_type_segment = None
    if selected_ct_id:
        tc = TypeConfig.objects.filter(content_type_id=selected_ct_id).first()
        if tc:
            from netbox_nsm.query.engine import type_segment_slug

            matrix_type_segment = tc.name or type_segment_slug(tc)

    matrix_href_kwargs = {
        "zone_content_type_id": selected_ct_id,
        "type_segment": matrix_type_segment,
        "display_template_map": display_template_map,
    }

    matrix_rows = []
    for src in src_zones:
        cells = []
        for dst in dst_zones:
            fwd_rules = cell_map.get((src.pk, dst.pk), [])
            rev_rules = cell_map.get((dst.pk, src.pk), [])
            cells.append(
                {
                    "fwd": _badge(fwd_rules),
                    "rev": _badge(rev_rules),
                    "combined": _combined_badge(fwd_rules, rev_rules),
                    "fwd_href": view_helpers._matrix_policy_href(
                        policy_url_base,
                        src_field_name,
                        dst_field_name,
                        src,
                        dst,
                        **matrix_href_kwargs,
                    ),
                    "rev_href": view_helpers._matrix_policy_href(
                        policy_url_base,
                        src_field_name,
                        dst_field_name,
                        dst,
                        src,
                        **matrix_href_kwargs,
                    ),
                    "both_href": view_helpers._matrix_policy_href(
                        policy_url_base,
                        src_field_name,
                        dst_field_name,
                        src,
                        dst,
                        bidirectional=True,
                        **matrix_href_kwargs,
                    ),
                    "add_href": with_branch_query(
                        (
                            f"{add_url_base}?rulebook={instance.pk}"
                            f"&prefill_src_ct={selected_ct_id}&prefill_src_obj={src.pk}"
                            f"&prefill_dst_ct={selected_ct_id}&prefill_dst_obj={dst.pk}"
                            f"&return_url={policy_url_base}"
                        ),
                        request,
                    ),
                    "is_self": src.pk == dst.pk,
                }
            )
        wrap_matrix_cell_hrefs(cells, request)
        matrix_rows.append({"source_zone": src, "cells": cells})

    return {
        "available_types": available_types,
        "selected_ct_id": selected_ct_id,
        "all_src_zones": all_zones,
        "all_dst_zones": all_zones,
        "src_zones": src_zones,
        "dst_zones": dst_zones,
        "src_filter_pks": src_filter_pks,
        "dst_filter_pks": dst_filter_pks,
        "matrix_rows": matrix_rows,
        "zone_labels": zone_labels,
        "action_legend": action_legend,
        "matrix_mode": matrix_mode,
    }
