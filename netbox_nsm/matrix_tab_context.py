"""Shared context for Zone Matrix tab views."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.models import RulebookFieldType, TypeConfig
from netbox_nsm.matrix_axis_filter import filter_objects_by_axis_query
from netbox_nsm.matrix_utils import (
    MATRIX_AXIS_MAX,
    dedupe_matrix_object_types,
    apply_default_matrix_axis_filters,
    matrix_axis_display_label,
    matrix_zone_display_label,
    resolve_matrix_object_type_selection,
)
from netbox_nsm.display_utils import get_display_template_map
from netbox_nsm.branch_urls import with_branch_query, wrap_matrix_cell_hrefs


def cap_matrix_axis_zones(
    zones: list, *, limit: int | None = None
) -> tuple[list, bool, int]:
    """Return (capped zones, was_truncated, original_count)."""
    max_count = MATRIX_AXIS_MAX if limit is None else limit
    total = len(zones)
    if total <= max_count:
        return zones, False, total
    return zones[:max_count], True, total


def build_matrix_axis_limit_info(
    *,
    src_total: int,
    dst_total: int,
    src_truncated: bool,
    dst_truncated: bool,
    limit: int = MATRIX_AXIS_MAX,
) -> dict | None:
    if not src_truncated and not dst_truncated:
        return None
    return {
        "limit": limit,
        "src_total": src_total,
        "dst_total": dst_total,
        "src_truncated": src_truncated,
        "dst_truncated": dst_truncated,
    }


def build_matrix_tab_context(
    request,
    instance,
    *,
    view_helpers,
    client_axis_filters: bool = False,
    lazy_grid: bool = False,
    src_row_range: tuple[int, int] | None = None,
) -> dict:
    """Build matrix_rows, filters, and legend for matrix templates."""
    show_obj_type_filter = False
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

    rules_url_base = with_branch_query(
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
    raw_available_types = list(available_types)
    available_types = dedupe_matrix_object_types(raw_available_types)
    show_obj_type_filter = len(available_types) > 1

    sel_ct_id_str = request.GET.get("obj_type", "")
    selected_ct_id = int(sel_ct_id_str) if sel_ct_id_str.isdigit() else None
    selected_ct_id = resolve_matrix_object_type_selection(
        selected_ct_id,
        raw_types=raw_available_types,
        available_types=available_types,
    )

    used_zones_by_pk = {}
    if selected_ct_id is not None:
        try:
            selected_ct = ContentType.objects.get(pk=selected_ct_id)
        except ContentType.DoesNotExist:
            selected_ct = None
        if selected_ct:
            zone_model = selected_ct.model_class()
            used_zone_pks: set[int] = set()
            for rule in rules_qs:
                for item in rule.object_items.all():
                    if item.content_type_id != selected_ct_id:
                        continue
                    used_zone_pks.add(item.object_id)
            if zone_model and used_zone_pks:
                for obj in zone_model.objects.filter(pk__in=used_zone_pks):
                    used_zones_by_pk[obj.pk] = obj

    display_template_map = get_display_template_map()

    def zone_label(zone) -> str:
        return matrix_zone_display_label(zone, selected_ct_id, display_template_map)

    all_zones = sorted(used_zones_by_pk.values(), key=lambda z: zone_label(z).lower())
    zone_labels = {z.pk: zone_label(z) for z in all_zones}
    zone_label_display = {
        pk: matrix_axis_display_label(label) for pk, label in zone_labels.items()
    }

    if client_axis_filters:
        src_q = request.GET.get("src_q", "").strip()
        if src_q:
            all_zones = filter_objects_by_axis_query(all_zones, src_q, zone_label)

    src_filter_pks = set()
    dst_filter_pks = set()
    if not client_axis_filters:
        src_filter_pks = {int(v) for v in request.GET.getlist("src_id") if v.isdigit()}
        dst_filter_pks = {int(v) for v in request.GET.getlist("dst_id") if v.isdigit()}
        src_filter_pks, dst_filter_pks = apply_default_matrix_axis_filters(
            all_zones,
            src_filter_pks=src_filter_pks,
            dst_filter_pks=dst_filter_pks,
        )
    src_zones = (
        [z for z in all_zones if z.pk in src_filter_pks]
        if src_filter_pks
        else all_zones
    )
    dst_zones = (
        [z for z in all_zones if z.pk in dst_filter_pks]
        if dst_filter_pks
        else all_zones
    )

    src_zones, src_truncated, src_total = cap_matrix_axis_zones(src_zones)
    dst_zones, dst_truncated, dst_total = cap_matrix_axis_zones(dst_zones)
    matrix_axis_limit = build_matrix_axis_limit_info(
        src_total=src_total,
        dst_total=dst_total,
        src_truncated=src_truncated,
        dst_truncated=dst_truncated,
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
    build_rows = (not lazy_grid) or (src_row_range is not None)
    if selected_ct_id is not None and build_rows:
        for rule in rules_qs:
            rule._color, rule._action_label = _action_color_label(rule)
        for rule in rules_qs:
            rule_src_pks = set()
            rule_dst_pks = set()
            for item in rule.object_items.all():
                if item.content_type_id != selected_ct_id:
                    continue
                if item.field and item.field.placement == "source":
                    rule_src_pks.add(item.object_id)
                elif item.field and item.field.placement == "destination":
                    rule_dst_pks.add(item.object_id)
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
        "src_field_slug": src_rb_field.slug if src_rb_field else "source",
        "dst_field_slug": dst_rb_field.slug if dst_rb_field else "destination",
    }

    matrix_rows = []
    src_iter = src_zones
    if src_row_range is not None:
        start, end = src_row_range
        src_iter = src_zones[start:end]
    for src in src_iter:
        cells = []
        for dst in dst_zones:
            fwd_rules = cell_map.get((src.pk, dst.pk), [])
            cells.append(
                {
                    "fwd": _badge(fwd_rules),
                    "filter_href": view_helpers._matrix_rules_href(
                        rules_url_base,
                        src_field_name,
                        dst_field_name,
                        src,
                        dst,
                        **matrix_href_kwargs,
                    ),
                    "add_href": with_branch_query(
                        (
                            f"{add_url_base}?rulebook={instance.pk}"
                            f"&prefill_src_ct={selected_ct_id}&prefill_src_obj={src.pk}"
                            f"&prefill_dst_ct={selected_ct_id}&prefill_dst_obj={dst.pk}"
                            f"&return_url={rules_url_base}"
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
        "show_obj_type_filter": show_obj_type_filter,
        "selected_ct_id": selected_ct_id,
        "all_src_zones": all_zones,
        "all_dst_zones": all_zones,
        "src_zones": src_zones,
        "dst_zones": dst_zones,
        "src_filter_pks": src_filter_pks,
        "dst_filter_pks": dst_filter_pks,
        "matrix_rows": matrix_rows,
        "zone_labels": zone_labels,
        "zone_label_display": zone_label_display,
        "action_legend": action_legend,
        "matrix_axis_limit": matrix_axis_limit,
        "matrix_dense": max(len(src_zones), len(dst_zones)) > 40,
    }
