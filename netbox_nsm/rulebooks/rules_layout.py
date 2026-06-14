"""Build NSM rules-table layout/rows from COT rulebook instances."""

from __future__ import annotations

from collections import defaultdict

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.analysis.addr_analysis_utils import object_is_addr_analyzable
from netbox_nsm.rulebooks.templates import _OBJECT_TYPE_LABELS, _field_display_label
from netbox_nsm.core.interface_parent import (
    interface_parent_host_payload,
    prefetch_interface_parents,
)
from netbox_nsm.core.nsm_object_status import get_nsm_object_status
from netbox_nsm.rulebooks.rules_pill_render import DEFAULT_MAX_VISIBLE_PILLS, render_rules_pill_cell

__all__ = (
    "apply_cot_system_field_filters",
    "build_cot_grouped_rules_table_data",
    "build_cot_rules_layout",
    "cot_db_order_fields",
    "cot_field_allowed_object_labels",
    "cot_field_type_display",
    "cot_multiobject_prefetch_plan",
    "cot_object_field_names_from_layout",
    "cot_row_group_object_field_names",
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


def _db_filter_field_name(field: str) -> str | None:
    return _DB_SORT_FIELD_MAP.get(field)


def _enabled_text_filter_q(needle: str, ftype: str):
    from django.db.models import Q

    token = (needle or "").strip().lower()
    if not token:
        return Q()
    on_hit = token in {"on", "enabled", "aktiv", "ein", "true", "1"}
    off_hit = token in {"off", "disabled", "inaktiv", "aus", "false", "0"}
    if on_hit and not off_hit:
        base = Q(status=True)
    elif off_hit and not on_hit:
        base = Q(status=False)
    else:
        return Q()
    if ftype in ("notContains", "notEqual"):
        return ~base
    return base


def _index_text_filter_q(needle: str, ftype: str):
    from django.db.models import CharField, Q
    from django.db.models.functions import Cast

    token = (needle or "").strip()
    if not token:
        return Q()
    if ftype in ("equals", "notEqual"):
        try:
            base = Q(index=int(token))
        except (TypeError, ValueError):
            base = Q(pk__in=[])
        if ftype == "notEqual":
            return ~base
        return base
    lookup = {
        "contains": "icontains",
        "notContains": "icontains",
        "startsWith": "istartswith",
        "endsWith": "iendswith",
    }.get(ftype, "icontains")
    base = Q(**{f"_index_text__{lookup}": token})
    if ftype in ("notContains",):
        return ~base
    return base


def _text_filter_spec_to_q(db_field: str, spec: dict):
    from django.db.models import Q

    if not isinstance(spec, dict):
        return Q()
    operator = (spec.get("operator") or "").upper()
    conditions = spec.get("conditions") or []
    if operator == "OR" and conditions:
        clause = Q()
        for cond in conditions:
            if isinstance(cond, dict):
                clause |= _text_filter_spec_to_q(db_field, cond)
        return clause
    if operator == "AND" and conditions:
        clause = Q()
        for cond in conditions:
            if isinstance(cond, dict):
                clause &= _text_filter_spec_to_q(db_field, cond)
        return clause

    needle = str(spec.get("filter") or "").strip()
    if not needle:
        return Q()
    ftype = spec.get("type") or "contains"
    if db_field == "status":
        return _enabled_text_filter_q(needle, ftype)
    if db_field == "index":
        return _index_text_filter_q(needle, ftype)

    lookup = {
        "contains": f"{db_field}__icontains",
        "notContains": f"{db_field}__icontains",
        "equals": f"{db_field}__iexact",
        "notEqual": f"{db_field}__iexact",
        "startsWith": f"{db_field}__istartswith",
        "endsWith": f"{db_field}__iendswith",
    }.get(ftype, f"{db_field}__icontains")
    base = Q(**{lookup: needle})
    if ftype in ("notContains", "notEqual"):
        return ~base
    return base


def apply_cot_system_field_filters(qs, filter_model: dict | None):
    """Apply system-column quick-search filters at the database layer."""
    from django.db.models import CharField
    from django.db.models.functions import Cast

    if not filter_model:
        return qs
    needs_index_cast = False
    for field, spec in filter_model.items():
        db_field = _db_filter_field_name(field)
        if not db_field or db_field != "index":
            continue
        if isinstance(spec, dict) and (spec.get("type") or "contains") not in (
            "equals",
            "notEqual",
        ):
            needs_index_cast = True
            break
    if needs_index_cast:
        qs = qs.annotate(_index_text=Cast("index", CharField()))
    for field, spec in filter_model.items():
        db_field = _db_filter_field_name(field)
        if not db_field or not isinstance(spec, dict):
            continue
        qs = qs.filter(_text_filter_spec_to_q(db_field, spec))
    return qs


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


def _build_type_config_sort_lookup() -> dict[int, tuple[int, str]]:
    """Map ``content_type_id`` → ``(sort_order, name)`` for layout column ordering."""
    from netbox_nsm.objects.nsm_config import build_nsm_config_lookup

    return {
        config.content_type_id: (config.sort_order, (config.name or "").strip())
        for config in build_nsm_config_lookup().values()
    }


def _sort_key_for_object_type(
    object_type,
    *,
    tc_lookup: dict[int, tuple[int, str]] | None = None,
) -> tuple[int, str, str]:
    from netbox_nsm.objects.type_config_specs import default_sort_order_for_slug

    ct_id = None
    try:
        ct_id = _content_type_for_object_type(object_type).pk
    except ContentType.DoesNotExist:
        pass
    if tc_lookup and ct_id is not None and ct_id in tc_lookup:
        sort_order, name = tc_lookup[ct_id]
        return (sort_order, name, object_type.model)

    cot = _cot_for_object_type(object_type)
    if cot is not None:
        return (
            default_sort_order_for_slug(cot.slug),
            (cot.verbose_name or cot.name or "").strip(),
            object_type.model,
        )
    return (0, _object_type_label(object_type), object_type.model)


def _sorted_related_object_types(
    field,
    *,
    tc_lookup: dict[int, tuple[int, str]] | None = None,
):
    object_types = list(field.related_object_types.all())
    return sorted(
        object_types,
        key=lambda ot: _sort_key_for_object_type(ot, tc_lookup=tc_lookup),
    )


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
        tc_lookup = _build_type_config_sort_lookup()
        for object_type in _sorted_related_object_types(field, tc_lookup=tc_lookup):
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
    address_ct_ids: set[int] | None = None,
) -> dict:
    url = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else "#"
    if ct_cache is not None:
        model_cls = obj.__class__
        if model_cls not in ct_cache:
            ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
        ct_pk = ct_cache[model_cls]
    else:
        ct_pk = ContentType.objects.get_for_model(obj).pk
    status = get_nsm_object_status(obj)
    return {
        "url": url,
        "name": _display_name(obj),
        "color": getattr(obj, "color", "") or "",
        "status": status,
        "excluded": False,
        "ct": ct_pk,
        "pk": getattr(obj, "pk", None),
        "addrAnalyzable": object_is_addr_analyzable(
            obj, ct_pk, address_ct_ids=address_ct_ids
        ),
        **interface_parent_host_payload(obj),
    }


