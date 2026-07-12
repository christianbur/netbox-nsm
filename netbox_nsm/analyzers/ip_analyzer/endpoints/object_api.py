"""
Lazy-load address drilldown for a single IP Analyzer cell object.

GET /plugins/netbox-nsm/api/ip-analyzer/object/?ct=&pk=
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.analyzers.ip_analyzer.ipa_ipam_tree import _build_ipa_object_drilldown_nodes

__all__ = ("IpAnalyzerObjectDrilldownApiView",)


def _build_object_drilldown_nodes(obj):
    """Return enriched IPAM logical tree nodes for one cell object."""
    return _build_ipa_object_drilldown_nodes(obj)


def _mark_lazy_loaded_nodes(nodes):
    for node in nodes or []:
        node["ipa_lazy_loaded"] = True
        _mark_lazy_loaded_nodes(node.get("children") or [])


class IpAnalyzerObjectDrilldownApiView(LoginRequiredMixin, View):
    http_method_names = ["get"]

    def get(self, request):
        ct_raw = request.GET.get("ct")
        pk_raw = request.GET.get("pk")
        depth_raw = request.GET.get("depth", "0")

        if not (str(ct_raw).isdigit() and str(pk_raw).isdigit()):
            return JsonResponse({"error": "ct and pk required"}, status=400)

        try:
            depth = max(int(depth_raw), 0)
        except (TypeError, ValueError):
            depth = 0

        ct = ContentType.objects.filter(pk=int(ct_raw)).first()
        if ct is None:
            return JsonResponse({"error": "content type not found"}, status=404)

        model_cls = ct.model_class()
        if model_cls is None:
            return JsonResponse({"error": "model not found"}, status=404)

        obj = model_cls.objects.filter(pk=int(pk_raw)).first()
        if obj is None:
            return JsonResponse({"error": "object not found"}, status=404)

        nodes, copy_lines = _build_object_drilldown_nodes(obj)
        _mark_lazy_loaded_nodes(nodes)
        html = render_to_string(
            "netbox_nsm/inc/ipa_cell_tree_drilldown_fragment.html",
            {
                "nodes": nodes,
                "depth": depth + 1,
                "ipa_cell_pill": False,
            },
            request=request,
        )
        return JsonResponse({"html": html, "copy_lines": copy_lines})
