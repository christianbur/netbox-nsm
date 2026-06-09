"""Server-side object browse for the rule editor picker (replaces direct NetBox REST)."""

from __future__ import annotations

import re
from typing import Any

from django.db.models import CharField, Q
from django.db.models.functions import Cast
from django.contrib.contenttypes.models import ContentType

from netbox_nsm.core.display_utils import get_display_template_map, render_object_display
from netbox_nsm.query.engine import _object_attribute

__all__ = (
    "MIN_PICKER_QUERY_LEN",
    "browse_content_type_objects",
    "browse_picker_objects",
    "is_picker_browse_allowed",
    "serialize_picker_object",
)

MIN_PICKER_QUERY_LEN = 1
MAX_PICKER_LIMIT = 100
DEFAULT_PICKER_LIMIT = 30

_NAME_SEARCH_FIELDS = ("name", "display", "prefix", "address", "slug")
_FK_SEARCH_LOOKUPS = (
    "ip_address__address",
    "prefix__prefix",
    "range__start_address",
    "range__end_address",
)
_INET_FIELD_TYPES = frozenset({"IPNetworkField", "IPAddressField"})


def _resolve_field(model_class, lookup_path: str):
    model = model_class
    field = None
    for part in lookup_path.split("__"):
        field = model._meta.get_field(part)
        if getattr(field, "is_relation", False) and field.related_model is not None:
            model = field.related_model
    return field


def _is_inet_like_field(field) -> bool:
    return type(field).__name__ in _INET_FIELD_TYPES


def _filter_queryset_by_query(qs, model_class, q: str):
    if not q:
        return qs
    text_clauses = Q()
    inet_paths: list[str] = []
    matched = False

    for field_name in _NAME_SEARCH_FIELDS:
        try:
            field = model_class._meta.get_field(field_name)
        except Exception:
            continue
        if _is_inet_like_field(field):
            inet_paths.append(field_name)
        else:
            text_clauses |= Q(**{f"{field_name}__icontains": q})
        matched = True

    try:
        model_class._meta.get_field("field_data")
        text_clauses |= Q(**{"field_data__icontains": q})
        matched = True
    except Exception:
        pass

    for lookup in _FK_SEARCH_LOOKUPS:
        fk_name = lookup.split("__", 1)[0]
        try:
            fk_field = model_class._meta.get_field(fk_name)
            if not getattr(fk_field, "is_relation", False):
                continue
            field = _resolve_field(model_class, lookup)
        except Exception:
            continue
        if _is_inet_like_field(field):
            inet_paths.append(lookup)
        else:
            text_clauses |= Q(**{f"{lookup}__icontains": q})
        matched = True

    if not matched:
        return qs.none()

    inet_clauses = Q()
    annotations = {}
    for index, path in enumerate(inet_paths):
        alias = f"_nsm_inet_search_{index}"
        annotations[alias] = Cast(path, CharField())
        inet_clauses |= Q(**{f"{alias}__icontains": q})

    if annotations:
        qs = qs.annotate(**annotations)
    return qs.filter(text_clauses | inet_clauses)


def is_picker_browse_allowed(ct_id: int) -> bool:
    """True when this content type may appear in a COT rulebook field picker."""
    from netbox_nsm.models import TypeConfig

    return TypeConfig.objects.filter(content_type_id=ct_id).exists()


def _resolve_short_name(obj: Any) -> str:
    for attr in ("name", "prefix", "address", "slug"):
        val = getattr(obj, attr, None)
        if val not in (None, ""):
            return str(val)
    return str(obj)


def _object_color(obj: Any) -> str:
    raw = _object_attribute(obj, "color")
    if raw in (None, ""):
        return ""
    return str(raw).strip()


def serialize_picker_object(
    obj: Any, content_type_id: int, tmpl_map: dict[int, str] | None = None
) -> dict:
    """NetBox-API-compatible brief object for lazy picker UIs."""
    display = render_object_display(obj, content_type_id, tmpl_map)
    return {
        "id": obj.pk,
        "name": _resolve_short_name(obj),
        "display": display,
        "color": _object_color(obj),
    }


def _order_queryset(qs, model_class):
    for field_name in ("name", "slug", "prefix", "address", "pk"):
        try:
            model_class._meta.get_field(field_name)
            return qs.order_by(field_name)
        except Exception:
            continue
    return qs.order_by("pk")


def _apply_name_filter_regex(items: list[dict], pattern: str | None) -> list[dict]:
    if not pattern:
        return items
    try:
        rx = re.compile(pattern)
    except re.error:
        return items
    return [
        item
        for item in items
        if rx.search(str(item.get("display") or item.get("name") or ""))
    ]


def browse_content_type_objects(
    ct_id: int,
    *,
    q: str = "",
    limit: int = DEFAULT_PICKER_LIMIT,
    offset: int = 0,
) -> dict:
    """
    Return ``{count, results}`` for object browse by content type.

    No rulebook picker permission check — callers enforce their own policy.
    When ``q`` is empty, returns the first page.
    """
    try:
        ct = ContentType.objects.get(pk=ct_id)
    except ContentType.DoesNotExist as exc:
        raise ValueError("Invalid content type") from exc

    model_class = ct.model_class()
    if model_class is None:
        return {"count": 0, "results": []}

    limit = max(1, min(int(limit), MAX_PICKER_LIMIT))
    offset = max(0, int(offset))

    qs = model_class.objects.all()
    if q:
        qs = _filter_queryset_by_query(qs, model_class, q)
    qs = _order_queryset(qs, model_class)

    total = qs.count()
    page = list(qs[offset : offset + limit])
    tmpl_map = get_display_template_map()
    results = [serialize_picker_object(obj, ct_id, tmpl_map) for obj in page]
    return {"count": total, "results": results}


def browse_picker_objects(
    ct_id: int,
    *,
    q: str = "",
    limit: int = DEFAULT_PICKER_LIMIT,
    offset: int = 0,
    name_filter_regex: str | None = None,
) -> dict:
    """
    Return ``{count, results}`` for rule picker browse.

    ``q`` empty with no wildcard semantics is handled by the view (min length).
    When ``q`` is empty after wildcard normalization, returns the first page.
    """
    if not is_picker_browse_allowed(ct_id):
        raise ValueError("Content type not allowed for rule picker")

    payload = browse_content_type_objects(ct_id, q=q, limit=limit, offset=offset)
    if name_filter_regex:
        payload["results"] = _apply_name_filter_regex(
            payload["results"], name_filter_regex
        )
        payload["count"] = len(payload["results"])
    return payload
