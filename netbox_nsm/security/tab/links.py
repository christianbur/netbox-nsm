"""Object-type tabs + value sub-grouping + server-side pagination.

The Security tab can link to very large numbers of objects (50k+). To keep the
rendered page bounded, linked objects are presented as:

1. **Object-type tabs** — one tab per linked content type, each with a count
   badge. Only the *active* tab's rows are rendered into the DOM.
2. **Value sub-filter** — within a tab, a segmented pill filter groups rows by a
   secondary "value" (e.g. an *Action* object's Permit / Deny), each with its
   own count.
3. **Pagination** — the active tab/value selection is paginated server-side so
   at most one page of rows (default 50) ever reaches the browser.

This module is pure presentation logic over the already-collected link payloads
(``finalize_link_type_groups`` output); it does not touch the link source of
truth or tab registration.
"""

from __future__ import annotations

from django.core.paginator import Paginator

from netbox_nsm.security.tab.value_groups import (
    UNGROUPED_KEY,
    UNGROUPED_LABEL,
    nsm_object_group_value,
)

__all__ = (
    "DEFAULT_PER_PAGE",
    "PARAM_ORDER",
    "PARAM_PAGE",
    "PARAM_PER_PAGE",
    "PARAM_TYPE",
    "PARAM_VALUE",
    "PER_PAGE_CHOICES",
    "build_value_subgroups",
    "prepare_link_tab_view",
)

PARAM_TYPE = "nsm_lt"
PARAM_VALUE = "nsm_lv"
PARAM_PAGE = "nsm_lp"
PARAM_PER_PAGE = "nsm_pp"
PARAM_ORDER = "nsm_lo"

DEFAULT_PER_PAGE = 50
PER_PAGE_CHOICES = (25, 50, 100, 250)

_VALID_ORDERS = ("name", "-name", "value", "-value")


def _querystring(request, **overrides) -> str:
    """Return a ``?a=b`` querystring from ``request.GET`` with overrides.

    A value of ``None`` removes the parameter. The result always starts with
    ``?`` (or is empty when there are no params).
    """
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


def build_value_subgroups(objects: list[dict]) -> list[dict]:
    """Group ``objects`` by value, preserving counts and a stable order.

    Returns a list of ``{value_key, value_label, count}``. Ungrouped objects
    (no recognisable value) are collapsed under :data:`UNGROUPED_KEY` and sorted
    last. When every object shares the same (or no) value the caller should not
    render the value filter.
    """
    counts: dict[str, dict] = {}
    for obj in objects:
        value_key = obj.get("value_key") or UNGROUPED_KEY
        value_label = obj.get("value_label") or UNGROUPED_LABEL
        bucket = counts.get(value_key)
        if bucket is None:
            counts[value_key] = {
                "value_key": value_key,
                "value_label": value_label,
                "count": 1,
            }
        else:
            bucket["count"] += 1

    def _sort_key(entry: dict):
        is_ungrouped = entry["value_key"] == UNGROUPED_KEY
        return (is_ungrouped, entry["value_label"].lower())

    return sorted(counts.values(), key=_sort_key)


def _object_sort_key(order: str):
    field = order.lstrip("-")
    reverse = order.startswith("-")

    if field == "value":

        def key(obj: dict):
            return (
                (obj.get("value_label") or "").lower(),
                (obj.get("name") or "").lower(),
            )

    else:

        def key(obj: dict):
            return (obj.get("name") or "").lower()

    return key, reverse


def _clamp_per_page(raw) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PER_PAGE
    return value if value in PER_PAGE_CHOICES else DEFAULT_PER_PAGE


def _smart_pages(page, paginator, *, window: int = 2) -> list[int | None]:
    """Compact page-number list with ``None`` markers for elided ranges."""
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


