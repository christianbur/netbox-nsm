"""Helpers for netbox_branching: preserve branch context in page links."""

from __future__ import annotations

__all__ = (
    "branch_schema_id_from_request",
    "with_branch_query",
    "wrap_rules_row_urls",
    "wrap_matrix_cell_hrefs",
)


def branch_schema_id_from_request(request) -> str | None:
    """Return active branch schema_id from the request cookie, if any."""
    if request is None:
        return None
    try:
        from netbox_branching.constants import COOKIE_NAME

        schema_id = request.COOKIES.get(COOKIE_NAME)
        if schema_id:
            return str(schema_id).strip() or None
    except ImportError:
        pass
    return None


def with_branch_query(url: str, request) -> str:
    """
    Append ``?_branch=<schema_id>`` (or ``&_branch=``) so navigation stays in the
    active branch. No-op on main / when branching is unavailable.
    """
    if not url or url == "#":
        return url
    schema_id = branch_schema_id_from_request(request)
    if not schema_id:
        return url
    try:
        from netbox_branching.constants import QUERY_PARAM
    except ImportError:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{QUERY_PARAM}={schema_id}"


def wrap_rules_row_urls(rows: list, request) -> None:
    """Mutate policy row dicts in place — detail/edit/delete links."""
    for row in rows or []:
        for key in ("url", "edit_url", "delete_url"):
            if key in row:
                row[key] = with_branch_query(row[key], request)
        system = row.get("system")
        if isinstance(system, dict) and system.get("url"):
            system["url"] = with_branch_query(system["url"], request)


def wrap_matrix_cell_hrefs(cells: list, request) -> None:
    """Mutate matrix cell dicts — rule filter and add-rule links."""
    for cell in cells or []:
        for key in (
            "filter_href",
            "add_href",
            "href",
        ):
            if key in cell:
                cell[key] = with_branch_query(cell[key], request)
