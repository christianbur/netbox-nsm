"""Build NSM rules-table layout/rows from COT rulebook instances."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.analysis.addr_analysis_utils import _object_is_addr_analyzable
from netbox_nsm.models.type_config import TypeConfig
from netbox_nsm.rulebooks.templates import _OBJECT_TYPE_LABELS, _field_display_label
from netbox_nsm.rulebooks.cell_render import DEFAULT_MAX_VISIBLE_PILLS, _render_rules_cell

__all__ = (
    "build_cot_grouped_rules_table_data",
    "build_cot_rules_layout",
    "cot_db_order_fields",
    "cot_field_allowed_object_labels",
    "cot_field_type_display",
    "cot_multiobject_prefetch_plan",
    "cot_object_field_names_from_layout",
    "cot_rule_instances_queryset",
    "prefetch_cot_multiobject_fields",
)

_SYSTEM_FIELD_MAP = {
    "index": "index",
    "status": "status",
    "name": "name",
    "description": "description",
}


_DB_SORT_FIELD_MAP = {
    "index": "index",
    "name": "name",
    "enabled": "status",
    "status": "status",
    "description": "description",
}


def cot_object_field_names_from_layout(layout: dict) -> list[str]:
    """Multi-object field names referenced by the rules table layout."""
    return sorted(
        {col["area_slug"] for col in (layout.get("grouped_columns") or [])}
    )


def cot_db_order_fields(sort_field: str, sort_order: str) -> list[str]:
    """Map rules-tab sort params to ORM ``order_by`` fields."""
    db_field = _DB_SORT_FIELD_MAP.get(sort_field, "index")
    prefix = "-" if sort_order == "desc" else ""
    return [f"{prefix}{db_field}", f"{prefix}pk"]


_PREFETCHED_M2M_ATTR = "_nsm_prefetched_m2m"


def cot_multiobject_prefetch_plan(virtual_rb, layout: dict) -> list[str]:
    """Multi-object field names referenced by the rules table layout."""
    return cot_object_field_names_from_layout(layout)


def _attach_prefetched_m2m(instances, field_name: str, by_source: dict[int, list]) -> None:
    for inst in instances:
        cache = getattr(inst, _PREFETCHED_M2M_ATTR, None)
        if cache is None:
            cache = {}
            setattr(inst, _PREFETCHED_M2M_ATTR, cache)
        cache[field_name] = by_source.get(inst.pk, [])


def _prefetch_standard_m2m_field(instances, field) -> None:
    from django.apps import apps
    from netbox_custom_objects.constants import APP_LABEL

    through = apps.get_model(APP_LABEL, field.through_model_name)
    instance_pks = [inst.pk for inst in instances]
    rows = list(
        through.objects.filter(source_id__in=instance_pks)
        .values_list("source_id", "target_id", "id")
        .order_by("source_id", "id")
    )
    target_ids = {target_id for _, target_id, _row_id in rows}
    model_class = field.related_object_type.model_class()
    if model_class is None:
        return
    obj_map = {
        obj.pk: obj for obj in model_class.objects.filter(pk__in=target_ids)
    }
    by_source: dict[int, list] = defaultdict(list)
    for source_id, target_id, _row_id in rows:
        obj = obj_map.get(target_id)
        if obj is not None:
            by_source[source_id].append(obj)
    _attach_prefetched_m2m(instances, field.name, by_source)


def _prefetch_polymorphic_m2m_field(instances, field) -> None:
    from django.apps import apps
    from netbox_custom_objects.constants import APP_LABEL

    through = apps.get_model(APP_LABEL, field.through_model_name)
    instance_pks = [inst.pk for inst in instances]
    rows = list(
        through.objects.filter(source_id__in=instance_pks)
        .values_list("source_id", "content_type_id", "object_id", "id")
        .order_by("source_id", "id")
    )
    by_ct: dict[int, set[int]] = defaultdict(set)
    for _source_id, ct_id, obj_id, _row_id in rows:
        by_ct[ct_id].add(obj_id)

    obj_map: dict[tuple[int, int], object] = {}
    for ct_id, obj_ids in by_ct.items():
        ct = ContentType.objects.get_for_id(ct_id)
        model_class = ct.model_class()
        if model_class is None:
            continue
        for obj in model_class.objects.filter(pk__in=obj_ids):
            obj_map[(ct_id, obj.pk)] = obj

    by_source: dict[int, list] = defaultdict(list)
    for source_id, ct_id, obj_id, _row_id in rows:
        obj = obj_map.get((ct_id, obj_id))
        if obj is not None:
            by_source[source_id].append(obj)

    by_source_sorted = {
        source_id: sorted(objs, key=str) for source_id, objs in by_source.items()
    }
    _attach_prefetched_m2m(instances, field.name, by_source_sorted)


def prefetch_cot_multiobject_fields(
    instances,
    virtual_rb,
    field_names: list[str],
) -> None:
    """Bulk-load multi-object field values (custom M2M is not Django-prefetchable)."""
    if not instances or not field_names:
        return

    from extras.choices import CustomFieldTypeChoices

    fields = list(
        virtual_rb.cot.fields.filter(
            name__in=field_names,
            type=CustomFieldTypeChoices.TYPE_MULTIOBJECT,
        )
    )
    for field in fields:
        if field.is_polymorphic:
            _prefetch_polymorphic_m2m_field(instances, field)
        else:
            _prefetch_standard_m2m_field(instances, field)


def cot_rule_instances_queryset(virtual_rb):
    model = virtual_rb.cot.get_model()
    return model.objects.all()


def _cot_for_object_type(object_type):
    import re

    from netbox_custom_objects.models import CustomObjectType

    if object_type.app_label != "netbox_custom_objects":
        return None
    match = re.match(r"table(\d+)model", object_type.model, re.IGNORECASE)
    if not match:
        return None
    return CustomObjectType.objects.filter(pk=int(match.group(1))).first()


def _object_type_label(object_type) -> str:
    """Label for a ``core.ObjectType`` row."""
    cot = _cot_for_object_type(object_type)
    if cot is not None:
        key = f"custom-objects/{cot.slug}"
        if key in _OBJECT_TYPE_LABELS:
            return _OBJECT_TYPE_LABELS[key]
        return cot.verbose_name or cot.name
    key = f"{object_type.app_label}/{object_type.model}"
    return _OBJECT_TYPE_LABELS.get(key, object_type.model.replace("_", " ").title())


def cot_field_allowed_object_labels(field) -> list[str]:
    """Human-readable allowed object types for a COT field (wizard-style labels)."""
    from extras.choices import CustomFieldTypeChoices

    if field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
        return []
    labels: list[str] = []
    if field.is_polymorphic:
        for object_type in field.related_object_types.all():
            labels.append(_object_type_label(object_type))
    elif field.related_object_type_id:
        labels.append(_object_type_label(field.related_object_type))
    return labels


def cot_field_type_display(field) -> str:
    """Human-readable field type, including allowed object types for multi-object fields."""
    type_label = field.get_type_display()
    allowed = cot_field_allowed_object_labels(field)
    if not allowed:
        return type_label
    return f"{type_label} ({', '.join(allowed)})"


def _content_type_for_object_type(object_type) -> ContentType:
    return ContentType.objects.get(
        app_label=object_type.app_label,
        model=object_type.model,
    )


def _display_name(obj) -> str:
    if hasattr(obj, "render_display"):
        return str(obj.render_display())
    return str(getattr(obj, "name", obj))


def _object_item_dict(
    obj,
    *,
    ct_cache: dict | None = None,
    matching_class_map: dict | None = None,
) -> dict:
    url = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "#"
    if ct_cache is not None:
        model_cls = obj.__class__
        if model_cls not in ct_cache:
            ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
        ct_pk = ct_cache[model_cls]
    else:
        ct_pk = ContentType.objects.get_for_model(obj).pk
    return {
        "url": url,
        "name": _display_name(obj),
        "color": getattr(obj, "color", "") or "",
        "excluded": False,
        "ct": ct_pk,
        "pk": getattr(obj, "pk", None),
        "addrAnalyzable": _object_is_addr_analyzable(
            obj, ct_pk, matching_class_map=matching_class_map
        ),
    }


def build_cot_rules_layout(cot) -> dict:
    """Column layout from the COT field schema (same shape as native grouped layout)."""
    from extras.choices import CustomFieldTypeChoices

    fields = list(
        cot.fields.exclude(ui_visible="hidden").order_by("weight", "name")
    )
    rules_layout = []
    header_groups = []
    grouped_columns = []
    group_idx = 0

    for field in fields:
        if field.name in _SYSTEM_FIELD_MAP:
            rules_layout.append(
                {
                    "kind": "system",
                    "slug": _SYSTEM_FIELD_MAP[field.name],
                    "label": field.label or field.name,
                }
            )
            continue

        if field.type != CustomFieldTypeChoices.TYPE_MULTIOBJECT:
            continue

        types = []
        if field.is_polymorphic:
            for ot in field.related_object_types.all():
                ct = _content_type_for_object_type(ot)
                types.append((f"ct_{ct.pk}", _object_type_label(ot)))
        elif field.related_object_type_id:
            ot = field.related_object_type
            ct = _content_type_for_object_type(ot)
            types.append((f"ct_{ct.pk}", _object_type_label(ot)))

        if not types:
            continue

        cols = []
        field_slug = field.name
        field_label = field.label or field.name.replace("_", " ").title()
        field_group = (field.group_name or "").strip()
        display_label = _field_display_label(
            {"label": field_label, "group_name": field_group},
            cot=cot,
        )
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

        group = {
            "label": display_label,
            "field_label": field_label,
            "field_group": field_group,
            "slug": field_slug,
            "is_polymorphic": field.is_polymorphic,
            "columns": cols,
        }
        for idx, col in enumerate(cols):
            col["is_group_start"] = idx == 0
            col["is_group_end"] = idx == len(cols) - 1
            col["group_band"] = "odd" if (group_idx % 2) else "even"
        header_groups.append(group)
        rules_layout.append(
            {
                "kind": "object",
                "slug": field_slug,
                "label": display_label,
                "field_label": field_label,
                "field_group": field_group,
                "is_polymorphic": field.is_polymorphic,
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

    return {
        "rules_layout": rules_layout,
        "header_groups": header_groups,
        "column_count": len(grouped_columns),
        "total_column_count": col_index + 1,
        "grouped_columns": grouped_columns,
    }


def _cot_edit_url(cot_slug: str, pk: int) -> str:
    return reverse(
        "plugins:netbox_custom_objects:customobject_edit",
        kwargs={"custom_object_type": cot_slug, "pk": pk},
    )


def _cot_delete_url(cot_slug: str, pk: int) -> str:
    return reverse(
        "plugins:netbox_custom_objects:customobject_delete",
        kwargs={"custom_object_type": cot_slug, "pk": pk},
    )


def _cot_detail_url(cot_slug: str, pk: int) -> str:
    return reverse(
        "plugins:netbox_custom_objects:customobject",
        kwargs={"custom_object_type": cot_slug, "pk": pk},
    )


def build_cot_grouped_rules_table_data(instances, virtual_rb, *, layout=None) -> dict:
    if layout is None:
        layout = build_cot_rules_layout(virtual_rb.cot)
    grouped_columns = layout["grouped_columns"]
    cot_slug = virtual_rb.slug
    rows = []

    object_field_names = {col["area_slug"] for col in grouped_columns}
    object_fields = list(
        virtual_rb.cot.fields.filter(name__in=object_field_names)
    )
    ct_cache: dict = {}
    matching_class_map = {
        tc.content_type_id: tc.matching_class
        for tc in TypeConfig.objects.only("content_type_id", "matching_class")
    }

    for instance in instances:
        per_key = {col["key"]: [] for col in grouped_columns}

        for field in object_fields:
            prefetched = getattr(instance, _PREFETCHED_M2M_ATTR, {})
            if field.name in prefetched:
                objs = prefetched[field.name]
            else:
                related = getattr(instance, field.name, None)
                if related is None:
                    continue
                objs = related.all() if hasattr(related, "all") else []
            for obj in objs:
                model_cls = obj.__class__
                if model_cls not in ct_cache:
                    ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
                key = f"{field.name}::ct_{ct_cache[model_cls]}"
                if key in per_key:
                    per_key[key].append(
                        _object_item_dict(
                            obj,
                            ct_cache=ct_cache,
                            matching_class_map=matching_class_map,
                        )
                    )

        cells = {}
        cells_items = {}
        cells_filter = {}
        for key, items in per_key.items():
            cells_items[key] = items
            cells[key] = _render_rules_cell(
                items, max_pills=DEFAULT_MAX_VISIBLE_PILLS, colored=True
            )
            cells_filter[key] = " ".join(item["name"] for item in items)

        index_val = getattr(instance, "index", None)
        status_val = bool(getattr(instance, "status", True))
        name_val = getattr(instance, "name", "") or ""
        desc_val = getattr(instance, "description", "") or "-"
        pk = instance.pk

        rows.append(
            {
                "pk": pk,
                "index": index_val,
                "enabled": status_val,
                "name": name_val,
                "url": _cot_detail_url(cot_slug, pk),
                "description": desc_val or "-",
                "edit_url": _cot_edit_url(cot_slug, pk),
                "delete_url": _cot_delete_url(cot_slug, pk),
                "system": {
                    "index": index_val,
                    "enabled": status_val,
                    "name": name_val,
                    "url": _cot_detail_url(cot_slug, pk),
                    "description": desc_val or "-",
                },
                "cells": cells,
                "cells_items": cells_items,
                "cells_filter": cells_filter,
            }
        )

    layout["rows"] = rows
    return layout