def prepare_link_tab_view(link_type_groups: list[dict], request) -> dict:
    """Build the object-type tab / value / pagination context.

    ``link_type_groups`` is the finalized link-group list (each group carries a
    ``objects`` list of payloads annotated with ``value_key`` / ``value_label``).

    Returns ``{"nsm_link_type_groups", "nsm_active_link_type",
    "nsm_active_link_value"}``. All per-tab rendering data (value pills, sorted
    page slice, pagination, sort headers) is attached to the *active* group dict
    so the template needs no per-key dictionary lookups.
    """
    groups = list(link_type_groups or [])

    get = request.GET if request is not None else {}
    requested_type = get.get(PARAM_TYPE) or ""
    requested_value = get.get(PARAM_VALUE) or ""
    order = get.get(PARAM_ORDER) or "name"
    if order not in _VALID_ORDERS:
        order = "name"
    per_page = _clamp_per_page(get.get(PARAM_PER_PAGE))
    try:
        page_number = max(1, int(get.get(PARAM_PAGE, 1)))
    except (TypeError, ValueError):
        page_number = 1

    type_keys = {g["type_key"] for g in groups}
    active_type = requested_type if requested_type in type_keys else ""
    if not active_type and groups:
        active_type = groups[0]["type_key"]

    tab_groups: list[dict] = []
    active_group = None
    for group in groups:
        subgroups = build_value_subgroups(group.get("objects") or [])
        is_active = group["type_key"] == active_type
        entry = {
            **group,
            "value_subgroups": subgroups,
            "has_value_grouping": len(subgroups) > 1,
            "is_active": is_active,
            "paginated": False,
            "tab_url": _querystring(
                request,
                **{PARAM_TYPE: group["type_key"], PARAM_VALUE: None, PARAM_PAGE: None},
            ),
        }
        tab_groups.append(entry)
        if is_active:
            active_group = entry

    context: dict = {
        "nsm_link_type_groups": tab_groups,
        "nsm_active_link_type": active_type,
        "nsm_active_link_value": "",
    }
    if active_group is None:
        return context

    subgroup_keys = {sg["value_key"] for sg in active_group["value_subgroups"]}
    active_value = requested_value if requested_value in subgroup_keys else ""
    context["nsm_active_link_value"] = active_value

    objects = list(active_group.get("objects") or [])
    if active_value:
        objects = [
            o for o in objects if (o.get("value_key") or UNGROUPED_KEY) == active_value
        ]

    sort_key, reverse = _object_sort_key(order)
    objects.sort(key=sort_key, reverse=reverse)

    paginator = Paginator(objects, per_page)
    page = paginator.get_page(page_number)
    smart_pages = _smart_pages(page, paginator)

    def _tab_qs(**extra) -> str:
        params = {PARAM_TYPE: active_type, PARAM_VALUE: active_value or None}
        params.update(extra)
        return _querystring(request, **params)

    # Value filter pills (reset page).
    active_group["all_value_url"] = _querystring(
        request, **{PARAM_TYPE: active_type, PARAM_VALUE: None, PARAM_PAGE: None}
    )
    active_group["all_value_active"] = not active_value
    for sg in active_group["value_subgroups"]:
        sg["url"] = _querystring(
            request,
            **{PARAM_TYPE: active_type, PARAM_VALUE: sg["value_key"], PARAM_PAGE: None},
        )
        sg["is_active"] = sg["value_key"] == active_value

    # Sortable column headers (toggle direction; keep tab/value; reset page).
    order_field = order.lstrip("-")
    descending = order.startswith("-")
    sort_headers = {}
    for field in ("name", "value"):
        is_current = order_field == field
        next_order = f"-{field}" if (is_current and not descending) else field
        sort_headers[field] = {
            "url": _tab_qs(**{PARAM_ORDER: next_order, PARAM_PAGE: None}),
            "sorted": is_current,
            "descending": is_current and descending,
        }
    active_group["sort_headers"] = sort_headers

    active_group["paginated"] = True
    active_group["page"] = list(page.object_list)
    active_group["pagination"] = {
        "num_pages": paginator.num_pages,
        "total": paginator.count,
        "showing_start": page.start_index(),
        "showing_end": page.end_index(),
        "prev_url": _tab_qs(**{PARAM_PAGE: page.previous_page_number()})
        if page.has_previous()
        else "",
        "next_url": _tab_qs(**{PARAM_PAGE: page.next_page_number()})
        if page.has_next()
        else "",
        "pages": [
            {
                "number": p,
                "url": _tab_qs(**{PARAM_PAGE: p}) if p else "",
                "current": p == page.number,
                "gap": p is None,
            }
            for p in smart_pages
        ],
        "per_page": per_page,
        "per_page_choices": [
            {"n": n, "url": _tab_qs(**{PARAM_PER_PAGE: n, PARAM_PAGE: None})}
            for n in PER_PAGE_CHOICES
        ],
    }
    return context
