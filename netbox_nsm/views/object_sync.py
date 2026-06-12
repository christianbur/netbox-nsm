from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views import View

from netbox_nsm.objects.address_object_builder import (
    apply_sync_fixes,
    expand_bulk_fix_tokens,
    scan_sync_state,
)
from netbox_nsm.objects.nsm_config import resolve_object_builder_config_for_cot
from netbox_nsm.views.object_sync_filters import (
    SYNC_FILTER_COLUMN_SPECS,
    SYNC_FILTER_PREFIX,
    apply_sync_issue_filters,
    build_filter_columns,
    build_filter_querystring,
    filter_model_from_request,
)
from netbox_nsm.views.object_sync_pagination import paginate_sync_list

__all__ = ("ObjectSyncView",)

_SYNC_CATEGORY_LABELS = (
    ("missing", _("Missing")),
    ("orphan_nsm", _("Orphan NSM")),
    ("status_mismatch", _("Status mismatch")),
    ("name_drift", _("Name drift")),
    ("duplicate_ipam_link", _("Duplicate IPAM link")),
    ("duplicate_group_ipam", _("Duplicate group IPAM")),
    ("group_ipam_overlap", _("Group IPAM overlap")),
    ("group_member_drift", _("Group member drift")),
)

_SYNC_QUERY_KEYS = (
    "source",
    "sync_page",
    "sync_per_page",
)


def _get_address_cot():
    try:
        from netbox_custom_objects.models import CustomObjectType
    except ImportError:
        raise Http404
    for slug in ("nsm_address", "nsm_addresses"):
        cot = CustomObjectType.objects.filter(slug=slug).first()
        if cot is not None:
            return cot
    raise Http404


def _sync_query_from_request(request, *, prefer_post: bool = False) -> str:
    data = request.POST if prefer_post else request.GET
    params = {}
    for key, value in data.items():
        if key in _SYNC_QUERY_KEYS or key.startswith(SYNC_FILTER_PREFIX):
            if value:
                params[key] = value
    encoded = urlencode(params)
    return f"?{encoded}" if encoded else ""


class ObjectSyncView(PermissionRequiredMixin, View):
    permission_required = "netbox_nsm.view_typeconfig"
    template_name = "netbox_nsm/object_sync.html"

    def get(self, request):
        cot = _get_address_cot()
        sync_config = resolve_object_builder_config_for_cot(cot)
        source_filter = request.GET.get("source", "").strip() or None
        source_keys = [source_filter] if source_filter else None

        sync_filter_model = filter_model_from_request(request, SYNC_FILTER_COLUMN_SPECS)

        sync = scan_sync_state(sync_config, source_keys=source_keys)
        filtered_sync_issues = apply_sync_issue_filters(sync.issues, sync_filter_model)
        sync_issues, sync_paginator, sync_page_obj = paginate_sync_list(
            request,
            filtered_sync_issues,
            page_param="sync_page",
            per_page_param="sync_per_page",
        )

        return render(
            request,
            self.template_name,
            {
                "cot": cot,
                "sync_config": sync_config,
                "sync_enabled": bool(sync_config and sync_config.get("enabled")),
                "config_edit_url": reverse(
                    "plugins:netbox_nsm:objectconfig_edit",
                    args=["nsm_address"],
                ),
                "sync": sync,
                "sync_issues": sync_issues,
                "sync_paginator": sync_paginator,
                "sync_page_obj": sync_page_obj,
                "sync_filter_columns": build_filter_columns(
                    request, SYNC_FILTER_COLUMN_SPECS
                ),
                "sync_filter_active": bool(sync_filter_model),
                "sync_clear_filters_url": (
                    reverse("plugins:netbox_nsm:object_sync")
                    + build_filter_querystring(
                        request,
                        drop_prefix=SYNC_FILTER_PREFIX,
                        reset_sync_page=True,
                    )
                ),
                "sync_category_rows": [
                    (cat, label, sync.counts.get(cat, 0))
                    for cat, label in _SYNC_CATEGORY_LABELS
                ],
                "source_filter": source_filter,
                "source_choices": (
                    ("ipam.ipaddress", _("IP Addresses")),
                    ("ipam.prefix", _("Prefixes")),
                    ("ipam.iprange", _("IP Ranges")),
                ),
                "can_fix_sync_issues": request.user.has_perm(
                    "netbox_nsm.change_typeconfig"
                ),
            },
        )

    def post(self, request):
        if not request.user.has_perm("netbox_nsm.change_typeconfig"):
            messages.error(request, _("You do not have permission to fix sync issues."))
            return redirect(reverse("plugins:netbox_nsm:object_sync"))

        cot = _get_address_cot()
        sync_config = resolve_object_builder_config_for_cot(cot)
        if not sync_config or not sync_config.get("enabled"):
            messages.error(request, _("Object Sync is not enabled in Object Config."))
            return redirect(reverse("plugins:netbox_nsm:object_sync"))

        bulk_action = (request.POST.get("bulk_fix") or "").strip()
        if bulk_action:
            selection_ids = request.POST.getlist("sync_select")
            fix_tokens = expand_bulk_fix_tokens(selection_ids, bulk_action)
            if not selection_ids:
                messages.warning(request, _("No sync issues selected."))
                return redirect(
                    reverse("plugins:netbox_nsm:object_sync")
                    + _sync_query_from_request(request, prefer_post=True)
                )
            if not fix_tokens:
                messages.warning(
                    request,
                    _("No selected issues support this bulk action."),
                )
                return redirect(
                    reverse("plugins:netbox_nsm:object_sync")
                    + _sync_query_from_request(request, prefer_post=True)
                )
        else:
            fix_tokens = [token for token in request.POST.getlist("fix") if token]

        if not fix_tokens:
            messages.warning(request, _("No fix action selected."))
            return redirect(
                reverse("plugins:netbox_nsm:object_sync")
                + _sync_query_from_request(request, prefer_post=True)
            )

        fix_result = apply_sync_fixes(fix_tokens, sync_config)
        if fix_result.fixed:
            messages.success(
                request,
                _("Fixed %(count)d sync issue(s).") % {"count": fix_result.fixed},
            )
        if fix_result.skipped:
            messages.info(
                request,
                _("Skipped %(count)d fix action(s) (already resolved or invalid).")
                % {"count": fix_result.skipped},
            )
        for error in fix_result.errors[:5]:
            messages.error(request, error)
        return redirect(
            reverse("plugins:netbox_nsm:object_sync")
            + _sync_query_from_request(request, prefer_post=True)
        )
