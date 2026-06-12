"""Pagination helpers for the Object Sync UI."""

from __future__ import annotations

from django.core.paginator import Paginator

from utilities.paginator import EnhancedPaginator

__all__ = (
    "OBJECT_SYNC_DEFAULT_PER_PAGE",
    "paginate_sync_list",
    "resolve_sync_per_page",
)

OBJECT_SYNC_DEFAULT_PER_PAGE = 25


def _clamp_page(page_num: int, paginator: Paginator) -> int:
    try:
        page_num = int(page_num)
    except (TypeError, ValueError):
        page_num = 1
    return max(1, min(page_num, paginator.num_pages or 1))


def resolve_sync_per_page(request, param_name: str) -> int:
    raw = request.GET.get(param_name)
    if raw:
        try:
            per_page = int(raw)
            if per_page >= 1:
                return per_page
        except ValueError:
            pass
    return OBJECT_SYNC_DEFAULT_PER_PAGE


def paginate_sync_list(
    request,
    items,
    *,
    page_param: str,
    per_page_param: str,
):
    """Return ``(page_items, paginator, page_obj)`` for the sync table."""
    per_page = resolve_sync_per_page(request, per_page_param)
    try:
        page_num = int(request.GET.get(page_param, 1))
    except (TypeError, ValueError):
        page_num = 1

    paginator = EnhancedPaginator(items, per_page)
    page_num = _clamp_page(page_num, paginator)
    page_obj = paginator.get_page(page_num)
    return list(page_obj.object_list), paginator, page_obj
