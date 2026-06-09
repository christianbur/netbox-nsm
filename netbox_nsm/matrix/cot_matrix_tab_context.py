"""Matrix tab context for COT-backed rulebooks (source_zones × destination_zones)."""

from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlencode

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.core.branch_urls import with_branch_query, wrap_matrix_cell_hrefs
from netbox_nsm.core.display_utils import get_display_template_map
from netbox_nsm.matrix.matrix_axis_filter import filter_objects_by_axis_query
from netbox_nsm.matrix.matrix_utils import (
    MATRIX_AXIS_MAX,
    apply_default_matrix_axis_filters,
    dedupe_matrix_object_types,
    matrix_axis_display_label,
    matrix_zone_display_label,
    resolve_matrix_object_type_selection,
)
from netbox_nsm.rulebooks.rules_layout import (
    _PREFETCHED_M2M_ATTR,
    _content_type_for_object_type,
    _object_type_label,
    cot_rule_instances_queryset,
    prefetch_cot_multiobject_fields,
)
from netbox_nsm.security.object_rules import build_matrix_cell_rules_filter_url

__all__ = (
    "MATRIX_DST_FIELD",
    "MATRIX_SRC_FIELD",
    "build_cot_matrix_tab_context",
    "build_matrix_cell_add_href",
    "cot_rulebook_matrix_capable",
    "cot_rulebook_matrix_enabled",
)

MATRIX_SRC_FIELD = "source_zones"
MATRIX_DST_FIELD = "destination_zones"
_MATRIX_PREFETCH_FIELDS = (MATRIX_SRC_FIELD, MATRIX_DST_FIELD, "actions")


def cot_rulebook_matrix_capable(cot) -> bool:
    """True when the COT schema has source and destination zone columns."""
    names = set(cot.fields.values_list("name", flat=True))
    return MATRIX_SRC_FIELD in names and MATRIX_DST_FIELD in names


def cot_rulebook_matrix_enabled(cot) -> bool:
    """True when the rulebook supports a matrix and the tab is not disabled."""
    if not cot_rulebook_matrix_capable(cot):
        return False
    from netbox_nsm.rulebooks.cot_hierarchy import get_cot_matrix_tab_enabled

    return get_cot_matrix_tab_enabled(cot.slug)


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


def _field_content_type_entries(field) -> list[dict]:
    from extras.choices import CustomFieldTypeChoices

    if field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return []
    entries: list[dict] = []
    if field.is_polymorphic:
        for ot in field.related_object_types.all():
            ct = _content_type_for_object_type(ot)
            entries.append({"ct_id": ct.pk, "label": _object_type_label(ot)})
    elif field.related_object_type_id:
        ot = field.related_object_type
        ct = _content_type_for_object_type(ot)
        entries.append({"ct_id": ct.pk, "label": _object_type_label(ot)})
    return entries


def _matrix_available_types(cot) -> list[dict]:
    fields = {
        field.name: field
        for field in cot.fields.filter(name__in=(MATRIX_SRC_FIELD, MATRIX_DST_FIELD))
    }
    if len(fields) != 2:
        return []
    dst_ct_ids = {entry["ct_id"] for entry in _field_content_type_entries(fields[MATRIX_DST_FIELD])}
    return [
        entry
        for entry in _field_content_type_entries(fields[MATRIX_SRC_FIELD])
        if entry["ct_id"] in dst_ct_ids
    ]


def _action_legend() -> list[dict]:
    try:
        from netbox_custom_objects.models import CustomObjectType

        action_cot = CustomObjectType.objects.filter(slug="nsm_action").first()
        if action_cot is None:
            return []
        model = action_cot.get_model()
        return sorted(
            [
                {
                    "name": getattr(obj, "name", str(obj)),
                    "color": getattr(obj, "color", "#888888") or "#888888",
                }
                for obj in model.objects.all()
            ],
            key=lambda row: row["name"],
        )
    except Exception:
        return []


def _action_color_label(rule) -> tuple[str, str]:
    prefetched = getattr(rule, _PREFETCHED_M2M_ATTR, {})
    if "actions" in prefetched:
        objs = prefetched["actions"]
    else:
        actions = getattr(rule, "actions", None)
        if actions is None:
            return "#888888", "?"
        objs = list(actions.all()) if hasattr(actions, "all") else []
    if not objs:
        return "#888888", "?"
    obj = objs[0]
    return getattr(obj, "color", None) or "#888888", getattr(obj, "name", str(obj))


def build_matrix_cell_add_href(
    add_url_base: str,
    rules_url_base: str,
    *,
    source_zone_pk: int,
    destination_zone_pk: int,
    request,
) -> str:
    """Add-rule URL with matrix row/column zones and return_url pre-filled."""
    query = urlencode(
        {
            "return_url": rules_url_base,
            "source_zone": source_zone_pk,
            "destination_zone": destination_zone_pk,
        }
    )
    return with_branch_query(f"{add_url_base}?{query}", request)


