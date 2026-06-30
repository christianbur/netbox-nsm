"""
Legacy redirect for the removed standalone IP Analysis page.

Bookmarks and old links under ``/plugins/netbox-nsm/ip-analysis/`` are sent to
Object Analyzer. When the old column-A query params are present, the first
object is pre-selected.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

__all__ = ("IpAnalysisLegacyRedirectView",)


def _first_legacy_object_params(request) -> dict[str, str] | None:
    for prefix in ("ip", "ip2"):
        ct_vals = request.GET.getlist(f"{prefix}_ct")
        pk_vals = request.GET.getlist(f"{prefix}_pk")
        if not ct_vals or not pk_vals:
            continue
        name_vals = request.GET.getlist(f"{prefix}_name")
        params = {"ct": ct_vals[0], "pk": pk_vals[0]}
        if name_vals and name_vals[0]:
            params["name"] = name_vals[0]
        return params
    return None


class IpAnalysisLegacyRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        from netbox_nsm.analyzers.registry import analyzer_reverse

        target = analyzer_reverse("object_analyzer")
        legacy = _first_legacy_object_params(request)
        if legacy:
            target = f"{target}?{urlencode(legacy)}"
        return redirect(target, permanent=True)
