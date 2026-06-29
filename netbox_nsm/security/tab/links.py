"""Security tab linked-objects table: quicksearch, type filter, pagination.

All linked objects render in a single flat table. Former object-type tabs are
exposed as the **Type** column; quicksearch and a type dropdown sit above the
table (PR #482-style controls, without value pills or object-type tabs).
"""

from __future__ import annotations

import re

from django.core.paginator import Paginator

__all__ = (
    "DEFAULT_PER_PAGE",
    "PARAM_ORDER",
    "PARAM_PAGE",
    "PARAM_PER_PAGE",
    "PARAM_Q",
    "PARAM_ROW_TYPE",
    "PER_PAGE_CHOICES",
    "build_row_type_options",
    "flatten_link_type_groups",
    "prepare_link_tab_view",
)

PARAM_Q = "nsm_q"
PARAM_ROW_TYPE = "nsm_ty"
PARAM_PAGE = "nsm_lp"
PARAM_PER_PAGE = "nsm_pp"
PARAM_ORDER = "nsm_lo"

# Legacy query params (object-type tabs / value pills) — ignored if present.
PARAM_TYPE = "nsm_lt"
PARAM_VALUE = "nsm_lv"

DEFAULT_PER_PAGE = 50
PER_PAGE_CHOICES = (25, 50, 100, 250)

_VALID_ORDERS = ("name", "-name", "value", "-value")
_STRIP_TAGS = re.compile(r"<[^>]+>")


def _querystring(request, **overrides) -> str:
    """Return a ``?a=b`` querystring from ``request.GET`` with overrides."""
    if request is not None:
        params = request.GET.copy()
    else:
        from django.http import QueryDict

        params = QueryDict(mutable=True)
    for key, value in overrides.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""


def _row_type_filter_key(obj: dict) -> str:
    return obj.get("row_type_filter_key") or ""


def _plain_text(value) -> str:
    text = str(value or "")
    return _STRIP_TAGS.sub("", text)


def flatten_link_type_groups(groups: list[dict]) -> list[dict]:
    """Merge grouped link payloads into one list with Type-column metadata."""
    rows: list[dict] = []
    for group in groups or []:
        type_key = group.get("type_key") or ""
        type_label = group.get("type_label") or type_key
        for obj in group.get("objects") or []:
            row = dict(obj)
            row["row_type_label"] = type_label
            row["row_type_filter_key"] = type_key
            rows.append(row)
    return rows


def build_row_type_options(objects: list[dict]) -> list[dict]:
    """Distinct Type-column values for the type dropdown."""
    buckets: dict[str, dict] = {}
    for obj in objects:
        key = _row_type_filter_key(obj)
        if not key:
            continue
        label = obj.get("row_type_label") or key
        bucket = buckets.get(key)
        if bucket is None:
            buckets[key] = {"key": key, "label": label, "count": 1}
        else:
            bucket["count"] += 1
    return sorted(buckets.values(), key=lambda entry: entry["label"].lower())


def _matches_quicksearch(obj: dict, query: str) -> bool:
    if not query:
        return True
    needle = query.lower()
    for field in ("name", "field_label", "row_type_label"):
        if needle in _plain_text(obj.get(field)).lower():
            return True
    return False


def _object_sort_key(order: str):
    field = order.lstrip("-")
    reverse = order.startswith("-")

    if field == "value":

        def key(obj: dict):
            return (
                _plain_text(obj.get("value_label")).lower(),
                _plain_text(obj.get("name")).lower(),
            )

    else:

        def key(obj: dict):
            return _plain_text(obj.get("name")).lower()

    return key, reverse