def _related_pks(
    rule,
    field_name: str,
    selected_ct_id: int,
    *,
    ct_cache: dict | None = None,
) -> set[int]:
    prefetched = getattr(rule, _PREFETCHED_M2M_ATTR, {})
    if field_name in prefetched:
        objs = prefetched[field_name]
    else:
        related = getattr(rule, field_name, None)
        if related is None:
            return set()
        objs = related.all() if hasattr(related, "all") else []

    pks: set[int] = set()
    for obj in objs:
        model_cls = obj.__class__
        if ct_cache is not None:
            if model_cls not in ct_cache:
                ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
            ct_pk = ct_cache[model_cls]
        else:
            ct_pk = ContentType.objects.get_for_model(obj).pk
        if ct_pk == selected_ct_id:
            pks.add(obj.pk)
    return pks


def build_cot_matrix_tab_context(
    request,
    virtual_rb,
    *,
    client_axis_filters: bool = False,
) -> dict:
    """Build matrix_rows, filters, and legend for COT matrix templates."""
    cot = virtual_rb.cot
    if not cot_rulebook_matrix_enabled(cot):
        return {
            "available_types": [],
            "show_obj_type_filter": False,
            "selected_ct_id": None,
            "matrix_rows": [],
            "action_legend": [],
        }

    rules_qs = list(
        cot_rule_instances_queryset(virtual_rb).order_by("index", "pk")
    )
    prefetch_cot_multiobject_fields(rules_qs, virtual_rb, list(_MATRIX_PREFETCH_FIELDS))
    action_legend = _action_legend()

    rules_url_base = with_branch_query(
        reverse(
            "plugins:netbox_nsm:cot_rulebook_rules",
            kwargs={"slug": virtual_rb.slug},
        ),
        request,
    )
    add_url_base = reverse(
        "plugins:netbox_custom_objects:customobject_add",
        kwargs={"custom_object_type": virtual_rb.slug},
    )

    raw_available_types = _matrix_available_types(cot)
    available_types = dedupe_matrix_object_types(raw_available_types)

    sel_ct_id_str = request.GET.get("obj_type", "")
    selected_ct_id = int(sel_ct_id_str) if sel_ct_id_str.isdigit() else None
    selected_ct_id = resolve_matrix_object_type_selection(
        selected_ct_id,
        raw_types=raw_available_types,
        available_types=available_types,
    )

    used_zones_by_pk: dict[int, object] = {}
    ct_cache: dict = {}
    if selected_ct_id is not None:
        try:
            selected_ct = ContentType.objects.get(pk=selected_ct_id)
        except ContentType.DoesNotExist:
            selected_ct = None
        if selected_ct:
            zone_model = selected_ct.model_class()
            used_zone_pks: set[int] = set()
            for rule in rules_qs:
                used_zone_pks.update(
                    _related_pks(
                        rule,
                        MATRIX_SRC_FIELD,
                        selected_ct_id,
                        ct_cache=ct_cache,
                    )
                )
                used_zone_pks.update(
                    _related_pks(
                        rule,
                        MATRIX_DST_FIELD,
                        selected_ct_id,
                        ct_cache=ct_cache,
                    )
                )
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

    src_filter_pks: set[int] = set()
    dst_filter_pks: set[int] = set()
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

    cell_map: dict[tuple[int | None, int | None], list] = defaultdict(list)
    if selected_ct_id is not None:
        for rule in rules_qs:
            rule._color, rule._action_label = _action_color_label(rule)
            rule_src_pks = _related_pks(
                rule,
                MATRIX_SRC_FIELD,
                selected_ct_id,
                ct_cache=ct_cache,
            )
            rule_dst_pks = _related_pks(
                rule,
                MATRIX_DST_FIELD,
                selected_ct_id,
                ct_cache=ct_cache,
            )
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

    matrix_rows = []
    for src in src_zones:
        cells = []
        for dst in dst_zones:
            fwd_rules = cell_map.get((src.pk, dst.pk), [])
            filter_href = build_matrix_cell_rules_filter_url(
                rules_url_base,
                src_column_key=MATRIX_SRC_FIELD,
                dst_column_key=MATRIX_DST_FIELD,
                src_filter=zone_label(src),
                dst_filter=zone_label(dst),
            )
            cells.append(
                {
                    "fwd": _badge(fwd_rules),
                    "filter_href": filter_href,
                    "add_href": build_matrix_cell_add_href(
                        add_url_base,
                        rules_url_base,
                        source_zone_pk=src.pk,
                        destination_zone_pk=dst.pk,
                        request=request,
                    ),
                    "is_self": src.pk == dst.pk,
                }
            )
        wrap_matrix_cell_hrefs(cells, request)
        matrix_rows.append({"source_zone": src, "cells": cells})

    return {
        "available_types": available_types,
        "show_obj_type_filter": len(available_types) > 1,
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
