"""Build NSM rules-table layout/rows from COT rulebook instances."""

from __future__ import annotations

from collections import defaultdict
import re

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from netbox_nsm.analyzers.ip_analyzer.ip_analyzer_utils import object_is_addr_analyzable
from netbox_nsm.core.display_template import render_display_template
from netbox_nsm.rulebooks.templates import _OBJECT_TYPE_LABELS, _field_display_label
from netbox_nsm.core.interface_parent import (
    interface_parent_host_payload,
    prefetch_interface_parents,
)
from netbox_nsm.core.nsm_object_status import get_nsm_object_status
from netbox_nsm.rulebooks.rules_pill_render import DEFAULT_MAX_VISIBLE_PILLS, render_rules_pill_cell
from netbox_nsm.type_metadata.menus import cot_has_menu

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


def _is_multiobject_field_type(field_type) -> bool:
    try:
        from extras.choices import CustomFieldTypeChoices

        return field_type == CustomFieldTypeChoices.TYPE_MULTIOBJECT
    except Exception:
        return str(field_type or "").strip().lower() == "multiobject"


def _is_object_field_type(field_type) -> bool:
    try:
        from extras.choices import CustomFieldTypeChoices

        return field_type == CustomFieldTypeChoices.TYPE_OBJECT
    except Exception:
        return str(field_type or "").strip().lower() == "object"


def _template_references_field(template: str, field_name: str) -> bool:
    # Match patterns like {{ target }} or {{ target|... }} with optional whitespace.
    pattern = r"\{\{\s*" + re.escape(field_name) + r"\s*(?:\||\}\})"
    return re.search(pattern, template or "") is not None


def _related_object_type_label(related_obj, ct_id: int | None = None) -> str:
    cot = getattr(related_obj, "custom_object_type", None)
    if cot is not None:
        label = (getattr(cot, "verbose_name", None) or getattr(cot, "name", None) or "").strip()
        if label:
            return label
    if ct_id is not None:
        from netbox_nsm.type_metadata.config import resolve_nsm_config_for_content_type

        cfg = resolve_nsm_config_for_content_type(ct_id)
        if cfg and (cfg.name or "").strip():
            return cfg.name.strip()
    return related_obj.__class__.__name__.replace("_", " ").strip() or "Object"


def _related_object_url(related_obj) -> str:
    cot = getattr(related_obj, "custom_object_type", None)
    slug = getattr(cot, "slug", None) if cot is not None else None
    if slug and cot_has_menu(cot, "objects"):
        from netbox_nsm.objects.cot_routes import nsm_object_reverse

        return nsm_object_reverse(None, slug, pk=getattr(related_obj, "pk", None))
    if hasattr(related_obj, "get_absolute_url"):
        try:
            return related_obj.get_absolute_url() or ""
        except Exception:
            return ""
    return ""


def _render_polymorphic_multiobject_items(
    obj,
    field_name: str,
    field,
    *,
    include_links: bool,
) -> list[dict[str, str]]:
    related = getattr(obj, field_name, None)
    if related is None:
        return [{"name": "-"}]
    try:
        refs = list(related.all()) if hasattr(related, "all") else list(related)
    except Exception:
        return [{"name": "-"}]
    if not refs:
        return [{"name": "-"}]

    from netbox_nsm.core.display_utils import get_display_template_map, render_object_display

    tmpl_map = get_display_template_map()
    ct_cache: dict[type, int | None] = {}
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    field_label = (getattr(field, "label", None) or field_name.replace("_", " ").title()).strip()

    for ref_obj in refs:
        if ref_obj is None:
            continue
        model_cls = ref_obj.__class__
        if model_cls not in ct_cache:
            try:
                ct_cache[model_cls] = ContentType.objects.get_for_model(ref_obj).pk
            except Exception:
                ct_cache[model_cls] = None
        ct_id = ct_cache[model_cls]
        if ct_id is None:
            rendered = str(ref_obj)
            type_label = _related_object_type_label(ref_obj, None)
        else:
            rendered = render_object_display(ref_obj, ct_id, tmpl_map)
            type_label = _related_object_type_label(ref_obj, ct_id)
        url = _related_object_url(ref_obj) if include_links else ""
        title = f"{type_label} ({field_label})"
        if title not in grouped:
            grouped[title] = []
            order.append(title)
        grouped[title].append({"name": rendered, "url": url})

    items: list[dict[str, str]] = []
    for title in order:
        items.append({"name": title, "group_label": True})
        for value in grouped.get(title) or []:
            item = {"name": value.get("name") or "", "group_item": True}
            if value.get("url"):
                item["url"] = value["url"]
            items.append(item)
    return items or [{"name": "-"}]


