"""
Lazy-load address drilldown for a single IP Analyzer cell object.

GET /plugins/netbox-nsm/api/ip-analysis/object/?ct=&pk=
"""

from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views import View

from netbox_nsm.analysis.addr_analysis_utils import (
    _build_addr_tree_node,
    _enrich_addr_tree_copy_lines,
    _enrich_addr_tree_leaf_counts,
    _flatten_addr_tree_paths,
    _object_supports_addr_analysis,
)

__all__ = ("IpAnalysisObjectDrilldownApiView",)


def _build_object_drilldown_nodes(obj):
    """Return enriched addr-tree child nodes for one cell object."""
    if not obj or not _object_supports_addr_analysis(obj):
        return [], []

    node = _build_addr_tree_node(obj)
    if not node:
        return [], []

    children = node.get("children") or []
    if children:
        for child in children:
            _enrich_addr_tree_copy_lines(child)
            _enrich_addr_tree_leaf_counts(child)
        copy_lines = _flatten_addr_tree_paths(children)
        return children, copy_lines

    if node.get("kind") == "leaf":
        _enrich_addr_tree_copy_lines(node)
        _enrich_addr_tree_leaf_counts(node)
        copy_lines = _flatten_addr_tree_paths([node])
        return [node], copy_lines

    return [], []


class IpAnalysisObjectDrilldownApiView(LoginRequiredMixin, View):
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
        html = render_to_string(
            "netbox_nsm/inc/addr_tree_nodes_fragment.html",
            {
                "nodes": nodes,
                "depth": depth + 1,
                "prefix": "ipa",
                "show_copy": False,
                "ipa_cell_pill": False,
            },
            request=request,
        )
        return JsonResponse({"html": html, "copy_lines": copy_lines})
