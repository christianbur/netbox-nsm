"""Per-column quick-search filters for the Object Sync table."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from netbox_nsm.objects.address_object_builder import SyncIssue
from netbox_nsm.rulebooks.grid_payload import (
    apply_ag_grid_row_filter,
    build_column_quick_filter_spec,
)

__all__ = (
    "SYNC_FILTER_PREFIX",
    "apply_sync_issue_filters",
    "build_filter_columns",
    "build_filter_querystring",
    "filter_model_from_request",
    "sync_issue_filter_record",
    "SYNC_FILTER_COLUMN_SPECS",
)

SYNC_FILTER_PREFIX = "sf_"

SYNC_FILTER_COLUMN_SPECS = (
    {"field": "category", "param": f"{SYNC_FILTER_PREFIX}category", "label": _("Category")},
    {"field": "source", "param": f"{SYNC_FILTER_PREFIX}source", "label": _("Source")},
    {"field": "object", "param": f"{SYNC_FILTER_PREFIX}object", "label": _("IPAM / Address")},
    {
        "field": "expected_name",
        "param": f"{SYNC_FILTER_PREFIX}expected_name",
        "label": _("Expected name"),
    },
    {
        "field": "expected_status",
        "param": f"{SYNC_FILTER_PREFIX}expected_status",
        "label": _("Status"),
    },
    {"field": "details", "param": f"{SYNC_FILTER_PREFIX}details", "label": _("Details")},
)


def filter_model_from_request(request, column_specs) -> dict[str, dict]:
    model: dict[str, dict] = {}
    for spec in column_specs:
        raw = (request.GET.get(spec["param"]) or "").strip()
        if not raw:
            continue
        parsed = build_column_quick_filter_spec(raw)
        if parsed:
            model[spec["field"]] = parsed
    return model


def build_filter_columns(request, column_specs) -> list[dict]:
    columns = []
    for spec in column_specs:
        columns.append(
            {
                **spec,
                "filter_value": (request.GET.get(spec["param"]) or "").strip(),
            }
        )
    return columns


def _sync_issue_details_text(issue: SyncIssue) -> str:
    parts: list[str] = []
    if issue.actual_status:
        parts.append(issue.actual_status)
    if issue.addresses:
        parts.extend(getattr(addr, "name", str(addr)) for addr in issue.addresses)
    if issue.groups:
        parts.extend(getattr(grp, "name", str(grp)) for grp in issue.groups)
    if issue.member_issues:
        parts.extend(issue.member_issues)
    if issue.detail:
        parts.append(issue.detail)
    return " ".join(str(part) for part in parts if part)


def sync_issue_filter_record(issue: SyncIssue) -> dict[str, str]:
    if issue.ipam_obj is not None:
        object_label = str(issue.ipam_obj)
    elif issue.address_obj is not None:
        object_label = str(issue.address_obj)
    elif issue.group_obj is not None:
        object_label = str(issue.group_obj)
    else:
        object_label = ""
    return {
        "category": issue.category or "",
        "source": issue.source_key or "",
        "object": object_label,
        "expected_name": issue.expected_name or "",
        "expected_status": issue.expected_status or "",
        "details": _sync_issue_details_text(issue),
    }


def apply_sync_issue_filters(issues, filter_model: dict[str, dict] | None):
    if not filter_model:
        return issues
    result = []
    for issue in issues:
        record = sync_issue_filter_record(issue)
        if apply_ag_grid_row_filter([record], filter_model):
            result.append(issue)
    return result


def build_filter_querystring(
    request,
    *,
    drop_prefix: str | None = None,
    reset_sync_page: bool = False,
) -> str:
    params = request.GET.copy()
    if drop_prefix:
        for key in list(params.keys()):
            if key.startswith(drop_prefix):
                del params[key]
    if reset_sync_page:
        params["sync_page"] = "1"
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""