def _extra_column_render_items(
    obj,
    value_template: str,
    *,
    include_links: bool,
) -> list[dict[str, str]]:
    rendered = render_display_template(obj, value_template or "{{ name }}")
    text = str(rendered or "").strip()
    if not text:
        return [{"name": "-"}]

    field_objects = getattr(obj, "_field_objects", None)
    if not isinstance(field_objects, dict) or not field_objects:
        return [{"name": text}]

    uses_multiobject = False
    referenced_multiobject_fields: list[tuple[str, object]] = []
    referenced_object_fields: list[tuple[str, object]] = []
    for field_info in field_objects.values():
        field_name = str(field_info.get("name") or "").strip()
        field = field_info.get("field")
        if not field_name or field is None:
            continue
        field_type = getattr(field, "type", None)
        if _is_object_field_type(field_type) and _template_references_field(
            value_template or "", field_name
        ):
            referenced_object_fields.append((field_name, field))
        if not _is_multiobject_field_type(getattr(field, "type", None)):
            continue
        if _template_references_field(value_template or "", field_name):
            uses_multiobject = True
            referenced_multiobject_fields.append((field_name, field))

    if len(referenced_object_fields) == 1:
        field_name, _field = referenced_object_fields[0]
        related_obj = getattr(obj, field_name, None)
        if related_obj is not None:
            item = {"name": text}
            if include_links:
                url = _related_object_url(related_obj)
                if url:
                    item["url"] = url
            return [item]

    if not uses_multiobject:
        return [{"name": text}]

    if len(referenced_multiobject_fields) == 1:
        field_name, field = referenced_multiobject_fields[0]
        if bool(getattr(field, "is_polymorphic", False)):
            return _render_polymorphic_multiobject_items(
                obj,
                field_name,
                field,
                include_links=include_links,
            )

    parts = [part.strip() for part in text.split(",") if part and part.strip()]
    if len(parts) <= 1:
        return [{"name": text}]
    return [{"name": part} for part in parts]


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
    from netbox_nsm.core.cot_m2m_through import (
        field_uses_polymorphic_through,
        get_field_through_model,
        read_m2m_ref_pairs,
    )

    if not field_uses_polymorphic_through(field):
        return _prefetch_standard_m2m_field(instances, field)

    through = get_field_through_model(field)
    if through is None:
        return
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


def _build_type_config_sort_lookup(*, rulebook_cot=None) -> dict[int, tuple[int, str]]:
    """Map ``content_type_id`` → ``(sort_order, name)`` for layout column ordering."""
    from netbox_nsm.type_metadata.config import build_nsm_config_lookup

    return {
        config.content_type_id: (config.sort_order, (config.name or "").strip())
        for config in build_nsm_config_lookup(rulebook_cot=rulebook_cot).values()
    }


def _build_type_config_columns_lookup(*, rulebook_cot=None) -> dict[int, list[dict]]:
    """Map ``content_type_id`` → normalized extra rule-view columns."""
    from netbox_nsm.type_metadata.config import build_nsm_config_lookup

    return {
        config.content_type_id: list(config.columns or [])
        for config in build_nsm_config_lookup(rulebook_cot=rulebook_cot).values()
        if config.columns
    }