def build_cot_rules_layout(cot) -> dict:
    """Column layout from the COT field schema (same shape as native grouped layout)."""
    from extras.choices import CustomFieldTypeChoices

    fields = list(
        cot.fields.exclude(ui_visible="hidden").order_by("weight", "name")
    )
    tc_lookup = _build_type_config_sort_lookup()
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
            for ot in _sorted_related_object_types(field, tc_lookup=tc_lookup):
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


def cot_row_group_object_field_names(
    group_column: dict,
    filter_model: dict | None,
    *,
    system_fields: frozenset[str],
) -> set[str]:
    """Minimal multi-object fields needed for row-group tab keys and active filters."""
    names: set[str] = set()
    if group_column.get("kind") == "object":
        area = (group_column.get("area_slug") or "").strip()
        if area:
            names.add(area)
        for merged_key in group_column.get("merged_keys") or []:
            merged_area = merged_key.split("::", 1)[0]
            if merged_area:
                names.add(merged_area)
    for field in filter_model or {}:
        if field in system_fields:
            continue
        area = field.split("::", 1)[0]
        if area:
            names.add(area)
    return names


def build_cot_grouped_rules_table_data(
    instances,
    virtual_rb,
    *,
    layout=None,
    object_field_names: set[str] | None = None,
) -> dict:
    if layout is None:
        layout = build_cot_rules_layout(virtual_rb.cot)
    grouped_columns = layout["grouped_columns"]
    if object_field_names is not None:
        grouped_columns = [
            col for col in grouped_columns if col["area_slug"] in object_field_names
        ]
    cot_slug = virtual_rb.slug
    rows = []

    field_names = {col["area_slug"] for col in grouped_columns}
    object_fields = list(
        virtual_rb.cot.fields.filter(name__in=field_names)
    )
    from netbox_nsm.objects.type_config_specs import content_type_ids_for_cot_slugs

    ct_cache: dict = {}
    address_ct_ids = set(
        content_type_ids_for_cot_slugs(["nsm_address", "nsm_address_group"])
    )

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
            prefetch_interface_parents(objs)
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
                            address_ct_ids=address_ct_ids,
                        )
                    )

        cells = {}
        cells_items = {}
        cells_filter = {}
        for key, items in per_key.items():
            cells_items[key] = items
            if object_field_names is None:
                cells[key] = render_rules_pill_cell(
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