def _clamp_per_page(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PER_PAGE
    return value if value in PER_PAGE_CHOICES else DEFAULT_PER_PAGE


def _smart_pages(page, paginator, *, window: int = 2) -> list[int | None]:
    total = paginator.num_pages
    if total <= 1:
        return [1] if total == 1 else []
    current = page.number
    pages: list[int | None] = []
    candidate = set(range(max(1, current - window), min(total, current + window) + 1))
    candidate.update({1, total})
    previous = 0
    for number in sorted(candidate):
        if number - previous > 1:
            pages.append(None)
        pages.append(number)
        previous = number
    return pages


def _row_has_actions(obj: dict) -> bool:
    if obj.get("supports_addr_analysis") or obj.get("addr_analyzable"):
        return True
    return bool(obj.get("edit_url") or obj.get("delete_url"))


def prepare_link_tab_view(link_type_groups: list[dict], request) -> dict:
    """Build flat-table context (controls + paginated page slice)."""
    get = request.GET if request is not None else {}
    query = (get.get(PARAM_Q) or "").strip()
    requested_row_type = get.get(PARAM_ROW_TYPE) or ""
    order = get.get(PARAM_ORDER) or "name"
    if order not in _VALID_ORDERS:
        order = "name"
    per_page = _clamp_per_page(get.get(PARAM_PER_PAGE))
    try:
        page_number = max(1, int(get.get(PARAM_PAGE, 1)))
    except (TypeError, ValueError):
        page_number = 1

    all_objects = flatten_link_type_groups(link_type_groups)
    if not all_objects:
        return {"nsm_link_table": None, "nsm_link_count": 0}

    row_type_options = build_row_type_options(all_objects)
    row_type_keys = {opt["key"] for opt in row_type_options}
    active_row_type = (
        requested_row_type if requested_row_type in row_type_keys else ""
    )

    objects = all_objects
    if active_row_type:
        objects = [o for o in objects if _row_type_filter_key(o) == active_row_type]
    if query:
        objects = [o for o in objects if _matches_quicksearch(o, query)]

    sort_key, reverse = _object_sort_key(order)
    objects.sort(key=sort_key, reverse=reverse)

    paginator = Paginator(objects, per_page)
    page = paginator.get_page(page_number)
    smart_pages = _smart_pages(page, paginator)

    def _table_qs(**extra) -> str:
        params = {
            PARAM_Q: query or None,
            PARAM_ROW_TYPE: active_row_type or None,
        }
        params.update(extra)
        return _querystring(request, **params)

    order_field = order.lstrip("-")
    descending = order.startswith("-")
    sort_headers = {}
    for field in ("name", "value"):
        is_current = order_field == field
        next_order = f"-{field}" if (is_current and not descending) else field
        sort_headers[field] = {
            "url": _table_qs(**{PARAM_ORDER: next_order, PARAM_PAGE: None}),
            "sorted": is_current,
            "descending": is_current and descending,
        }

    table = {
        "page": list(page.object_list),
        "paginated": True,
        "show_actions": any(_row_has_actions(obj) for obj in all_objects),
        "q": query,
        "active_row_type": active_row_type,
        "has_row_type_filter": len(row_type_options) > 1,
        "row_type_options": row_type_options,
        "clear_filters_url": _querystring(
            request,
            **{PARAM_Q: None, PARAM_ROW_TYPE: None, PARAM_PAGE: None},
        ),
        "sort_headers": sort_headers,
        "pagination": {
            "num_pages": paginator.num_pages,
            "total": paginator.count,
            "showing_start": page.start_index() if paginator.count else 0,
            "showing_end": page.end_index() if paginator.count else 0,
            "prev_url": _table_qs(**{PARAM_PAGE: page.previous_page_number()})
            if page.has_previous()
            else "",
            "next_url": _table_qs(**{PARAM_PAGE: page.next_page_number()})
            if page.has_next()
            else "",
            "pages": [
                {
                    "number": p,
                    "url": _table_qs(**{PARAM_PAGE: p}) if p else "",
                    "current": p == page.number,
                    "gap": p is None,
                }
                for p in smart_pages
            ],
            "per_page": per_page,
            "per_page_choices": [
                {"n": n, "url": _table_qs(**{PARAM_PER_PAGE: n, PARAM_PAGE: None})}
                for n in PER_PAGE_CHOICES
            ],
        },
    }

    return {
        "nsm_link_table": table,
        "nsm_link_count": len(all_objects),
    }