def _sort_key_for_object_type(
    object_type,
    *,
    tc_lookup: dict[int, tuple[int, str]] | None = None,
) -> tuple[int, str, str]:
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
        from netbox_nsm.type_metadata.config import resolve_nsm_config_for_cot

        resolved = resolve_nsm_config_for_cot(cot)
        sort_order = resolved.sort_order if resolved else 0
        return (
            sort_order,
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


def _display_name(
    obj,
    *,
    ct_pk: int | None = None,
    tmpl_map: dict | None = None,
) -> str:
    raw_name = str(getattr(obj, "name", obj))
    render_display_value = None
    if hasattr(obj, "render_display"):
        try:
            render_display_value = str(obj.render_display())
        except Exception:
            render_display_value = None

    if ct_pk is None:
        try:
            ct_pk = ContentType.objects.get_for_model(obj).pk
        except Exception:
            ct_pk = None

    render_object_display_value = None
    if ct_pk is not None:
        from netbox_nsm.core.display_utils import (
            get_display_template_map,
            render_object_display,
        )

        if tmpl_map is None:
            tmpl_map = get_display_template_map()
        render_object_display_value = render_object_display(obj, ct_pk, tmpl_map)

    if render_object_display_value:
        return render_object_display_value
    if render_display_value:
        return render_display_value
    return raw_name


def _object_item_dict(
    obj,
    *,
    ct_cache: dict | None = None,
    address_ct_ids: set[int] | None = None,
    include_links: bool = True,
    tmpl_map: dict | None = None,
) -> dict:
    if not include_links:
        ct_pk = None
        if ct_cache is not None:
            model_cls = obj.__class__
            if model_cls not in ct_cache:
                ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
            ct_pk = ct_cache[model_cls]
        display_name = _display_name(obj, ct_pk=ct_pk, tmpl_map=tmpl_map)
        return {"name": display_name}

    cot = getattr(obj, "custom_object_type", None)
    slug = getattr(cot, "slug", None) if cot is not None else None
    if slug and cot_has_menu(cot, "objects"):
        from netbox_nsm.objects.cot_routes import nsm_object_reverse

        url = nsm_object_reverse(None, slug, pk=getattr(obj, "pk", None))
    elif hasattr(obj, "get_absolute_url"):
        url = obj.get_absolute_url()
    else:
        url = "#"
    if ct_cache is not None:
        model_cls = obj.__class__
        if model_cls not in ct_cache:
            ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
        ct_pk = ct_cache[model_cls]
    else:
        ct_pk = ContentType.objects.get_for_model(obj).pk
    status = get_nsm_object_status(obj)
    display_name = _display_name(obj, ct_pk=ct_pk, tmpl_map=tmpl_map)
    return {
        "url": url,
        "name": display_name,
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
    tc_lookup = _build_type_config_sort_lookup(rulebook_cot=cot)
    tc_columns_lookup = _build_type_config_columns_lookup(rulebook_cot=cot)
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
            field_label = field.label or field.name.replace("_", " ").title()
            field_group = (field.group_name or "").strip()
            display_label = _field_display_label(
                {"label": field_label, "group_name": field_group},
                cot=cot,
            )
            rules_layout.append(
                {
                    "kind": "field",
                    "slug": field.name,
                    "label": display_label,
                    "field_label": field_label,
                    "field_group": field_group,
                    "field_type": field.type,
                }
            )
            continue

        types = []
        if field.is_polymorphic:
            for ot in _sorted_related_object_types(field, tc_lookup=tc_lookup):
                ct = _content_type_for_object_type(ot)
                types.append((f"ct_{ct.pk}", _object_type_label(ot), ct.pk))
        elif field.related_object_type_id:
            ot = field.related_object_type
            ct = _content_type_for_object_type(ot)
            types.append((f"ct_{ct.pk}", _object_type_label(ot), ct.pk))

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
        for type_key, type_label, type_ct_id in types:
            key = f"{field_slug}::{type_key}"
            col_def = {
                "key": key,
                "label": type_label,
                "area_slug": field_slug,
                "type_name": type_key,
            }
            cols.append(col_def)
            grouped_columns.append(col_def)

            for extra in tc_columns_lookup.get(type_ct_id, []):
                extra_key = f"{key}::col_{extra['key']}"
                extra_def = {
                    "key": extra_key,
                    "label": extra["label"],
                    "area_slug": field_slug,
                    "type_name": type_key,
                    "source_key": key,
                    "column_key": extra["key"],
                    "column_order": int(extra.get("column_order", 0)),
                    "value_template": extra["value_template"],
                    "show_colored_pills": False,
                }
                cols.append(extra_def)
                grouped_columns.append(extra_def)

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
        if entry["kind"] in ("system", "field"):
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


def _scalar_field_display(instance, field) -> dict:
    """Render a non-object COT field value for the rules table."""
    from extras.choices import CustomFieldTypeChoices

    value = getattr(instance, field.name, None)
    ftype = field.type

    if ftype == CustomFieldTypeChoices.TYPE_BOOLEAN:
        if value is None:
            return {"display": "-", "url": ""}
        return {"display": "\u2713" if value else "\u2717", "url": "", "boolean": bool(value)}

    if ftype == CustomFieldTypeChoices.TYPE_OBJECT:
        if value is None:
            return {"display": "-", "url": ""}
        url = value.get_absolute_url() if hasattr(value, "get_absolute_url") else ""
        return {"display": str(value), "url": url or ""}

    if value is None or value == "":
        return {"display": "-", "url": ""}

    if isinstance(value, (list, tuple)):
        text = ", ".join(str(v) for v in value if v not in (None, ""))
        return {"display": text or "-", "url": ""}

    if ftype == CustomFieldTypeChoices.TYPE_URL:
        return {"display": str(value), "url": str(value)}

    return {"display": str(value), "url": ""}


def build_cot_grouped_rules_table_data(
    instances,
    virtual_rb,
    *,
    layout=None,
    object_field_names: set[str] | None = None,
    include_links: bool = True,
) -> dict:
    if layout is None:
        layout = build_cot_rules_layout(virtual_rb.cot)
    grouped_columns = layout["grouped_columns"]
    scalar_field_slugs = [
        entry["slug"]
        for entry in (layout.get("rules_layout") or [])
        if entry.get("kind") == "field"
    ]
    scalar_fields = (
        list(virtual_rb.cot.fields.filter(name__in=scalar_field_slugs))
        if scalar_field_slugs
        else []
    )
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
    from netbox_nsm.type_metadata.specs import content_type_ids_for_cot_slugs

    ct_cache: dict = {}
    address_ct_ids = set(
        content_type_ids_for_cot_slugs(
            ["nsm_address", "nsm_address_custom", "nsm_address_group"]
        )
    )
    from netbox_nsm.core.display_utils import get_display_template_map

    tmpl_map = get_display_template_map()
    extra_columns_by_source: dict[str, list[dict]] = {}
    source_column_label_by_key: dict[str, str] = {}
    source_column_is_polymorphic: dict[str, bool] = {}
    for entry in layout.get("rules_layout") or []:
        if entry.get("kind") != "object":
            continue
        is_poly = bool(entry.get("is_polymorphic"))
        for group_col in (entry.get("group") or {}).get("columns") or []:
            key = group_col.get("key")
            if not key or group_col.get("source_key"):
                continue
            source_column_is_polymorphic[key] = is_poly

    for col in grouped_columns:
        if not col.get("source_key"):
            source_column_label_by_key[col["key"]] = str(col.get("label") or "").strip()
        source_key = col.get("source_key")
        if source_key and col.get("value_template"):
            extra_columns_by_source.setdefault(source_key, []).append(col)

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
            for idx, obj in enumerate(objs):
                model_cls = obj.__class__
                if model_cls not in ct_cache:
                    ct_cache[model_cls] = ContentType.objects.get_for_model(obj).pk
                key = f"{field.name}::ct_{ct_cache[model_cls]}"
                if key in per_key:
                    item = _object_item_dict(
                        obj,
                        ct_cache=ct_cache,
                        address_ct_ids=address_ct_ids,
                        include_links=include_links,
                        tmpl_map=tmpl_map,
                    )
                    per_key[key].append(item)
                    for extra_col in extra_columns_by_source.get(key, []):
                        if source_column_is_polymorphic.get(key, False):
                            if idx > 0:
                                per_key[extra_col["key"]].append(
                                    {"name": "", "segment_break": True}
                                )
                            segment_header = {
                                "name": item.get("name") or "",
                                "segment_label": True,
                            }
                            segment_type_label = source_column_label_by_key.get(key, "")
                            if segment_type_label:
                                segment_header["segment_type_label"] = segment_type_label
                            if item.get("url"):
                                segment_header["url"] = item["url"]
                            per_key[extra_col["key"]].append(segment_header)
                        items = _extra_column_render_items(
                            obj,
                            extra_col.get("value_template") or "{{ name }}",
                            include_links=include_links,
                        )
                        per_key[extra_col["key"]].extend(items)

        cells = {}
        cells_items = {}
        cells_filter = {}
        for key, items in per_key.items():
            cells_items[key] = items
            if object_field_names is None and include_links:
                cells[key] = render_rules_pill_cell(
                    items, max_pills=DEFAULT_MAX_VISIBLE_PILLS, colored=True
                )
            cells_filter[key] = " ".join(item["name"] for item in items)

        field_values = {
            field.name: _scalar_field_display(instance, field)
            for field in scalar_fields
        }

        index_val = getattr(instance, "index", None)
        status_val = bool(getattr(instance, "status", True))
        name_val = getattr(instance, "name", "") or ""
        desc_val = getattr(instance, "description", "") or "-"
        pk = instance.pk
        detail_url = _cot_detail_url(cot_slug, pk) if include_links else ""

        row = {
            "pk": pk,
            "index": index_val,
            "enabled": status_val,
            "name": name_val,
            "description": desc_val or "-",
            "system": {
                "index": index_val,
                "enabled": status_val,
                "name": name_val,
                "description": desc_val or "-",
            },
            "cells_items": cells_items,
            "cells_filter": cells_filter,
            "fields": field_values,
        }
        if include_links:
            row.update(
                {
                    "url": detail_url,
                    "edit_url": _cot_edit_url(cot_slug, pk),
                    "delete_url": _cot_delete_url(cot_slug, pk),
                    "system": {
                        **row["system"],
                        "url": detail_url,
                    },
                    "cells": cells,
                }
            )
        rows.append(row)

    layout["rows"] = rows
    return layout
